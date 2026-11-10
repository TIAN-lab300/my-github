"""Coverage checks, bounded external supplementation, and reviewed link import."""
import os
import hashlib
import json
from pathlib import Path
from fastapi import APIRouter,Depends
from app.core.db import DATA,transaction,one,run,insert,uid,now,dump
from app.core.security import current_user,resource_access,role,fail
from app.api.resources import visible,tokenize
from app.services.web_evidence import search_web,fetch_page,search_status

router=APIRouter()


def coverage_for(body,user):
    nodes=body.get('nodes')
    if not isinstance(nodes,list) or not nodes or len(nodes)>100:
        fail(422,'请提供1至100个待检查知识点')
    if any(not isinstance(node,dict) or not isinstance(node.get('id'),str) or not isinstance(node.get('title'),str) or not node['title'].strip() for node in nodes):
        fail(422,'知识点必须具有编号和标题')
    ids={node['id'] for node in nodes}
    if len(ids)!=len(nodes):fail(422,'知识点编号重复')
    gaps=[];sources={}
    requires_current=body.get('requires_current') is True
    max_age=body.get('max_age_days',180)
    if type(max_age) is not int or not 1<=max_age<=3650:fail(422,'来源时效窗口须为1至3650天')
    with transaction() as db:
        from app.services.planning_rules import graph_snapshot
        from app.services.topic_bank import question_bank
        graph,_=graph_snapshot(db)
        known={node['id']:node for node in graph}
        bank,_=question_bank(db,'diagnostic')
        candidates=[]
        for resource in visible(db,user):
            if resource['status']!='published' and resource['scope']!='private':continue
            version=one(db,"SELECT * FROM resource_versions WHERE id=:v AND parse_status='ready' AND index_status='indexed'",v=resource['current_version'])
            if version:candidates.append((resource,version))
        for node in nodes:
            registered=known.get(node['id'])
            if registered is None:gaps.append({'node_id':node['id'],'type':'mapping','reason':'知识点尚未映射已审核图谱'})
            prerequisites=registered['prerequisites'] if registered else node.get('prerequisites',[])
            if not isinstance(prerequisites,list) or any(not isinstance(value,str) for value in prerequisites):fail(422,'先修关系必须为编号列表')
            for prerequisite in prerequisites:
                if prerequisite not in ids:gaps.append({'node_id':node['id'],'type':'prerequisite','reason':'先修节点缺失 '+prerequisite})
            if type(node.get('minutes')) is not int or node['minutes']<=0:gaps.append({'node_id':node['id'],'type':'duration','reason':'缺少正整数预计学时'})
            if not any(question['skill']==node['id'] for question in bank):gaps.append({'node_id':node['id'],'type':'assessment','reason':'缺少已关联题目'})
            matched=[{'resource_id':resource['id'],'version_id':version['id'],'excerpt':version['body'][max(0,version['body'].lower().find(node['title'].lower())-60):][:500]} for resource,version in candidates if node['title'].lower() in version['body'].lower()]
            sources[node['id']]=matched
            if requires_current and matched:
                from datetime import datetime,timezone
                today=datetime.now(timezone.utc).date()
                fresh=False
                for source in matched:
                    version=next(version for _,version in candidates if version['id']==source['version_id'])
                    declared=json.loads(version['extraction_json']).get('published_at')
                    try:age=(today-datetime.fromisoformat(declared).date()).days
                    except (TypeError,ValueError):age=None
                    source['published_at']=declared
                    source['freshness']='unknown' if age is None else 'current' if 0<=age<=max_age else 'outside_window'
                    fresh=fresh or source['freshness']=='current'
                if not fresh:gaps.append({'node_id':node['id'],'type':'freshness','reason':'来源日期未知或超出时效窗口，需要核实当前资料'})
            if not matched:gaps.append({'node_id':node['id'],'type':'evidence','reason':'授权正文没有明确标题匹配，需补充材料或人工确认'})
    # Kahn traversal validates the complete dependency structure, including disconnected cycles.
    pending={node['id']:set(node.get('prerequisites',[]))&ids for node in nodes}
    while pending:
        ready={key for key,value in pending.items() if not value}
        if not ready:
            gaps.append({'node_id':None,'type':'cycle','reason':'先修结构存在环'});break
        pending={key:value-ready for key,value in pending.items() if key not in ready}
    return {'status':'draft' if gaps else 'candidate','gaps':gaps,'sources':sources,
            'coverage_method':'授权正文标题匹配与确定性结构检查，语义充分性需审查',
            'search_eligible':bool(gaps) and all(gap['type'] in ('evidence','freshness') for gap in gaps)}


@router.get('/admin/search/status')
def provider_status(user=Depends(current_user)):
    role(user,'admin')
    return search_status()

