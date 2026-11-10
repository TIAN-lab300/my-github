import json,re
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from fastapi import APIRouter,Depends,BackgroundTasks,Header
from fastapi import HTTPException
from pydantic import ValidationError
from app.core.db import *
from app.core.security import *
from app.schemas import GoalInput,BudgetInput,Checkin,Submission
from app.services.learning import *
from app.services.diagnostic_bank import RETEST,validate_answers
from app.services.topic_bank import question_bank,keywords,PRACTICE
from app.services.planning_rules import graph_snapshot

router=APIRouter()

def question_snapshot(bank,version):
    return [{**q,'version':version,'rule_version':'assessment-v1','source':{'kind':'curated' if version in ('curated-v1','diagnostic-v1','equivalent-v1') else 'reviewed_graph','id':'zhixing-'+q['id'],'license':'项目自编题' if version in ('curated-v1','diagnostic-v1','equivalent-v1') else '经管理员审核的图谱题库，来源见图谱版本'}} for q in bank]

@router.get('/curriculum/skills')
def curriculum(user=Depends(current_user)):
    with transaction() as db:
        graph,version=graph_snapshot(db)
        bank,_=question_bank(db,'diagnostic')
        covered={q['skill'] for q in bank}
        return {'version':version,'skills':[{'id':node['id'],'name':node['name'],'minutes':node['minutes'],'prerequisites':node['prerequisites'],'diagnostic_available':node['id'] in covered} for node in graph]}

@router.post('/goals/interpret')
def interpret(body:dict,user=Depends(current_user)):
    role(user,'student')
    text=str(body.get('text','')).strip()
    if not text or len(text)>1000: fail(422,'请输入1至1000字目标描述')
    skills=[]
    if 'python' in text.lower(): skills=[s['id'] for s in SKILLS]
    else:
        for skill,words in [('functions',['函数']),('recursion',['递归']),('stack',['调用栈'])]:
            if any(word in text for word in words):skills.append(skill)
    with transaction() as db:
        graph,_=graph_snapshot(db)
    skill_ids={node['id'] for node in graph}
    skills=[skill for skill in skills if skill in skill_ids]
    for skill,aliases in keywords(graph).items():
        if skill not in skills and any(alias.lower() in text.lower() for alias in aliases):skills.append(skill)
    date_match=re.search(r'\d{4}-\d{2}-\d{2}',text)
    time_match=re.search(r'每周\s*(\d+)\s*(小时|分钟)',text)
    weekly=int(time_match[1])*(60 if time_match[2]=='小时' else 1) if time_match else None
    return {'title':text,'target_skill_ids':skills,'due_date':date_match[0] if date_match else None,'weekly_minutes':weekly,
            'preference':'video' if '视频' in text else 'text' if '文本' in text or '阅读' in text else 'unspecified',
            'needs_clarification':[] if skills else ['请补充知识范围，当前题库支持函数、递归和调用栈'],
            'confirmed':False,'method':'local-rule-v1'}

@router.get('/goals/{id}/diagnoses')
def diagnosis_history(id:str,user=Depends(current_user)):
    with transaction() as db:
        goal_access(db,user,id)
        return rows(db,'SELECT id,attempt_id,created_at FROM diagnoses WHERE goal_id=:g ORDER BY created_at DESC',g=id)

