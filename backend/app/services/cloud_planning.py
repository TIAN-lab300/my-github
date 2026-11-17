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
        from app.services.quality_policy import activation_state
        if not config or not activation_state(db,config)['allowed']:
            fail(409,'运行绑定模型尚未通过当前teaching-v4质量评价与复核','MODEL_QUALITY_REQUIRED')
    remaining=state['cloud_deadline']-time.time()
    if remaining<=0:fail(503,'四智能体运行超过180秒时限','MODEL_TIMEOUT')
    config['timeout_seconds']=min(config['timeout_seconds'],remaining)
    started=time.monotonic()
    try:
        response=call_model(config,dump({'agent':agent,'prompt_version':config['prompt_version'],'output_contract_version':'planning-v4','output_limits':{'summary_or_reason_max_chars':2000,'instructions_max_chars':4000,'string_array_max_items':20,'string_array_item_max_chars':500,'tasks_max_items':30,'citation_version_ids_max_items':8},'task':payload}))
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
    permitted=[];blocked=[]
    with transaction() as db:
        for source in state.get('sources',[]):
            resource=resource_access(db,state['actor'],source['resource_id'])
            if not resource['cloud_allowed']:
                blocked.append({'title':resource['title'],'skills':source['supported_skills']})
                continue
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
    if not required<=supported:
        missing=required-supported
        names={item['id']:item.get('name',item['id']) for item in state.get('graph',[])}
        skills='、'.join(names.get(skill,skill) for skill in sorted(missing))
        titles='、'.join(dict.fromkeys(item['title'] for item in blocked if missing.intersection(item['skills'])))
        fail(409,'以下知识点缺少已授权云端发送的正文：'+skills+'。'+('相关资料：'+titles+'。' if titles else '')+'请由资料所有者或管理员进入课程知识库→编辑资料信息，勾选“允许必要正文发送云端”并保存，然后重新生成；也可选择本地规则规划。','CLOUD_PERMISSION_REQUIRED')
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
        'learner_evidence':state['learner_evidence'],'budget':state['budget_snapshot'],
        'instruction':'根据learner_evidence中已评分的诊断与当前掌握度分析目标和先修要求，区分首次诊断与后续变化。unknown表示缺少证据，不是已证实薄弱。学习时长不等于掌握度，不得推测未测技能、改写分数或BKT概率。返回summary字符串和risks字符串数组。'})
    if not isinstance(response.get('summary'),str):fail(503,'诊断智能体缺少summary','MODEL_SCHEMA_INVALID')
    state['cloud_outputs']={'diagnosis':response}
    planning.record_cloud_step(state,'GoalDiagnosisAgent','云端分析目标与先修要求')
    return state


