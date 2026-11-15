"""Four cloud agents generate bounded proposals through existing business services."""
import json
import hashlib
import time
from langgraph.graph import StateGraph,END
from app.core.db import transaction,one,dump
from app.core.security import fail,resource_access
from app.services import planning
from app.services.learning import allocate
from app.services.planning_rules import validate


def agent_call(state,agent,payload):
    from app.api.models import call_model
    if state.get('sources'):authorized_sources(state)
    with transaction() as db:
        record=one(db,'SELECT * FROM agent_runs WHERE id=:id',id=state['run_id'])
        if record['status']!='running':fail(409,'运行已取消或中断')
        config=one(db,'SELECT * FROM model_configs WHERE id=:id',id=record['model_config_id'])
        quality=one(db,'SELECT review_status,case_count,passed_count FROM model_quality_reports WHERE model_config_id=:id ORDER BY created_at DESC LIMIT 1',id=record['model_config_id'])
        if not config or not quality or quality['review_status']!='approved' or quality['case_count']!=60 or quality['passed_count']!=60:
            fail(409,'运行绑定的模型配置需要完成质量复核','MODEL_QUALITY_REQUIRED')
    remaining=state['cloud_deadline']-time.time()
    if remaining<=0:fail(503,'四智能体运行超过180秒时限','MODEL_TIMEOUT')
    config['timeout_seconds']=min(config['timeout_seconds'],remaining)
    started=time.monotonic()
    try:
        response=call_model(config,dump({'agent':agent,'prompt_version':config['prompt_version'],'output_contract_version':'planning-v2','output_limits':{'summary_or_reason_max_chars':2000,'instructions_max_chars':4000,'string_array_max_items':20,'string_array_item_max_chars':500,'tasks_max_items':30,'citation_version_ids_max_items':8},'task':payload}))
    except Exception:
        state.setdefault('cloud_calls',[]).append({'agent':agent,'model_config_id':config['id'],'status':'failed','elapsed_ms':int((time.monotonic()-started)*1000),'usage':None})
        from app.core.db import run
        with transaction() as db:run(db,"UPDATE agent_runs SET checkpoint=:c WHERE id=:id AND status='running'",c=dump(state),id=state['run_id'])
        raise
    metadata=response.pop('_provider_meta',{})
    state.setdefault('cloud_calls',[]).append({'agent':agent,'model_config_id':config['id'],'model':config['model'],'prompt_version':config['prompt_version'],'status':'succeeded','elapsed_ms':int((time.monotonic()-started)*1000),'usage':metadata.get('usage'),'request_id':metadata.get('request_id')})
    if time.time()>state['cloud_deadline']:fail(503,'四智能体运行超过180秒时限','MODEL_TIMEOUT')
    with transaction() as db:
        current=one(db,'SELECT status FROM agent_runs WHERE id=:id',id=state['run_id'])
        if current['status']!='running':fail(409,'运行已取消或中断')
    from app.services.cloud_contracts import validate_output
    return validate_output(agent,response)