@router.post('/goals/{id}/diagnoses/retest',status_code=201)
def retest(id:str,user=Depends(current_user)):
    with transaction() as db:
        g=goal_access(db,user,id)
        if g['status']=='archived': fail(409,'目标已归档')
        history=rows(db,'SELECT * FROM diagnoses WHERE goal_id=:g AND goal_version=:v ORDER BY created_at',g=id,v=g['version'])
        if not history or not history[0]['attempt_id']: fail(409,'请先完成首次诊断')
        if len(history)>1:
            if not history[-1]['attempt_id']: return {'id':history[-1]['id']}
            fail(409,'等价题库已用尽；请通过路径练习补强，不能重复公开试卷刷掌握度','RETEST_BANK_EXHAUSTED')
        practiced=one(db,'SELECT c.id FROM checkins c JOIN paths p ON p.id=c.path_id WHERE p.goal_id=:g AND c.created_at>:t AND c.proportion>0',g=id,t=history[0]['created_at'])
        if not practiced: fail(409,'请先完成该目标的一次路径补强学习记录')
        graph_id=history[0]['bank_version']
        bank,bank_version=question_bank(db,'retest',graph_id if graph_id not in ('diagnostic-v1','curated-v1') else None)
        questions=question_snapshot(bank,bank_version)
        if not questions: fail(409,'该目标缺少等价题库','RETEST_BANK_EXHAUSTED')
        did=uid();insert(db,'diagnoses',id=did,goal_id=id,student_id=user['id'],questions=dump(questions),goal_version=g['version'],bank_version=bank_version,created_at=now())
        audit(db,user['id'],'diagnostic_retest_created',did)
        return {'id':did}

@router.get('/learners/me/budget')
def budget(user=Depends(current_user)):
    role(user,'student')
    with transaction() as db:
        b=one(db,'SELECT * FROM budgets WHERE user_id=:u',u=user['id']);b['days']=json.loads(b['days']);return b

@router.patch('/learners/me/budget')
def budget_edit(body:BudgetInput,user=Depends(current_user)):
    role(user,'student')
    try: ZoneInfo(body.timezone)
    except ZoneInfoNotFoundError: fail(422,'时区无效')
    if not body.days or not set(body.days)<=set(range(7)): fail(422,'请选择有效学习日')
    with transaction() as db:
        b=one(db,'SELECT * FROM budgets WHERE user_id=:u',u=user['id'])
        if b['version']!=body.version: fail(409,'预算已变化')
        run(db,'UPDATE budgets SET daily_minutes=:d,weekly_minutes=:w,timezone=:t,days=:days,version=version+1 WHERE user_id=:u',d=body.daily_minutes,w=body.weekly_minutes,t=body.timezone,days=dump(sorted(set(body.days))),u=user['id'])
        touch(db,user['id'])
    return {'ok':True,'message':'预算变化，请重新检查活动路径并生成重规划预览'}

@router.get('/goals')
def listing(user=Depends(current_user)):
    role(user,'student')
    with transaction() as db:
        goals=rows(db,'SELECT * FROM goals WHERE student_id=:u ORDER BY created_at DESC',u=user['id'])
        for g in goals:
            g['target_skill_ids']=json.loads(g.pop('skills'))
            g['paths']=rows(db,'SELECT id,status,content_status,reason,created_at,fingerprint FROM paths WHERE goal_id=:id ORDER BY created_at DESC',id=g['id'])
            current_budget=one(db,'SELECT version FROM budgets WHERE user_id=:u',u=user['id'])
            g['requires_replan']=any(p['status']=='active' and (json.loads(p['fingerprint'])['goal']!=g['version'] or json.loads(p['fingerprint'])['budget']!=current_budget['version']) for p in g['paths'])
            g['diagnoses']=rows(db,'SELECT id,attempt_id FROM diagnoses WHERE goal_id=:id ORDER BY created_at DESC',id=g['id'])
        return goals

