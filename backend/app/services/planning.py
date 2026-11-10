"""A four-node LangGraph pipeline; local planning is explicitly deterministic."""
import json,re
from typing import TypedDict
from fastapi import HTTPException
from langgraph.graph import StateGraph,END
from app.core.db import *
from app.core.security import fail,class_access
from app.services.learning import SKILLS,mastery,allocate,fingerprint
from app.services.planning_rules import graph_snapshot,validate,completed_history

class State(TypedDict,total=False):
    run_id:str
    goal:dict
    actor:dict
    tasks:list
    sources:list
    schedule:list
    fingerprint:str
    path_id:str
    graph:list
    graph_version:str
    previous:dict
    mode:str
    triggers:list
    remediations:list
    preserved:list
    execution:list
    diff:dict
    rules:list
    budget_snapshot:dict
    cloud_calls:list
    cloud_mode:bool
    cloud_deadline:float
    cloud_outputs:dict
    cloud_issues:list
    cloud_approved:bool
    cloud_repairs:int
    last_agent:str

def record_step(db,state,agent,detail):
    record=one(db,'SELECT status,retry_count FROM agent_runs WHERE id=:id',id=state['run_id'])
    if not record or record['status']=='cancelled':fail(409,'运行已取消')
    state['last_agent']=agent
    output={'task_ids':[t['id'] for t in state.get('tasks',[])],
            'source_versions':[s['version_id'] for s in state.get('sources',[])],
            'scope':state.get('mode'),'rules':state.get('rules',[])}
    output['model_calls']=[call for call in state.get('cloud_calls',[]) if call['agent']==agent]
    output['tools']={'GoalDiagnosisAgent':['goal.read','diagnosis.read','graph.snapshot','mastery.read'],
                     'PathBuildingAgent':['resources.authorized','budget.allocate'],
                     'PlanReviewAgent':['rules.validate'],
                     'LearningReplanAgent':['paths.persist','remediation.persist']}[agent]
    insert(db,'agent_steps',id=uid(),run_id=state['run_id'],agent=agent,status='succeeded',detail=detail,created_at=now(),
           input_fingerprint=state.get('fingerprint','{}'),output_summary=dump(output),attempt_no=record['retry_count'])
    run(db,'UPDATE agent_runs SET checkpoint=:c WHERE id=:id',c=dump(state),id=state['run_id'])

def record_cloud_step(state,agent,detail):
    with transaction() as db:record_step(db,state,agent,detail)

def step(state,agent,detail):
    if state.get('cloud_mode'):return
    with transaction() as db:record_step(db,state,agent,detail)

