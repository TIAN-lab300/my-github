"""Versioned edit operations and administrator-owned knowledge graph registry."""
import json
from datetime import datetime,timezone
from pydantic import ValidationError
from fastapi import APIRouter,Depends
from app.core.db import *
from app.core.security import *
from app.schemas import TaskInput
from app.api.tasks import task_dto,validate_questions

router=APIRouter()

@router.patch('/resources/{id}')
def resource_edit(id:str,body:dict,user=Depends(current_user)):
    with transaction() as db:
        r=resource_access(db,user,id,True)
        if body.get('version')!=r['version']: fail(409,'资料版本已变化')
        title=str(body.get('title',r['title'])).strip()
        if not title or len(title)>200: fail(422,'标题需为1至200字')
        if 'cloud_allowed' in body and not isinstance(body['cloud_allowed'],bool): fail(422,'云端授权必须为布尔值')
        for field,limit in [('description',3000),('tags',500),('source_license',1000)]:
            value=body.get(field,r[field])
            if not isinstance(value,str) or not value.strip() or len(value)>limit: fail(422,'说明、标签和来源权限不能为空或超长')
        run(db,'UPDATE resources SET title=:t,description=:d,tags=:tags,source_license=:l,cloud_allowed=:cloud,version=version+1 WHERE id=:id',t=title,d=str(body.get('description',r['description']))[:3000],tags=str(body.get('tags',r['tags']))[:500],l=str(body.get('source_license',r['source_license']))[:1000],cloud=int(bool(body.get('cloud_allowed',r['cloud_allowed']))),id=id)
        audit(db,user['id'],'resource_metadata_updated',id)
    return {'ok':True}

@router.get('/teacher/tasks/{id}')
def task_detail(id:str,user=Depends(current_user)):
    role(user,'teacher')
    with transaction() as db:
        t=one(db,'SELECT * FROM tasks WHERE id=:id AND owner_id=:u',id=id,u=user['id'])
        if not t: fail(404,'任务不存在')
        return task_dto(t,True)

@router.patch('/teacher/tasks/{id}')
def task_edit(id:str,body:dict,user=Depends(current_user)):
    role(user,'teacher')
    with transaction() as db:
        t=one(db,'SELECT * FROM tasks WHERE id=:id AND owner_id=:u',id=id,u=user['id'])
        if not t: fail(404,'任务不存在')
        class_access(db,user,t['class_id'],True)
        if t['status']!='draft' or body.get('version')!=t['version']: fail(409,'仅可修改最新版本草稿，已发布任务需撤回后重发')
        if set(body)-{'version','title','description','minutes','due_at','questions','recipients','code_cases'}:
            fail(422,'仅允许编辑标题、说明、时长、截止、题目和接收人')
        merged=task_dto(t,True);merged.update(body)
        try: validated=TaskInput(**merged)
        except ValidationError: fail(422,'任务字段不合法，请检查标题、时间、题目和接收人')
        if validated.class_id!=t['class_id']: fail(422,'草稿不能变更所属班级')
        try: due=datetime.fromisoformat(validated.due_at)
        except ValueError: fail(422,'截止时间不合法')
        if due.tzinfo is None or due<=datetime.now(timezone.utc): fail(422,'截止时间必须包含时区且晚于当前时间')
        if validated.mode=='code' and not validated.code_cases:fail(422,'代码任务至少需要一个测试用例')
        if validated.mode=='quiz' and not validated.questions: fail(422,'测验至少需要一道题')
        if len({q.id for q in validated.questions})!=len(validated.questions): fail(422,'题目编号不能重复')
        validate_questions([q.model_dump() for q in validated.questions])
        members={m['user_id'] for m in rows(db,"SELECT user_id FROM memberships WHERE class_id=:c AND status='active'",c=t['class_id'])}
        if not set(validated.recipients)<=members: fail(422,'接收人必须是本班有效成员')
        if validated.resource_id:
            resource=resource_access(db,user,validated.resource_id)
            if resource['class_id']!=t['class_id'] or resource['status']!='published': fail(422,'只能关联本班已发布资料')
        run(db,'UPDATE tasks SET title=:title,description=:description,minutes=:minutes,due_at=:due_at,questions=:questions,recipients=:recipients,code_cases=:code_cases,version=version+1 WHERE id=:id',id=id,title=validated.title,description=validated.description,minutes=validated.minutes,due_at=validated.due_at,questions=dump([q.model_dump() for q in validated.questions]),recipients=dump(validated.recipients),code_cases=dump([case.model_dump() for case in validated.code_cases]))
        audit(db,user['id'],'task_draft_updated',id)
    return {'ok':True}

@router.get('/admin/graphs')
def graphs(user=Depends(current_user)):
    role(user,'admin')
    with transaction() as db: return rows(db,'SELECT * FROM graph_versions ORDER BY created_at DESC LIMIT 50')