def validate_goal(db,user,body):
    if not body.title.strip(): fail(422,'目标标题不能为空')
    try: due=date.fromisoformat(body.due_date)
    except ValueError: fail(422,'截止日期格式错误')
    settings=one(db,'SELECT timezone FROM budgets WHERE user_id=:u',u=user['id'])
    today=datetime.now(ZoneInfo(settings['timezone'])).date()
    if due<today or due>today+timedelta(days=730): fail(422,'截止日期须在未来两年内')
    if body.class_id:
        c=class_access(db,user,body.class_id)
        if c['status']!='active': fail(409,'不能关联归档班级')
    graph,_=graph_snapshot(db)
    skills=body.target_skill_ids
    if skills and (len(skills)!=len(set(skills)) or not set(skills)<=set(s['id'] for s in graph)): fail(422,'知识点不存在或重复')
    if not skills and {node['id'] for node in graph}=={node['id'] for node in SKILLS} and any(term in body.title.lower() for term in ('python','函数','递归','调用栈')):
        skills=[node['id'] for node in graph]
    if not skills:
        skills=[skill for skill,aliases in keywords(graph).items() if any(alias.lower() in body.title.lower() for alias in aliases)]
        if not skills and 'python' in body.title.lower():skills=[node['id'] for node in graph if node['id'] in {item['id'] for item in SKILLS}]
    return skills

def preserve_goal(db,g):
    if not one(db,'SELECT id FROM goal_revisions WHERE goal_id=:g AND version=:v',g=g['id'],v=g['version']):
        insert(db,'goal_revisions',id=uid(),goal_id=g['id'],version=g['version'],payload=dump(g),created_at=now())

@router.get('/goals/{id}')
def detail(id:str,user=Depends(current_user)):
    with transaction() as db:
        g=goal_access(db,user,id)
        g['target_skill_ids']=json.loads(g.pop('skills'))
        return g

@router.get('/goals/{id}/history')
def goal_history(id:str,user=Depends(current_user)):
    with transaction() as db:
        goal_access(db,user,id)
        return rows(db,'SELECT version,payload,created_at FROM goal_revisions WHERE goal_id=:g ORDER BY version DESC',g=id)

@router.get('/goals/{id}/feasibility')
def feasibility(id:str,user=Depends(current_user)):
    with transaction() as db:
        g=goal_access(db,user,id)
        skills=json.loads(g['skills'])
        if not skills:return {'status':'missing_structure','required_minutes':None,'reasons':['请先确认目标知识点映射'],'proven_infeasible':False}
        from app.services.planning_rules import graph_snapshot
        graph,_=graph_snapshot(db)
        required_skills=set(skills)
        for node in reversed(graph):
            if node['id'] in required_skills: required_skills.update(node['prerequisites'])
        required=sum(s['minutes'] for s in graph if s['id'] in required_skills)
        try:
            schedule=allocate(db,user['id'],required,g['due_date'],id,g['weekly_minutes'])
            from app.api.resources import visible
            text=''
            for resource in visible(db,user):
                if resource['status']!='published' and resource['scope']!='private':continue
                version=one(db,"SELECT body FROM resource_versions WHERE id=:id AND parse_status='ready' AND index_status='indexed'",id=resource['current_version'])
                if version:text+=version['body'].lower()+'\n'
            tokens=keywords(graph)
            gaps=[skill for skill in required_skills if not any(token.lower() in text for token in tokens[skill])]
            return {'status':'evidence_gap' if gaps else 'feasible','required_minutes':required,'schedule':schedule,
                    'missing_skills':gaps,'reasons':['缺少授权正文，请补充资料：'+','.join(gaps)] if gaps else [],'proven_infeasible':False}
        except HTTPException as exc:
            if exc.status_code!=409:raise
            return {'status':'budget_conflict','required_minutes':required,'schedule':[],'reasons':[exc.detail['message']],'proven_infeasible':True}

@router.post('/goals',status_code=201)
def create(body:GoalInput,user=Depends(current_user)):
    role(user,'student')
    with transaction() as db:
        skills=validate_goal(db,user,body);id=uid()
        insert(db,'goals',id=id,student_id=user['id'],title=body.title.strip(),skills=dump(skills),weekly_minutes=body.weekly_minutes,due_date=body.due_date,class_id=body.class_id,preference=body.preference,created_at=now())
        preserve_goal(db,one(db,'SELECT * FROM goals WHERE id=:id',id=id))
        touch(db,user['id'])
    return {'id':id,'target_skill_ids':skills,'message':'请确认技能；当前本地知识图支持函数、递归、调用栈，其他主题需补齐图谱和证据'}