def diagnose(state):
    with transaction() as db:
        r=one(db,'SELECT * FROM agent_runs WHERE id=:id',id=state['run_id'])
        g=one(db,'SELECT * FROM goals WHERE id=:id',id=r['goal_id']);u=one(db,'SELECT id,name,username,role,status FROM users WHERE id=:id',id=r['actor_id'])
        if not g or g['status']=='archived' or u['status']!='active': fail(409,'目标不可用')
        if g['class_id'] and class_access(db,u,g['class_id'])['status']!='active':fail(409,'关联班级已归档')
        skills=json.loads(g['skills'])
        available_graph,_=graph_snapshot(db)
        if not skills or not set(skills)<=set(s['id'] for s in available_graph): fail(409,'新主题缺少已验证图谱、题库和来源；当前只支持本地函数/递归主题','COVERAGE_GAP')
        diagnosis=one(db,'SELECT * FROM diagnoses WHERE goal_id=:g AND goal_version=:v AND attempt_id IS NOT NULL ORDER BY created_at DESC LIMIT 1',g=g['id'],v=g['version'])
        if not diagnosis:fail(409,'请先提交诊断')
        graph,version=graph_snapshot(db)
        questions=json.loads(diagnosis['questions'])
        graph=[{**node,'assessment_source':{'bank_version':diagnosis['bank_version'],
                'question_ids':[q['id'] for q in questions if q['skill']==node['id']]}} for node in graph]
        previous=one(db,"SELECT * FROM paths WHERE goal_id=:g AND status='active'",g=g['id'])
        budget=one(db,'SELECT * FROM budgets WHERE user_id=:u',u=u['id'])
        mode='initial';triggers=[]
        if r['kind']=='replan':
            mode='local'
            current=mastery(db,u['id'])
            if any(current.get(skill,{}).get('probability',.2)<.45 for skill in skills):triggers.append('掌握薄弱')
            overdue=rows(db,"SELECT a.id FROM assignments a JOIN tasks t ON t.id=a.task_id WHERE a.student_id=:u AND a.status NOT IN ('completed','cancelled') AND t.status='published' AND t.due_at<:time ORDER BY t.due_at",u=u['id'],time=now())
            if len(overdue)>=2:triggers.append('连续至少两个任务到期未完成')
            old=json.loads(previous['validation']) if previous else {}
            before=old.get('budget_snapshot',budget)
            change=max(abs(budget[k]-before[k])/max(before[k],1) for k in ('daily_minutes','weekly_minutes'))
            if change:triggers.append('全局预算变化')
            if change>.30:mode='global'
            if previous and old.get('graph_version','curated-v1')!=version:
                mode='global';triggers.append('图谱版本变化')
            if previous and set(json.loads(old.get('goal_snapshot',g)['skills']))!=set(skills):
                mode='global';triggers.append('目标范围变化')
            if not previous:mode='global'
            if previous and json.loads(previous['fingerprint']).get('goal')!=g['version']:triggers.append('目标版本变化')
            for source in json.loads(previous['sources']) if previous else []:
                resource=one(db,'SELECT current_version,status FROM resources WHERE id=:id',id=source['resource_id'])
                if not resource or resource['current_version']!=source['version_id'] or resource['status']!='published':
                    triggers.append('来源证据变化');break
            if not triggers:triggers.append('学生主动评估')
        state.update(goal=g,actor=u,fingerprint=fingerprint(db,u['id'],g['id']),graph=graph,graph_version=version,
                     previous=previous,budget_snapshot=budget,mode=mode,triggers=triggers)
    step(state,'GoalDiagnosisAgent','读取已提交诊断和已确认技能；未调用云端模型')
    return state

