"""Graph snapshots and deterministic planning constraints."""
import json
from app.core.db import one
from app.core.security import fail
from app.services.learning import SKILLS,mastery,allocate


def graph_snapshot(db,goal_id=None):
    if goal_id:
        from app.services.engineering_goals import graph_for
        scoped=graph_for(db,goal_id)
        if scoped:return scoped
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