@router.patch('/goals/{id}')
def edit(id:str,body:dict,user=Depends(current_user)):
    with transaction() as db:
        g=goal_access(db,user,id)
        if body.get('version')!=g['version']: fail(409,'目标版本已变化')
        if g['status']=='archived': fail(409,'归档目标只读')
        if set(body)-{'version','status','title','target_skill_ids','weekly_minutes','due_date','class_id','preference'}: fail(422,'目标包含不支持的字段')
        if body.get('status',g['status']) not in (g['status'],'archived'): fail(422,'目标状态不合法')
        preserve_goal(db,g)
        if body.get('status')=='archived':
            run(db,"UPDATE goals SET status='archived',version=version+1 WHERE id=:id",id=id)
            run(db,"UPDATE reservations SET status='cancelled' WHERE goal_id=:id AND status='active'",id=id)
        else:
            try:
                merged=GoalInput(title=body.get('title',g['title']),target_skill_ids=body.get('target_skill_ids',json.loads(g['skills'])),weekly_minutes=body.get('weekly_minutes',g['weekly_minutes']),due_date=body.get('due_date',g['due_date']),class_id=body.get('class_id',g['class_id']),preference=body.get('preference',g['preference']))
            except ValidationError: fail(422,'目标字段不合法')
            skills=validate_goal(db,user,merged)
            run(db,'UPDATE goals SET title=:t,skills=:s,weekly_minutes=:w,due_date=:d,class_id=:c,version=version+1 WHERE id=:id',t=merged.title,s=dump(skills),w=merged.weekly_minutes,d=merged.due_date,c=merged.class_id,id=id)
            run(db,'UPDATE goals SET preference=:p WHERE id=:id',p=merged.preference,id=id)
        touch(db,user['id'])
        preserve_goal(db,one(db,'SELECT * FROM goals WHERE id=:id',id=id))
    return {'ok':True,'requires_replan':True,'message':'目标版本已更新，原路径与已完成记录保留，请重新评估路径'}

@router.post('/goals/{id}/diagnoses',status_code=201)
def diagnose(id:str,user=Depends(current_user)):
    with transaction() as db:
        g=goal_access(db,user,id)
        if g['status']=='archived': fail(409,'目标已归档')
        graph,_=graph_snapshot(db)
        if not json.loads(g['skills']) or not set(json.loads(g['skills']))<=set(s['id'] for s in graph): fail(409,'该主题缺少可用题库')
        # Do not allow infinite replay of identical disclosed questions as new evidence.
        existing=one(db,'SELECT * FROM diagnoses WHERE goal_id=:id AND goal_version=:v ORDER BY created_at DESC',id=id,v=g['version'])
        if existing: return {'id':existing['id'],'questions':public_questions(json.loads(existing['questions'])),'attempt_id':existing['attempt_id']}
        bank,bank_version=question_bank(db,'diagnostic')
        questions=question_snapshot(bank,bank_version)
        missing=set(json.loads(g['skills']))-{q['skill'] for q in questions}
        if not questions or missing:fail(409,'诊断题库覆盖不足，请补充材料或重试','DIAGNOSTIC_COVERAGE_GAP')
        did=uid();insert(db,'diagnoses',id=did,goal_id=id,student_id=user['id'],questions=dump(questions),goal_version=g['version'],bank_version=bank_version,created_at=now())
        return {'id':did,'questions':public_questions(questions),'attempt_id':None}