def authorized_sources(state):
    permitted=[]
    with transaction() as db:
        for source in state.get('sources',[]):
            resource=resource_access(db,state['actor'],source['resource_id'])
            if not resource['cloud_allowed']:continue
            if resource['current_version']!=source['version_id']:fail(409,'资料版本已变化')
            version=one(db,'SELECT body FROM resource_versions WHERE id=:v',v=source['version_id'])
            if not version:fail(409,'授权资料的版本已不存在')
            fragments=[]
            positions=[]
            source_remaining=2400
            for location in source.get('locations',[]):
                start,end=location.get('start'),location.get('end')
                if type(start) is not int or type(end) is not int or not 0<=start<end<=len(version['body']):
                    fail(409,'课程片段位置已失效，请重新生成规划','EVIDENCE_CHANGED')
                if source_remaining<=0:break
                fragment=version['body'][start:min(end,start+source_remaining)]
                if not fragment:continue
                fragments.append(fragment)
                positions.append({'skill':location['skill'],'start':start,'end':start+len(fragment)})
                source_remaining-=len(fragment)+3
            if not fragments:continue
            excerpt=' … '.join(fragments)
            permitted.append({'resource_id':source['resource_id'],'version_id':source['version_id'],
                              'title':resource['title'][:200],'excerpt':excerpt,'locations':positions,
                              'supported_skills':source['supported_skills'],
                              'excerpt_sha256':hashlib.sha256(excerpt.encode()).hexdigest()})
    required={item['skill_id'] for item in state.get('execution',[])}
    supported={skill for source in permitted for skill in source['supported_skills']}
    if not required<=supported:fail(409,'必要资料未授权云端发送，请调整资料授权或选择本地规划','CLOUD_PERMISSION_REQUIRED')
    # Keep at least one source for every required skill before adding optional evidence.
    selected=[]
    for skill in sorted(required):
        source=next(item for item in permitted if skill in item['supported_skills'])
        if source not in selected:selected.append(source)
    for source in permitted:
        if len(selected)>=8:break
        if source not in selected:selected.append(source)
    remaining=9000
    bounded=[]
    for source in selected:
        if len(source['excerpt'])>remaining:
            if any(skill in required and not any(skill in item['supported_skills'] for item in bounded) for skill in source['supported_skills']):
                fail(409,'课程片段超过云端发送上限，请缩小目标范围','EVIDENCE_LIMIT')
            continue
        bounded.append(source)
        remaining-=len(source['excerpt'])
    if not required<={skill for source in bounded for skill in source['supported_skills']}:
        fail(409,'课程片段超过云端发送上限，请缩小目标范围','EVIDENCE_LIMIT')
    return bounded


def diagnose(state):
    planning.diagnose(state)
    response=agent_call(state,'GoalDiagnosisAgent',{
        'goal':state['goal']['title'],'skills':json.loads(state['goal']['skills']),
        'instruction':'分析学习目标和先修要求，返回summary字符串和risks字符串数组。'})
    if not isinstance(response.get('summary'),str):fail(503,'诊断智能体缺少summary','MODEL_SCHEMA_INVALID')
    state['cloud_outputs']={'diagnosis':response}
    planning.record_cloud_step(state,'GoalDiagnosisAgent','云端分析目标与先修要求')
    return state


def build(state):
    planning.build(state)
    sources=authorized_sources(state)
    response=agent_call(state,'PathBuildingAgent',{
        'diagnosis':state['cloud_outputs']['diagnosis'],
        'required_task_count':len(state['execution']),
        'allowed_skill_ids':[task['skill_id'] for task in state['execution']],
        'excluded_mastered_or_out_of_scope_skills':[node['id'] for node in state['graph'] if node['id'] not in {task['skill_id'] for task in state['execution']}],
        'tasks':[{'skill_id':task['skill_id'],'minutes':task['minutes'],'prerequisites':task['prerequisites']} for task in state['execution']],
        'sources':sources,'previous_review':state.get('cloud_issues',[]),
        'instruction':'严格以输入tasks为唯一待学任务清单，输出tasks长度必须等于required_task_count，skill_id集合必须恰好等于allowed_skill_ids，每个技能只能有一个对象。多个阅读、练习、测评活动写在同一个instructions字符串中，不拆成多项。诊断summary仅供参考，禁止添加excluded_mastered_or_out_of_scope_skills中的技能，不重新安排已掌握的先修技能。若required_task_count为0返回空tasks。生成具体学习活动，保持全部skill_id各一次及先修顺序。返回tasks数组，每项含skill_id、正整数minutes、instructions字符串、citation_version_ids数组。只能引用所提供且支持对应技能的来源。返回reason字符串解释安排。'})
    proposed=response.get('tasks')
    expected={item['skill_id']:item for item in state['execution']}
    if not isinstance(proposed,list) or len(proposed)!=len(expected):fail(503,'路径智能体任务数量不符合要求','MODEL_SCHEMA_INVALID')
    ordered=[];seen=set()
    for entry in proposed:
        if not isinstance(entry,dict) or entry.get('skill_id') not in expected or entry['skill_id'] in seen:
            fail(503,'路径智能体返回未知或重复技能','MODEL_SCHEMA_INVALID')
        skill=entry['skill_id'];seen.add(skill)
        if type(entry.get('minutes')) is not int or not 1<=entry['minutes']<=1440 or not isinstance(entry.get('instructions'),str) or not entry['instructions'].strip():
            fail(503,'路径智能体任务内容或学时不合法','MODEL_SCHEMA_INVALID')
        citations=entry.get('citation_version_ids')
        allowed={source['version_id'] for source in sources if skill in source['supported_skills']}
        if not isinstance(citations,list) or not citations or any(not isinstance(value,str) for value in citations) or not set(citations)<=allowed:
            fail(503,'路径智能体引用未经授权或不支持该技能的来源','MODEL_CITATION_INVALID')
        item=expected[skill]
        item.update(minutes=item.get('remaining_minutes',entry['minutes']),instructions=entry['instructions'][:4000],
                    citations=[{'resource_id':source['resource_id'],'version_id':source['version_id']} for source in sources if source['version_id'] in citations])
        ordered.append(item)
    state['execution']=ordered
    order={item['skill_id']:index for index,item in enumerate(ordered)}
    state['tasks'].sort(key=lambda item:order[item['skill_id']])
    state['remediations'].sort(key=lambda item:order[item['skill_id']])
    with transaction() as db:
        schedule=allocate(db,state['actor']['id'],sum(item['minutes'] for item in ordered),state['goal']['due_date'],state['goal']['id'],state['goal']['weekly_minutes']) if ordered else []
    remaining=[item['minutes'] for item in ordered]
    for item in ordered:item['dates']=[]
    for day in schedule:
        available=day['minutes']
        for index,item in enumerate(ordered):
            amount=min(available,remaining[index])
            if amount:item['dates'].append({'date':day['date'],'minutes':amount})
            available-=amount;remaining[index]-=amount
    state['schedule']=schedule;state['diff']['after_schedule']=schedule
    state['cloud_outputs']['path']={'reason':str(response.get('reason',''))[:2000]}
    planning.record_cloud_step(state,'PathBuildingAgent','云端生成活动、学时与授权引用，经业务服务重新排期')
    return state