@router.post('/admin/graphs',status_code=201)
def graph_create(body:dict,user=Depends(current_user)):
    role(user,'admin')
    nodes=body.get('nodes',[]);edges=body.get('edges',[])
    if not isinstance(nodes,list) or not nodes or len(nodes)>500 or not isinstance(edges,list) or len(edges)>5000: fail(422,'图谱规模或结构不合法')
    if any(not isinstance(n,dict) for n in nodes): fail(422,'图谱节点必须为对象')
    ids=[n.get('id') for n in nodes]
    if not all(isinstance(x,str) and x for x in ids) or len(set(ids))!=len(ids): fail(422,'节点ID必须非空且唯一')
    adjacency={id:[] for id in ids};degree={id:0 for id in ids}
    for n in nodes:
        if 'name' in n and (not isinstance(n['name'],str) or not n['name'].strip() or len(n['name'])>200):fail(422,'节点名称须为1至200字')
        if type(n.get('minutes')) is not int or n['minutes']<=0: fail(422,'所有节点需有正整数预计分钟')
    for e in edges:
        if not isinstance(e,list) or len(e)!=2 or not all(isinstance(x,str) for x in e) or e[0] not in degree or e[1] not in degree: fail(422,'先修边必须引用现存节点')
        adjacency[e[0]].append(e[1]);degree[e[1]]+=1
    queue=[id for id in ids if degree[id]==0];order=[]
    while queue:
        id=queue.pop(0);order.append(id)
        for nxt in adjacency[id]:
            degree[nxt]-=1
            if degree[nxt]==0: queue.append(nxt)
    if len(order)!=len(nodes): fail(422,'硬先修图包含环，拒绝保存')
    for node in nodes:
        aliases=node.get('aliases',[])
        if not isinstance(aliases,list) or len(aliases)>20 or any(not isinstance(value,str) or not value.strip() or len(value)>100 for value in aliases):fail(422,'知识点别名不合法')
    with transaction() as db:
        id=uid();insert(db,'graph_versions',id=id,nodes=dump(nodes),edges=dump(edges),owner_id=user['id'],created_at=now());audit(db,user['id'],'graph_registered',id)
    return {'id':id,'topological_order':order,'status':'registered','message':'图谱登记完成，正式主题仍需题库与证据映射'}

@router.post('/admin/graphs/{id}/activate')
def graph_activate(id:str,user=Depends(current_user)):
    role(user,'admin')
    from app.services.learning import SKILLS
    with transaction() as db:
        graph=one(db,'SELECT * FROM graph_versions WHERE id=:id',id=id)
        if not graph:fail(404,'图谱不存在')
        from app.services.topic_bank import validate_banks
        validate_banks(json.loads(graph['nodes']))
        run(db,'UPDATE graph_versions SET active=0 WHERE active=1')
        run(db,'UPDATE graph_versions SET active=1 WHERE id=:id',id=id)
        audit(db,user['id'],'graph_activated',id)
    return {'ok':True,'graph_version':id}


@router.post('/admin/graphs/generate',status_code=201)
def generate_topic_graph(body:dict,user=Depends(current_user)):
    role(user,'admin')
    goal=body.get('goal');resource_ids=body.get('resource_ids')
    if not isinstance(goal,str) or not goal.strip() or len(goal)>200 or not isinstance(resource_ids,list) or not 1<=len(resource_ids)<=10 or any(not isinstance(value,str) for value in resource_ids):
        fail(422,'请提供目标和1至10份已授权来源')
    sources=[]
    with transaction() as db:
        config=one(db,"SELECT * FROM model_configs WHERE status='active'")
        if not config:fail(409,'请先评估并激活云端模型')
        for resource_id in resource_ids:
            resource=resource_access(db,user,resource_id)
            if not resource['cloud_allowed']:fail(409,'来源未授权发送云端')
            version=one(db,"SELECT * FROM resource_versions WHERE id=:v AND parse_status='ready' AND index_status='indexed'",v=resource['current_version'])
            if not version:fail(409,'来源正文未就绪')
            sources.append({'version_id':version['id'],'body':version['body'][:5000]})
    from app.api.models import call_model
    proposal=call_model(config,dump({'goal':goal,'sources':sources,'instruction':'生成待人工审阅的知识图谱与单选题库JSON，返回nodes数组和edges数组。最多30节点。节点含id、name、minutes、aliases、source_version_ids、diagnostic_questions、retest_questions、practice_questions。三套题目须不同，每题含id、skill、prompt、options、answer（从0开始字符串序号）、explanation。仅使用所给资料，不能确定的内容列入gaps。不要自动批准。'}))
    nodes=proposal.get('nodes')
    if not isinstance(nodes,list) or not nodes or len(nodes)>30:fail(503,'模型图谱规模不合法','MODEL_SCHEMA_INVALID')
    allowed={source['version_id'] for source in sources}
    for node in nodes:
        citations=node.get('source_version_ids') if isinstance(node,dict) else None
        if not isinstance(citations,list) or not citations or any(not isinstance(value,str) for value in citations) or not set(citations)<=allowed:
            fail(503,'模型图谱引用不合法','MODEL_CITATION_INVALID')
    from app.services.topic_bank import validate_banks
    validate_banks(nodes)
    with transaction() as db:
        for resource_id,source in zip(resource_ids,sources):
            current=resource_access(db,user,resource_id)
            if not current['cloud_allowed'] or current['current_version']!=source['version_id']:fail(409,'生成期间来源权限或版本发生变化')
    result=graph_create({'nodes':nodes,'edges':proposal.get('edges',[])},user)
    return {**result,'gaps':proposal.get('gaps',[]),'review_required':True}