@router.get('/diagnoses/{id}')
def diagnostic(id:str,user=Depends(current_user)):
    with transaction() as db:
        d=one(db,'SELECT * FROM diagnoses WHERE id=:id AND student_id=:u',id=id,u=user['id'])
        if not d: fail(404,'诊断不存在')
        d['questions']=public_questions(json.loads(d['questions']))
        d['draft_answers']=json.loads(d['draft_answers'])
        d['result']=one(db,'SELECT * FROM attempts WHERE id=:id',id=d['attempt_id']) if d['attempt_id'] else None
        mapped={q['skill'] for q in d['questions']}
        d['coverage']={'mapped_skills':sorted(mapped),'question_count':len(d['questions']),'confidence':'normal' if len(d['questions'])>=6 else 'low'}
        d['mastery']=json.loads(d.pop('mastery_snapshot')) if d['attempt_id'] else {}
        return d

@router.put('/diagnoses/{id}/draft')
def diagnostic_draft(id:str,body:dict,user=Depends(current_user)):
    with transaction() as db:
        d=one(db,'SELECT * FROM diagnoses WHERE id=:id AND student_id=:u',id=id,u=user['id'])
        if not d or d['attempt_id']: fail(409,'诊断不存在或已提交')
        g=goal_access(db,user,d['goal_id'])
        if g['status']=='archived': fail(409,'归档目标不能修改诊断')
        if g['version']!=d['goal_version']: fail(409,'目标已变化，请领取当前版本诊断')
        validate_answers(json.loads(d['questions']),body,partial=True)
        run(db,'UPDATE diagnoses SET draft_answers=:a WHERE id=:id',a=dump(body),id=id)
    return {'ok':True}

@router.post('/diagnoses/{id}/submit')
def diagnostic_submit(id:str,body:Submission,user=Depends(current_user)):
    with transaction() as db:
        d=one(db,'SELECT * FROM diagnoses WHERE id=:id AND student_id=:u',id=id,u=user['id'])
        if not d: fail(404,'诊断不存在')
        if d['attempt_id']: return one(db,'SELECT * FROM attempts WHERE id=:id',id=d['attempt_id'])
        g=goal_access(db,user,d['goal_id']);questions=json.loads(d['questions'])
        if g['status']=='archived': fail(409,'归档目标不能提交新诊断')
        if g['version']!=d['goal_version']: fail(409,'目标已变化，请领取当前版本诊断')
        validate_answers(questions,body.answers)
        aid=uid();insert(db,'attempts',id=aid,student_id=user['id'],goal_id=g['id'],class_id=g['class_id'],answers=dump(body.answers),feedback='[]',status='scored',minutes=body.minutes,created_at=now())
        f,s=observations(db,aid,questions,body.answers,user['id'],g['class_id'])
        run(db,'UPDATE attempts SET feedback=:f,score=:s WHERE id=:id',f=dump(f),s=s,id=aid)
        run(db,'UPDATE diagnoses SET attempt_id=:a WHERE id=:id',a=aid,id=id)
        run(db,'UPDATE diagnoses SET mastery_snapshot=:m WHERE id=:id',m=dump(mastery(db,user['id'])),id=id)
        save_mastery(db,user['id']);return one(db,'SELECT * FROM attempts WHERE id=:id',id=aid)

@router.post('/goals/{id}/planning-runs',status_code=202)
def planning(id:str,background:BackgroundTasks,engine:str='local',idempotency_key:str=Header(default=''),user=Depends(current_user)):
    return queue_run(id,'initial',background,idempotency_key,user,engine)

@router.post('/goals/{id}/replan-previews',status_code=202)
def replan(id:str,background:BackgroundTasks,engine:str='local',idempotency_key:str=Header(default=''),user=Depends(current_user)):
    return queue_run(id,'replan',background,idempotency_key,user,engine)

