"""Deterministic scoring, evidence replay, and time allocation."""
import json
from datetime import datetime,timedelta,timezone,date
from zoneinfo import ZoneInfo
from app.core.db import *
from app.core.security import fail

def bkt(p,correct):
    likelihood=.9 if correct else .1
    alternative=.25 if correct else .75
    posterior=p*likelihood/(p*likelihood+(1-p)*alternative)
    return posterior+(1-posterior)*.2

def mastery(db,student,class_id=None):
    sql='SELECT o.*, l.skill_id AS canonical_skill FROM observations o LEFT JOIN project_evidence_links l ON l.observation_id=o.id WHERE o.student_id=:u'
    args={'u':student}
    if class_id:
        sql+=' AND o.class_id=:c'; args['c']=class_id
    sql+=' ORDER BY o.rowid'
    result={}
    aliases=set()
    for obs in rows(db,sql,**args):
        skill=obs['canonical_skill'] or obs['skill']
        if obs['canonical_skill']:aliases.add(skill)
        item=result.setdefault(skill,{'probability':.2,'evidence_count':0})
        before=item['probability']
        item['probability']=bkt(item['probability'],obs['correct'])
        item['evidence_count']+=1
        item['last_update']={'prior':before,'posterior':item['probability'],'evidence_id':obs['attempt_id'],'parameter_version':'bkt-v1','mastery_threshold':.75,'weak_threshold':.45}
    for skill in aliases:result['catalog:'+skill]=result[skill]
    return result

def observations(db,attempt,questions,answers,student,class_id=None):
    feedback=[]; scores=[]
    for index,q in enumerate(questions):
        if q.get('kind')=='subjective':
            feedback.append({'id':q['id'],'prompt':q['prompt'],'status':'pending_review','skill':q['skill']}); continue
        value=str(answers.get(q['id'],'' )).strip()
        expected=str(q['answer']).strip()
        if q.get('kind')=='multi':
            correct=set(value.split(','))==set(expected.split(','))
        else: correct=value==expected
        scores.append(int(correct))
        from app.services.engineering_goals import add_evidence
        if not add_evidence(db,student,q,attempt,correct,index):
            insert(db,'observations',id=uid(),attempt_id=attempt,student_id=student,class_id=class_id,skill=q['skill'],correct=int(correct),sequence=index)
        feedback.append({'id':q['id'],'prompt':q['prompt'],'answer':expected,'explanation':q.get('explanation',''),'correct':correct,'skill':q['skill'],'rule_version':'assessment-v1','recommendation':'进入后续学习并按计划复习' if correct else '复习本知识点资料并完成补强测验'})
    return feedback,(sum(scores)/len(scores) if scores else None)

def save_mastery(db,student,class_id=None):
    for skill,item in mastery(db,student,class_id).items():
        insert(db,'mastery_snapshots',id=uid(),student_id=student,class_id=class_id,skill=skill,probability=item['probability'],evidence_count=item['evidence_count'],created_at=now())
    touch(db,student)