def build(state):
    from app.api.resources import visible
    from app.services.topic_bank import keywords
    tokens=keywords(state['graph'])
    with transaction() as db:
        g=state['goal'];u=state['actor'];m=mastery(db,u['id'])
        target=set(json.loads(g['skills']))
        for node in reversed(state['graph']):
            if node['id'] in target:target.update(node['prerequisites'])
        sources=[]
        for resource in visible(db,u):
            if resource['status']!='published' and resource['scope']!='private':continue
            version=one(db,"SELECT * FROM resource_versions WHERE id=:id AND parse_status='ready' AND index_status='indexed'",id=resource['current_version'])
            if not version:continue
            supported=[skill for skill in target if any(t.lower() in version['body'].lower() for t in tokens[skill])]
            if supported:
                locations=[];fragments=[]
                for skill in supported:
                    matches=[match for token in tokens[skill] if (match:=re.search(re.escape(token),version['body'],re.IGNORECASE))]
                    start=max(0,min(match.start() for match in matches)-80)
                    end=min(len(version['body']),start+300)
                    locations.append({'skill':skill,'start':start,'end':end})
                    fragments.append(version['body'][start:end])
                sources.append({'resource_id':resource['id'],'version_id':version['id'],'title':resource['title'],
                    'location':'正文字符 '+','.join(str(p['start'])+'-'+str(p['end']) for p in locations),
                    'excerpt':' … '.join(fragments),'locations':locations,
                    'supported_skills':supported,'cloud_allowed':bool(resource['cloud_allowed'])})
        gaps=target-{skill for source in sources for skill in source['supported_skills']}
        if gaps:fail(409,'授权正文覆盖不足：'+','.join(sorted(gaps))+'；请补充资料','EVIDENCE_GAP')
        previous=state.get('previous')
        old={t['skill_id']:t for t in json.loads(previous['tasks'])} if previous else {}
        preserved=completed_history(db,previous)
        completed={entry['item']['skill_id']:entry['item'] for entry in preserved}
        tasks=[];remediations=[];execution=[]
        for node in state['graph']:
            skill=node['id']
            if skill not in target or m.get(skill,{}).get('probability',.2)>=.75:continue
            item={**node,'skill_id':skill,'id':old.get(skill,{}).get('id',uid()) if state['mode']=='local' else uid(),
                  'assessment':'完成相关知识测验，达到0.75解锁后续学习',
                  'reinforcement':m.get(skill,{}).get('probability',.2)<.45,
                  'citations':[{'resource_id':s['resource_id'],'version_id':s['version_id']} for s in sources if skill in s['supported_skills']]}
            if skill in completed:
                item.update(id=uid(),kind='remediation',source_item_id=completed[skill]['id'])
                remediations.append(item)
            else:tasks.append(item)
            execution.append(item)
        minutes=sum(item['minutes'] for item in execution)
        try:
            schedule=allocate(db,u['id'],minutes,g['due_date'],g['id'],g['weekly_minutes']) if minutes else []
        except Exception as exc:
            if state['mode']!='local' or not hasattr(exc,'status_code') or exc.status_code!=409:raise
            state['mode']='global'
            state['triggers'].append('局部排期不可行，改为全局重排')
            import math
            for item in execution:
                previous_item=old.get(item['skill_id'])
                if not previous_item:continue
                partial=one(db,'SELECT proportion FROM checkins WHERE path_id=:p AND item_id=:i',p=previous['id'],i=previous_item['id'])
                if partial and 0<partial['proportion']<1:
                    item['minutes']=max(1,math.ceil(item['minutes']*(1-partial['proportion'])))
            minutes=sum(item['minutes'] for item in execution)
            schedule=allocate(db,u['id'],minutes,g['due_date'],g['id'],g['weekly_minutes']) if minutes else []
        pending=[{'item':item,'remaining':item['minutes']} for item in execution]
        for item in execution:item['dates']=[]
        for day in schedule:
            available=day['minutes']
            for planned in pending:
                amount=min(available,planned['remaining'])
                if amount:planned['item']['dates'].append({'date':day['date'],'minutes':amount})
                planned['remaining']-=amount;available-=amount
                if not available:break
        diff={'added':sorted({t['skill_id'] for t in tasks}-set(old)),
              'removed':sorted(set(old)-{t['skill_id'] for t in tasks}),
              'kept':sorted(set(old)&{t['skill_id'] for t in tasks}),
              'reinforced':[t['skill_id'] for t in remediations],
              'before_schedule':json.loads(previous['validation']).get('schedule',[]) if previous else [],
              'after_schedule':schedule,'scope':state['mode'],'risks':state['triggers']}
        state.update(tasks=tasks,sources=sources,schedule=schedule,remediations=remediations,
                     preserved=preserved,execution=execution,diff=diff)
    step(state,'PathBuildingAgent','按先修与掌握度构造学习及独立补强任务，核算全局预算')
    return state

def review(state):
    with transaction() as db:state['rules']=validate(state,db)
    if not all(rule['passed'] for rule in state['rules']):
        raise HTTPException(409,{'code':'PATH_RULE_FAILED','message':'路径硬规则未通过：'+','.join(rule['rule_id'] for rule in state['rules'] if not rule['passed']),'rules':state['rules']})
    step(state,'PlanReviewAgent','逐条通过VR-001至VR-008')
    return state