@router.post('/admin/search/evaluate')
def evaluate_search(user=Depends(current_user)):
    error=None
    try:results=search_web('Python 官方文档 函数')
    except Exception as exception:
        results=[];error=str(exception)[:250] if isinstance(exception,ValueError) else '搜索服务超时或网络不可达'
    with transaction() as db:
        from app.core.db import audit
        insert(db,'search_runs',id=uid(),actor_id=user['id'],query='Python 官方文档 函数',status='failed' if error else 'provider_verified' if results else 'empty',rounds=1,results=dump(results),error=error,created_at=now())
        audit(db,user['id'],'search_capability_evaluated',None,result='failed' if error else 'success')
    if error:fail(503,error,'SEARCH_PROVIDER_UNAVAILABLE')
    return {'provider_search_verified':bool(results),'evidence_verified':False,'result_count':len(results),'results':results}


@router.post('/retrieval/coverage')
def coverage(body:dict,user=Depends(current_user)):
    return coverage_for(body,user)


@router.post('/retrieval/supplement')
def supplement(body:dict,user=Depends(current_user)):
    query=body.get('query')
    if not isinstance(query,str) or not query.strip() or len(query)>200:fail(422,'检索词须为1至200字')
    mode=body.get('mode','upload_only')
    if mode not in ('upload_only','web_allowed'):fail(422,'检索模式不合法')
    check=coverage_for(body,user) if body.get('nodes') else {'status':'draft','gaps':[{'type':'evidence','reason':'仅请求资料推荐，未检查完整学习目标覆盖'}],'sources':{},'search_eligible':True}
    fresh=body.get('requires_current') is True
    if mode=='upload_only' or (not check['search_eligible'] and not (fresh and not check['gaps'])):
        return {**check,'results':[],'web_search_executed':False,'rounds':0}
    results=[];seen=set();error=None;rounds=0
    try:
        for number in range(2):
            rounds+=1
            search_query=query if number==0 else query+' 教程 官方文档'
            for result in search_web(search_query):
                if result['url'] in seen:continue
                seen.add(result['url']);result['retrieved_at']=now()
                results.append(result)
            if results:break
    except Exception as exc:
        error=str(exc)[:250] if isinstance(exc,ValueError) else '搜索服务超时或网络不可达'
    status='failed' if error else 'recommendations' if results else 'empty'
    with transaction() as db:
        search_id=uid()
        insert(db,'search_runs',id=search_id,actor_id=user['id'],query=query,status=status,rounds=rounds,results=dump(results),error=error,created_at=now())
    return {**check,'status':'draft','search_id':search_id,'results':results,'error':error,
            'web_search_attempted':True,'web_search_executed':not error or search_status()['configured'],'rounds':rounds,'message':'推荐网址待教师审核并导入正文，当前证据不足时保留草稿'}


@router.post('/resources/{id}/import-link',status_code=201)
def import_link(id:str,body:dict,user=Depends(current_user)):
    role(user,'teacher')
    if body.get('authorized') is not True:fail(422,'须确认有权抓取并用于课程教学')
    with transaction() as db:
        resource=resource_access(db,user,id,True)
        if resource['kind']!='link':fail(409,'仅登记的网址可导入')
        if type(body.get('version')) is not int or body['version']!=resource['version']:fail(409,'资料已变化')
        source=one(db,'SELECT * FROM resource_versions WHERE id=:v',v=resource['current_version'])
    try:page=fetch_page(source['filename'])
    except Exception as exc:
        fail(422,str(exc)[:250] if isinstance(exc,ValueError) else '网页抓取失败，请检查网址或稍后重试')
    version_id=uid();storage=uid()+'.txt';data=page['body'].encode('utf-8')
    (DATA/'files'/storage).write_bytes(data)
    try:
        with transaction() as db:
            current=resource_access(db,user,id,True)
            if current['version']!=resource['version']:fail(409,'抓取期间资料已变化，请重新审核')
            insert(db,'resource_versions',id=version_id,resource_id=id,filename='imported-webpage.txt',storage_key=storage,mime='text/plain',bytes=len(data),hash=hashlib.sha256(data).hexdigest(),body=page['body'],parse_status='ready',index_status='indexed',error=None,extraction_json=dump({'url':page['url'],'domain':page['domain'],'retrieved_at':now(),'published_at':page.get('published_at'),'reviewed_by':user['id']}),review_status='approved',created_at=now())
            run(db,'INSERT INTO chunks VALUES(:r,:v,:b)',r=id,v=version_id,b=tokenize(page['body']))
            run(db,"UPDATE resources SET kind='text',current_version=:v,status='draft',version=version+1 WHERE id=:r",v=version_id,r=id)
            from app.core.db import audit
            audit(db,user['id'],'resource_link_imported',id,page['url'])
    except Exception:
        (DATA/'files'/storage).unlink(missing_ok=True);raise
    return {'id':id,'version_id':version_id,'status':'draft','message':'授权正文已导入，请审核后发布'}