def _allocate_early(db,student,minutes,due_date,exclude_goal=None,goal_limit=None):
    budget=one(db,'SELECT * FROM budgets WHERE user_id=:u',u=student)
    tz=ZoneInfo(budget['timezone']); today=datetime.now(tz).date()
    due=datetime.fromisoformat(due_date).astimezone(tz).date() if 'T' in due_date else date.fromisoformat(due_date)
    if due<today or due>today+timedelta(days=730): fail(422,'截止日期须在未来两年内')
    reservations=rows(db,"SELECT * FROM reservations WHERE student_id=:u AND status='active'",u=student)
    daily={}; weekly={}; goal_week={}
    def add(day,m):
        key=date.fromisoformat(day).strftime('%G-%V')
        daily[day]=daily.get(day,0)+m; weekly[key]=weekly.get(key,0)+m
    for r in reservations:
        if exclude_goal and r['goal_id']==exclude_goal: continue
        add(r['local_date'],r['minutes'])
        if exclude_goal and r['goal_id']=='project:'+exclude_goal:
            week=date.fromisoformat(r['local_date']).strftime('%G-%V');goal_week[week]=goal_week.get(week,0)+r['minutes']
    # Actual work replaces reservations upon completion; never double count it.
    for event in actual_events(db,student):
        day=datetime.fromisoformat(event['created_at']).astimezone(tz).date().isoformat()
        add(day,event['minutes'])
        if exclude_goal and event.get('goal_id')==exclude_goal:
            week=date.fromisoformat(day).strftime('%G-%V');goal_week[week]=goal_week.get(week,0)+event['minutes']
    remaining=minutes; output=[]; days=json.loads(budget['days'])
    for offset in range((due-today).days+1):
        day=today+timedelta(days=offset)
        if day.weekday() not in days: continue
        ds=day.isoformat(); wk=day.strftime('%G-%V')
        available=min(budget['daily_minutes']-daily.get(ds,0),budget['weekly_minutes']-weekly.get(wk,0))
        if goal_limit: available=min(available,goal_limit-goal_week.get(wk,0))
        if available<=0: continue
        m=min(remaining,available); output.append({'date':ds,'minutes':m}); remaining-=m
        add(ds,m); goal_week[wk]=goal_week.get(wk,0)+m
        if remaining==0: break
    if remaining: fail(409,f'全局预算不足，仍缺{remaining}分钟；请延长截止或调整预算','BUDGET_CONFLICT')
    return output