def save(state):
    with transaction() as db:
        r=one(db,'SELECT * FROM agent_runs WHERE id=:id',id=state['run_id'])
        if r['status']=='cancelled': fail(409,'运行已取消')
        if fingerprint(db,state['actor']['id'],state['goal']['id'])!=state['fingerprint']: fail(409,'生成过程中输入已变化，请重试')
        pid=uid()
        validation={key:state[key] for key in ('graph','graph_version','rules','remediations','preserved','execution','diff','mode','triggers','budget_snapshot')}
        validation.update(is_valid=True,schedule=state['schedule'],method='cloud-four-agent-v1' if state.get('cloud_mode') else 'local-deterministic-v2',cloud_called=bool(state.get('cloud_mode')),cloud_outputs=state.get('cloud_outputs',{}),model_config_id=r['model_config_id'],
                          previous=state['previous']['id'] if state.get('previous') else None,goal_snapshot=state['goal'])
        insert(db,'paths',id=pid,goal_id=state['goal']['id'],student_id=state['actor']['id'],status='pending_acceptance',
               content_status='verified',tasks=dump(state['tasks']),sources=dump(state['sources']),validation=dump(validation),
               fingerprint=state['fingerprint'],reason='依据诊断、图谱和全局预算生成，范围 '+state['mode'],created_at=now())
        from app.services.topic_bank import question_bank
        bank,_=question_bank(db,'practice',state['graph_version'] if state['graph_version']!='curated-v1' else None)
        for item in state['execution']:
            insert(db,'path_question_bank',path_id=pid,item_id=item['id'],questions=dump([question for question in bank if question['skill']==item['skill_id']]))
        for item in state['remediations']:
            insert(db,'remediation_tasks',id=item['id'],path_id=pid,skill=item['skill_id'],source_item_id=item['source_item_id'],
                   status='candidate',minutes=item['minutes'],created_at=now())
        state['path_id']=pid
        record_step(db,state,'LearningReplanAgent','云端解释调整原因，保存待接受路径及独立补强候选' if state.get('cloud_mode') else '保存待接受路径及独立补强候选')
        run(db,"UPDATE agent_runs SET status='succeeded',result_id=:p,finished_at=:t WHERE id=:id",p=pid,t=now(),id=state['run_id'])
    return state

graph=StateGraph(State)
for name,fn in [('diagnose',diagnose),('build',build),('review',review),('save',save)]: graph.add_node(name,fn)
graph.set_conditional_entry_point(lambda state:{'GoalDiagnosisAgent':'build','PathBuildingAgent':'review','PlanReviewAgent':'save'}.get(state.get('last_agent'),'diagnose'),{'diagnose':'diagnose','build':'build','review':'review','save':'save'});graph.add_edge('diagnose','build');graph.add_edge('build','review');graph.add_edge('review','save');graph.add_edge('save',END)
workflow=graph.compile()

def execute(run_id):
    try:
        with transaction() as db:
            claimed=run(db,"UPDATE agent_runs SET status='running',finished_at=NULL WHERE id=:id AND status='queued'",id=run_id)
            if claimed.rowcount!=1:return
            record=one(db,'SELECT * FROM agent_runs WHERE id=:id',id=run_id)
            state=json.loads(record['checkpoint'])
            if state.get('fingerprint')!=fingerprint(db,record['actor_id'],record['goal_id']):state={}
            state['run_id']=run_id
        if record['execution_mode']=='cloud':
            import time
            from app.services.cloud_planning import workflow as cloud_workflow
            state.update(cloud_mode=True,cloud_deadline=time.time()+180,cloud_repairs=0,cloud_calls=[])
            cloud_workflow.invoke(state,{'recursion_limit':20})
        else:
            workflow.invoke(state)
    except Exception as exc:
        message=exc.detail.get('message') if hasattr(exc,'detail') and isinstance(exc.detail,dict) else '规划执行失败，请检查日志与输入'
        with transaction() as db:
            record=one(db,'SELECT * FROM agent_runs WHERE id=:id',id=run_id)
            if record and record['status'] not in ('cancelled','succeeded'):
                checkpoint=json.loads(record['checkpoint'])
                phase={'GoalDiagnosisAgent':'PathBuildingAgent','PathBuildingAgent':'PlanReviewAgent','PlanReviewAgent':'LearningReplanAgent'}.get(checkpoint.get('last_agent'),'GoalDiagnosisAgent')
                insert(db,'agent_steps',id=uid(),run_id=run_id,agent=phase,status='failed',detail=message,
                       created_at=now(),input_fingerprint=checkpoint.get('fingerprint','{}'),
                       output_summary=dump({'error':message,'rules':exc.detail.get('rules',[]) if hasattr(exc,'detail') and isinstance(exc.detail,dict) else []}),attempt_no=record['retry_count'])
            run(db,"UPDATE agent_runs SET status='failed',error=:e,finished_at=:t WHERE id=:id AND status NOT IN ('cancelled','succeeded')",e=message,t=now(),id=run_id)