def queue_run(id,kind,background,key,user,engine='local'):
    if engine not in ('local','cloud'):fail(422,'规划模式不合法')
    from app.services.planning import execute
    if not key or len(key)>120: fail(422,'请提供Idempotency-Key')
    with transaction() as db:
        g=goal_access(db,user,id)
        if g['status']=='archived': fail(409,'目标已归档')
        existing=one(db,'SELECT * FROM agent_runs WHERE actor_id=:u AND kind=:k AND idem_key=:i',u=user['id'],k=kind,i=key)
        if existing:
            if existing['execution_mode']!=engine:fail(409,'幂等键已用于其他执行模式')
            if existing['goal_id']!=id: fail(409,'幂等键已用于其他目标')
            return {'run_id':existing['id'],'status':existing['status']}
        config=one(db,"SELECT * FROM model_configs WHERE status='active' LIMIT 1") if engine=='cloud' else None
        if engine=='cloud' and not config:fail(409,'请先由管理员评估并激活模型配置')
        rid=uid();insert(db,'agent_runs',execution_mode=engine,model_config_id=config['id'] if config else None,id=rid,actor_id=user['id'],goal_id=id,kind=kind,status='queued',idem_key=key,created_at=now())
    background.add_task(execute,rid)
    return {'run_id':rid,'status':'queued'}

@router.get('/paths/{id}')
def path(id:str,user=Depends(current_user)):
    with transaction() as db:
        p=one(db,'SELECT * FROM paths WHERE id=:id AND student_id=:u',id=id,u=user['id'])
        if not p: fail(404,'路径不存在')
        for k in ('tasks','sources','validation'): p[k]=json.loads(p[k])
        mastered=mastery(db,user['id'])
        p['remediations']=p['validation'].get('remediations',[])
        for item in p['tasks']+p['remediations']:
            item['locked']=any(mastered.get(s,{}).get('probability',.2)<.75 for s in item.get('prerequisites',[]))
            item['checkin']=one(db,'SELECT * FROM checkins WHERE path_id=:p AND item_id=:i',p=id,i=item['id'])
        p['requires_refresh']=p['fingerprint']!=fingerprint(db,user['id'],p['goal_id'])
        warnings=[]
        for rejected in rows(db,"SELECT validation FROM paths WHERE goal_id=:g AND status='rejected' ORDER BY created_at DESC LIMIT 3",g=p['goal_id']):
            warnings.extend(json.loads(rejected['validation']).get('triggers',[]))
        p['replan_warnings']=list(dict.fromkeys(warnings))
        return p

@router.post('/paths/{id}/accept')
def accept(id:str,user=Depends(current_user)):
    with transaction() as db:
        p=one(db,'SELECT * FROM paths WHERE id=:id AND student_id=:u',id=id,u=user['id'])
        if not p: fail(404,'路径不存在')
        if p['status']=='active': return {'ok':True}
        if p['status']!='pending_acceptance' or p['content_status']!='verified': fail(409,'路径尚不满足接受条件')
        g=goal_access(db,user,p['goal_id'])
        if g['status']=='archived' or fingerprint(db,user['id'],g['id'])!=p['fingerprint']: fail(409,'预览已过期，请重新生成','STALE_PREVIEW')
        if g['class_id'] and class_access(db,user,g['class_id'])['status']!='active':fail(409,'关联班级已归档')
        from app.core.security import resource_access
        for source in json.loads(p['sources']):
            r=resource_access(db,user,source['resource_id'])
            private_owner=r['scope']=='private' and r['owner_id']==user['id']
            if (r['status']!='published' and not private_owner) or r['current_version']!=source['version_id']: fail(409,'来源已变化，请重新生成')
        items=json.loads(p['tasks']);minutes=sum(t['minutes'] for t in items)
        metadata=json.loads(p['validation'])
        remediations=metadata.get('remediations',[])
        minutes+=sum(t['minutes'] for t in remediations)
        if metadata.get('rules'):
            from app.services.planning_rules import validate
            state={'goal':g,'actor':user,'graph':metadata['graph'],'tasks':items,'remediations':remediations,
                   'execution':metadata['execution'],'sources':json.loads(p['sources']),
                   'schedule':metadata['schedule'],'preserved':metadata.get('preserved',[]),
                   'previous':one(db,'SELECT * FROM paths WHERE id=:id',id=metadata['previous']) if metadata.get('previous') else None}
            if not all(rule['passed'] for rule in validate(state,db)):fail(409,'路径规则重新审查失败，请重新生成')
        schedule=allocate(db,user['id'],minutes,g['due_date'],g['id'],g['weekly_minutes']) if minutes else []
        run(db,"UPDATE paths SET status='superseded' WHERE goal_id=:g AND status='active'",g=g['id'])
        run(db,"UPDATE reservations SET status='cancelled' WHERE goal_id=:g AND status='active'",g=g['id'])
        run(db,"UPDATE remediation_tasks SET status='cancelled' WHERE path_id IN (SELECT id FROM paths WHERE goal_id=:g AND id!=:p) AND status IN ('active','candidate')",g=g['id'],p=id)
        run(db,"UPDATE remediation_tasks SET status='active' WHERE path_id=:p AND status='candidate'",p=id)
        run(db,"UPDATE paths SET status='active' WHERE id=:id",id=id)
        for s in schedule: insert(db,'reservations',id=uid(),student_id=user['id'],source_type='path',source_id=id,goal_id=g['id'],local_date=s['date'],minutes=s['minutes'])
        run(db,"UPDATE goals SET status='active' WHERE id=:id",id=g['id']);touch(db,user['id'])
    return {'ok':True}