def allocate(db,student,minutes,due_date,exclude_goal=None,goal_limit=None,pace='early'):
    if pace not in ('early','balanced'):fail(422,'排期方式无效')
    if not minutes:return []
    baseline=_allocate_early(db,student,minutes,due_date,exclude_goal,goal_limit)
    if pace=='early':return baseline
    # Prefer ~15-minute sessions spread over the available horizon, not tiny daily fragments.
    import heapq,math
    budget=one(db,'SELECT * FROM budgets WHERE user_id=:u',u=student)
    tz=ZoneInfo(budget['timezone']);today=datetime.now(tz).date()
    due=datetime.fromisoformat(due_date).astimezone(tz).date() if 'T' in due_date else date.fromisoformat(due_date)
    daily={};weekly={};project_week={}
    def used(day,m):
        week=date.fromisoformat(day).strftime('%G-%V')
        daily[day]=daily.get(day,0)+m;weekly[week]=weekly.get(week,0)+m
    for r in rows(db,"SELECT * FROM reservations WHERE student_id=:u AND status='active'",u=student):
        if exclude_goal and r['goal_id']==exclude_goal:continue
        used(r['local_date'],r['minutes'])
        if exclude_goal and r['goal_id']=='project:'+exclude_goal:
            week=date.fromisoformat(r['local_date']).strftime('%G-%V');project_week[week]=project_week.get(week,0)+r['minutes']
    for event in actual_events(db,student):
        ds=datetime.fromisoformat(event['created_at']).astimezone(tz).date().isoformat();used(ds,event['minutes'])
        if exclude_goal and event.get('goal_id')==exclude_goal:
            week=date.fromisoformat(ds).strftime('%G-%V');project_week[week]=project_week.get(week,0)+event['minutes']
    days=json.loads(budget['days']);slots=[];week_left={}
    for offset in range((due-today).days+1):
        day=today+timedelta(days=offset);ds=day.isoformat();week=day.strftime('%G-%V')
        capacity=max(0,budget['daily_minutes']-daily.get(ds,0))
        week_left[week]=max(0,min(budget['weekly_minutes']-weekly.get(week,0),max(0,goal_limit-project_week.get(week,0)) if goal_limit else budget['weekly_minutes']))
        if day.weekday() in days and capacity and week_left[week]:slots.append({'date':ds,'week':week,'capacity':capacity})
    if not slots:fail(409,'截止日前没有可用学习时段','BUDGET_CONFLICT')
    count=min(len(slots),max(1,math.ceil(minutes/15)))
    selected={round(i*(len(slots)-1)/(count-1)) for i in range(count)} if count>1 else {len(slots)//2}
    heap=[(0,i) for i in selected];heapq.heapify(heap);secondary=[i for i in range(len(slots)) if i not in selected]
    assigned=[0]*len(slots);remaining=minutes
    while remaining:
        if not heap:
            if not secondary:fail(409,'截止日前可用预算不足','BUDGET_CONFLICT')
            heap=[(assigned[i],i) for i in secondary];heapq.heapify(heap);secondary=[]
        amount,i=heapq.heappop(heap);slot=slots[i]
        if assigned[i]>=slot['capacity'] or not week_left[slot['week']]:continue
        assigned[i]+=1;week_left[slot['week']]-=1;remaining-=1
        if assigned[i]<slot['capacity'] and week_left[slot['week']]:heapq.heappush(heap,(assigned[i],i))
    return [{'date':slot['date'],'minutes':assigned[i]} for i,slot in enumerate(slots) if assigned[i]]


def actual_events(db,student,class_id=None):
    args={'u':student}; suffix=''
    if class_id: suffix=' AND class_id=:c';args['c']=class_id
    events=rows(db,'SELECT id,minutes,created_at,resource_id AS source_id FROM study_sessions WHERE student_id=:u'+suffix,**args)
    events+=rows(db,'SELECT id,minutes,created_at,assignment_id AS source_id,goal_id FROM attempts WHERE student_id=:u'+suffix,**args)
    events+=rows(db,'SELECT id,minutes,created_at,source_id,goal_id FROM project_worklogs WHERE student_id=:u'+suffix,**args)
    if not class_id:
        events+=rows(db,'SELECT c.id,c.minutes,c.created_at,c.item_id AS source_id,p.goal_id FROM checkins c JOIN paths p ON p.id=c.path_id WHERE c.student_id=:u',u=student)
        events+=rows(db,'SELECT id,minutes,created_at,material_link_id AS source_id FROM learning_sessions WHERE student_id=:u',u=student)
    return events

SKILLS=[{'id':'functions','name':'函数基础','minutes':30,'prerequisites':[]},
        {'id':'recursion','name':'递归与结束条件','minutes':45,'prerequisites':['functions']},
        {'id':'stack','name':'调用栈与综合练习','minutes':45,'prerequisites':['recursion']}]

QUESTIONS=[
 {'id':'q1','skill':'functions','prompt':'Python定义函数使用哪个关键字？','options':['def','class','return'],'answer':'0','explanation':'def用于定义函数。'},
 {'id':'q2','skill':'functions','prompt':'函数返回结果使用哪个语句？','options':['print','return','pass'],'answer':'1','explanation':'return返回结果，print只输出。'},
 {'id':'q3','skill':'recursion','prompt':'递归必须有何条件？','options':['无限循环','结束条件','全局变量'],'answer':'1','explanation':'结束条件确保递归能够终止。'},
 {'id':'q4','skill':'recursion','prompt':'递归调用的规模应该怎样变化？','options':['趋向结束条件','一直增大','不变'],'answer':'0','explanation':'每次调用须逐步趋向基本情况。'},
 {'id':'q5','skill':'stack','prompt':'函数嵌套调用通常如何返回？','options':['先进先出','随机','后进先出'],'answer':'2','explanation':'调用栈遵循后进先出。'},
 {'id':'q6','skill':'stack','prompt':'无限递归最可能导致什么？','options':['栈深度错误','自动结束','自动转循环'],'answer':'0','explanation':'递归深度受运行环境限制。'}]

def public_questions(questions):
    return [{k:v for k,v in q.items() if k not in ('answer','explanation')} for q in questions]
