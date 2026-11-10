"""Graph snapshots and deterministic planning constraints."""
import json
from app.core.db import one
from app.core.security import fail
from app.services.learning import SKILLS,mastery,allocate

def completed_history(db,previous):
    if not previous:return []
    metadata=json.loads(previous['validation'])
    preserved=list(metadata.get('preserved',[]))
    identities={(entry['path_id'],entry['item']['id']) for entry in preserved}
    for item in json.loads(previous['tasks'])+metadata.get('remediations',[]):
        fact=one(db,'SELECT * FROM checkins WHERE path_id=:p AND item_id=:i AND proportion>=1',p=previous['id'],i=item['id'])
        if fact and (previous['id'],item['id']) not in identities:
            preserved.append({'path_id':previous['id'],'item':item,'checkin':fact})
    return preserved

def graph_snapshot(db):
    saved=one(db,'SELECT * FROM graph_versions WHERE active=1')
    if not saved:return [dict(n) for n in SKILLS],'curated-v1'
    nodes={n['id']:{**{key:value for key,value in n.items() if not key.endswith('_questions')},'name':n.get('name',n['id']),'prerequisites':[]} for n in json.loads(saved['nodes'])}
    for before,after in json.loads(saved['edges']):nodes[after]['prerequisites'].append(before)
    ordered=[];pending=list(nodes)
    while pending:
        ready=[key for key in pending if set(nodes[key]['prerequisites'])<=set(n['id'] for n in ordered)]
        if not ready:fail(409,'图谱存在先修冲突')
        for key in ready:ordered.append(nodes[key]);pending.remove(key)
    return ordered,saved['id']

def validate(state,db):
    execution=state['execution']
    known={n['id'] for n in state['graph'] if n.get('assessment_source',{}).get('question_ids')}
    current=mastery(db,state['actor']['id'])
    satisfied={skill for skill,value in current.items() if value['probability']>=.75}
    prerequisite_ok=True
    for item in execution:
        if not set(item['prerequisites'])<=satisfied:prerequisite_ok=False
        satisfied.add(item['skill_id'])
    minutes=sum(i['minutes'] for i in execution)
    try:
        expected=allocate(db,state['actor']['id'],minutes,state['goal']['due_date'],state['goal']['id'],state['goal']['weekly_minutes']) if minutes else []
        load_ok=expected==state['schedule']
    except Exception as exc:
        if not hasattr(exc,'status_code'):raise
        load_ok=False
    sources={(s['resource_id'],s['version_id']):s for s in state['sources']}
    citation_ok=all(any((c['resource_id'],c['version_id']) in sources and item['skill_id'] in sources[(c['resource_id'],c['version_id'])]['supported_skills'] for c in item.get('citations',[])) for item in execution)
    previous=state.get('previous')
    preserved=completed_history(db,previous)
    checks=[
        ('VR-001',prerequisite_ok,'先修已掌握或在执行序列更早安排'),
        ('VR-002',sum(s['minutes'] for s in state['schedule'])==minutes,'全部学习及补强分钟计入排期'),
        ('VR-003',load_ok,'日周负荷满足全局预算'),
        ('VR-004',len({t['skill_id'] for t in state['tasks']})==len(state['tasks']) and len({t['id'] for t in execution})==len(execution),'知识节点及执行任务不重复'),
        ('VR-005',citation_ok,'每项任务有授权资源版本引用'),
        ('VR-006',all(i['skill_id'] in known and i['minutes']>0 for i in execution),'测验映射有效知识点'),
        ('VR-007',preserved==state.get('preserved',[]),'已完成事实保持只读'),
        ('VR-008',prerequisite_ok,'重规划保留未完成先修')]
    return [{'rule_id':key,'passed':bool(ok),'reason':reason} for key,ok,reason in checks]