@router.post('/paths/{id}/reject')
def reject(id:str,user=Depends(current_user)):
    with transaction() as db:
        p=one(db,'SELECT * FROM paths WHERE id=:id AND student_id=:u',id=id,u=user['id'])
        if not p or p['status']!='pending_acceptance': fail(409,'预览不存在或已处理')
        run(db,"UPDATE paths SET status='rejected' WHERE id=:id",id=id)
        run(db,"UPDATE remediation_tasks SET status='rejected' WHERE path_id=:id AND status='candidate'",id=id)
    return {'ok':True,'message':'保留原路径，先修限制和延期风险仍然有效'}

@router.post('/check-ins')
def checkin(body:Checkin,user=Depends(current_user)):
    role(user,'student')
    with transaction() as db:
        p=one(db,"SELECT * FROM paths WHERE id=:id AND student_id=:u AND status='active'",id=body.path_id,u=user['id'])
        if not p: fail(404,'活动路径不存在')
        if goal_access(db,user,p['goal_id'])['status']=='archived': fail(409,'归档目标不能新增学习记录')
        old=one(db,'SELECT * FROM checkins WHERE path_id=:p AND item_id=:i',p=body.path_id,i=body.item_id)
        if old:
            if old['difficulty']!=body.difficulty or old['note']!=body.note:
                run(db,'UPDATE checkins SET difficulty=:d,note=:n WHERE id=:id',d=body.difficulty,n=body.note,id=old['id'])
                touch(db,user['id'])
            return {**old,'difficulty':body.difficulty,'note':body.note}
        item=next((t for t in json.loads(p['tasks'])+json.loads(p['validation']).get('remediations',[]) if t['id']==body.item_id),None)
        if not item: fail(404,'路径任务不存在')
        m=mastery(db,user['id'])
        if any(m.get(s,{}).get('probability',.2)<.75 for s in item['prerequisites']): fail(409,'先修知识尚未通过有效测验，不能开始此任务')
        id=uid();insert(db,'checkins',id=id,student_id=user['id'],**body.model_dump(),created_at=now())
        run(db,"UPDATE remediation_tasks SET status='studied' WHERE id=:id AND path_id=:p",id=body.item_id,p=p['id'])
        # Release this work's planned minutes; actual minutes are counted independently.
        remaining=round(item['minutes']*body.proportion)
        for r in rows(db,"SELECT * FROM reservations WHERE source_id=:p AND status='active' ORDER BY local_date",p=p['id']):
            release=min(remaining,r['minutes']);remaining-=release
            run(db,'UPDATE reservations SET minutes=minutes-:m WHERE id=:id',m=release,id=r['id'])
            if remaining==0: break
        touch(db,user['id'])
    return {'id':id,'message':'已记录学习；掌握度仅由有效测验证据更新'}