def build(state):
    state['cloud_round']=state.get('cloud_repairs',0)+1
    planning.build(state)
    sources=authorized_sources(state)
    response=agent_call(state,'PathBuildingAgent',{
        'diagnosis':state['cloud_outputs']['diagnosis'],
        'learner_evidence':state['learner_evidence'],
        'required_task_count':len(state['execution']),
        'allowed_skill_ids':[task['skill_id'] for task in state['execution']],
        'excluded_mastered_or_out_of_scope_skills':[node['id'] for node in state['graph'] if node['id'] not in {task['skill_id'] for task in state['execution']}],
        'tasks':[{'skill_id':task['skill_id'],'minutes':task['minutes'],'prerequisites':task['prerequisites'],'kind':task.get('kind','learning'),'teaching_packet':{k:v for k,v in task.get('teaching_packet',{}).items() if k!='reading'}} for task in state['execution']],
        'sources':sources,'previous_review':state.get('cloud_issues',[]),'repair_findings':state.get('review_findings',[]),
        'instruction':'只可修复instructions和citation_version_ids，不可改写teaching_packet、题库、分数、先修、任务范围和业务时长；若review_findings指出固定材料或服务端证据问题，不可用文字回避。严格以输入tasks为唯一待学任务清单，输出tasks长度必须等于required_task_count，skill_id集合必须恰好等于allowed_skill_ids，每个技能只能有一个对象。多个阅读、练习、测评活动写在同一个instructions字符串中，不拆成多项。诊断summary仅供参考，禁止添加excluded_mastered_or_out_of_scope_skills中的技能，不自行添加已掌握先修；输入kind=review是用户明确要求的已达标复习，必须保留并标明复习，不得称为薄弱补强。若required_task_count为0返回空tasks。生成具体学习活动，保持全部skill_id各一次及先修顺序。返回tasks数组，每项含skill_id、正整数minutes、instructions字符串、citation_version_ids数组。只能引用所提供且支持对应技能的来源。teaching_packet给出了真实可用新题数和明确的原创示例，只能按它安排，不声称未提供的题/图已存在。测验每次仅领取1道题；无新题时明确测验待补齐，不编造题目。复习必须说明已达标，不称薄弱。时长由业务估计保留，不为了用满预算而延长；模型分钟仅作建议。调用栈公共示例若使用完整追踪，应为6事件、含初始态7快照，普通函数示例只跟踪给定代码的定义、参数和返回值，不添加方程反推。返回reason字符串解释安排。'})
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
        item.update(minutes=item['minutes'],proposed_minutes=entry['minutes'],instructions=entry['instructions'][:4000],
                    citations=[{'resource_id':source['resource_id'],'version_id':source['version_id']} for source in sources if source['version_id'] in citations])
        ordered.append(item)
    from app.services.teaching_packets import model_claim_issues
    state['cloud_semantic_issues']=[issue for item in ordered for issue in model_claim_issues(item)]
    state['execution']=ordered
    order={item['skill_id']:index for index,item in enumerate(ordered)}
    state['tasks'].sort(key=lambda item:order[item['skill_id']])
    state['remediations'].sort(key=lambda item:order[item['skill_id']])
    with transaction() as db:
        schedule=allocate(db,state['actor']['id'],sum(item['minutes'] for item in ordered),state['goal']['due_date'],state['goal']['id'],state['goal']['weekly_minutes'],pace=state.get('planning_options',{}).get('pace','early')) if ordered else []
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
    permitted=authorized_sources(state)
    allowed_versions={s['version_id'] for s in permitted}
    import copy
    model_tasks=copy.deepcopy(state['execution'])
    for task in model_tasks:
        task.pop('assessment_source',None) # Initial diagnostic IDs are not practice-question identities.
        packet=task.get('teaching_packet',{})
        if packet.get('reading'):
            packet['reading']['sources']=[s for s in packet['reading']['sources'] if s['version_id'] in allowed_versions]
    from app.services.planning_review import server_facts,findings,REVIEW_INSTRUCTION
    with transaction() as db:
        state['rules']=validate(state,db)
        facts=server_facts(db,state)
    response=agent_call(state,'PlanReviewAgent',{
        'server_verified':facts,'tasks':model_tasks,'teaching_warnings':state.get('teaching_warnings',[]),'rules':state['rules'],'sources':authorized_sources(state),
        'learner_evidence':state['learner_evidence'],
        'instruction':REVIEW_INSTRUCTION})
    if type(response.get('approved')) is not bool or not isinstance(response.get('issues'),list):
        fail(503,'审查智能体输出不合法','MODEL_SCHEMA_INVALID')
    state['review_findings']=findings(response,{item['skill_id'] for item in state['execution']})
    issues=[rule['reason'] for rule in state['rules'] if not rule['passed']]
    issues.extend(str(value)[:500] for value in response['issues'][:20])
    issues.extend(state.get('cloud_semantic_issues',[]))
    state['cloud_issues']=issues
    state['cloud_approved']=response['approved'] and not issues
    state['cloud_outputs']['review']={**response,'evidence_contract':facts['contract'],'server_verified':facts,'model_approved':response['approved'],'approved':state['cloud_approved'],'issues':issues}
    state['cloud_repairs']=state.get('cloud_repairs',0)+(0 if state['cloud_approved'] else 1)
    blocked=any(item['field'] in ('fixed_material','server_evidence') for item in state['review_findings']) or any(not rule['passed'] for rule in state['rules'])
    decision='通过' if state['cloud_approved'] else '阻断，需修正固定材料或服务端证据' if blocked else '未通过，退回描述或引用修复'
    planning.record_cloud_step(state,'PlanReviewAgent','第'+str(state.get('cloud_round',1))+'轮教学审查：'+decision)
    if blocked:fail(409,'审查发现固定材料或服务端证据问题，已停止文字重试：'+'；'.join(issues),'PATH_MATERIAL_REVIEW_REQUIRED')
    if not state['cloud_approved'] and state['cloud_repairs']>3:
        fail(409,'路径在三次修复后仍未通过审查','PATH_REPAIR_EXHAUSTED')
    return state


def finalize(state):
    authorized_sources(state)
    response=agent_call(state,'LearningReplanAgent',{
        'mode':state['mode'],'triggers':state['triggers'],'diff':state['diff'],
        'learner_evidence':state['learner_evidence'],
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