def review(state):
    with transaction() as db:state['rules']=validate(state,db)
    response=agent_call(state,'PlanReviewAgent',{
        'tasks':state['execution'],'rules':state['rules'],'sources':authorized_sources(state),
        'instruction':'审查教学顺序、具体活动与评估目标是否一致，并逐项对照sources的授权片段判断引用是否支持活动。若引入材料未覆盖的知识、外部资源或结论，必须拒绝并在issues列出具体技能和不受支持的内容。返回approved布尔值和issues字符串数组。硬规则失败必须拒绝。approved为true时issues必须为空。'})
    if type(response.get('approved')) is not bool or not isinstance(response.get('issues'),list):
        fail(503,'审查智能体输出不合法','MODEL_SCHEMA_INVALID')
    issues=[rule['reason'] for rule in state['rules'] if not rule['passed']]
    issues.extend(str(value)[:500] for value in response['issues'][:20])
    state['cloud_issues']=issues
    state['cloud_approved']=response['approved'] and all(rule['passed'] for rule in state['rules'])
    state['cloud_outputs']['review']=response
    state['cloud_repairs']=state.get('cloud_repairs',0)+(0 if state['cloud_approved'] else 1)
    if not state['cloud_approved'] and state['cloud_repairs']>3:
        fail(409,'路径在三次修复后仍未通过审查','PATH_REPAIR_EXHAUSTED')
    planning.record_cloud_step(state,'PlanReviewAgent','完成云端教学审查及确定性硬规则校验')
    return state


def finalize(state):
    authorized_sources(state)
    response=agent_call(state,'LearningReplanAgent',{
        'mode':state['mode'],'triggers':state['triggers'],'diff':state['diff'],
        'instruction':'解释当前计划或重规划的调整原因、风险和后续学习建议，返回reason字符串与recommendations字符串数组。不得改写已完成历史。'})
    if not isinstance(response.get('reason'),str):fail(503,'重规划智能体缺少原因解释','MODEL_SCHEMA_INVALID')
    state['cloud_outputs']['replan']=response
    return planning.save(state)


graph=StateGraph(planning.State)
for name,node in [('diagnose',diagnose),('build',build),('review',review),('save',finalize)]:graph.add_node(name,node)
graph.set_entry_point('diagnose')
graph.add_edge('diagnose','build');graph.add_edge('build','review')
graph.add_conditional_edges('review',lambda state:'save' if state['cloud_approved'] else 'build',{'save':'save','build':'build'})
graph.add_edge('save',END)
workflow=graph.compile()