def assessment_item(db,user,path_id,item_id):
    p=one(db,"SELECT * FROM paths WHERE id=:id AND student_id=:u AND status='active'",id=path_id,u=user['id'])
    if not p: fail(404,'活动路径不存在')
    if goal_access(db,user,p['goal_id'])['status']=='archived':fail(409,'归档目标不能提交新测验')
    item=next((t for t in json.loads(p['tasks'])+json.loads(p['validation']).get('remediations',[]) if t['id']==item_id),None)
    if not item: fail(404,'任务不存在')
    m=mastery(db,user['id'])
    if any(m.get(s,{}).get('probability',.2)<.75 for s in item['prerequisites']): fail(409,'先修尚未达标')
    return p,item

@router.get('/paths/{id}/items/{item}/assessment')
def path_assessment(id:str,item:str,user=Depends(current_user)):
    with transaction() as db:
        p,t=assessment_item(db,user,id,item)
        # Equivalent practice variants differ from disclosed diagnosis questions.
        frozen=one(db,'SELECT questions FROM path_question_bank WHERE path_id=:p AND item_id=:i',p=id,i=item)
        qs=json.loads(frozen['questions']) if frozen else PRACTICE.get(t['skill_id'],[])
        old=one(db,'SELECT attempt_id FROM path_assessments WHERE path_id=:p AND item_id=:i',p=id,i=item)
        result=one(db,'SELECT * FROM attempts WHERE id=:id',id=old['attempt_id']) if old else None
        return {'questions':public_questions(qs),'result':result}

@router.post('/paths/{id}/items/{item}/attempts')
def path_attempt(id:str,item:str,body:Submission,user=Depends(current_user)):
    with transaction() as db:
        p,t=assessment_item(db,user,id,item)
        old=one(db,'SELECT attempt_id FROM path_assessments WHERE path_id=:p AND item_id=:i',p=id,i=item)
        if old: return one(db,'SELECT * FROM attempts WHERE id=:id',id=old['attempt_id'])
    # Read the same server-owned question version used by the assessment DTO.
    dto=path_assessment(id,item,user)
    with transaction() as db:
        frozen=one(db,'SELECT questions FROM path_question_bank WHERE path_id=:p AND item_id=:i',p=id,i=item)
        qs=json.loads(frozen['questions']) if frozen else PRACTICE.get(t['skill_id'],[])
    if not qs or any(q['id'] not in body.answers for q in qs): fail(422,'请完成测验')
    with transaction() as db:
        p,t=assessment_item(db,user,id,item)
        old=one(db,'SELECT attempt_id FROM path_assessments WHERE path_id=:p AND item_id=:i',p=id,i=item)
        if old: return one(db,'SELECT * FROM attempts WHERE id=:id',id=old['attempt_id'])
        g=goal_access(db,user,p['goal_id']);aid=uid()
        insert(db,'attempts',id=aid,student_id=user['id'],goal_id=g['id'],class_id=g['class_id'],answers=dump(body.answers),feedback='[]',status='scored',minutes=body.minutes,created_at=now())
        f,s=observations(db,aid,qs,body.answers,user['id'],g['class_id'])
        run(db,'UPDATE attempts SET feedback=:f,score=:s WHERE id=:id',f=dump(f),s=s,id=aid)
        insert(db,'path_assessments',path_id=id,item_id=item,attempt_id=aid)
        save_mastery(db,user['id'])
        return one(db,'SELECT * FROM attempts WHERE id=:id',id=aid)
