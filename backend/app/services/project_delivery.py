"""Engineering delivery is independent of BKT; only authorized humans accept artifacts."""
import json
from urllib.parse import urlsplit
from app.core.db import transaction,one,rows,run,insert,uid,now,dump,audit,touch
from app.core.security import fail,role,class_access,resource_access
from app.services import engineering_goals as engineering


def access(db,user,gid,write=False):
    g=one(db,'SELECT * FROM goals WHERE id=:g',g=gid)
    if not g:fail(404,'工程目标不存在')
    if user['role']=='student':
        if g['student_id']!=user['id']:fail(404,'工程目标不存在')
    elif user['role']=='teacher':
        if not g['class_id']:fail(404,'该工程未关联你的班级')
        class_access(db,user,g['class_id'],True)
    elif user['role']!='admin':fail(403,'无权查看工程')
    if write:
        role(user,'student')
        if g['status']=='archived':fail(409,'已归档工程不能修改或提交')
        if g['class_id'] and class_access(db,user,g['class_id'])['status']!='active':fail(409,'关联班级已归档')
    ctx=engineering.context(db,gid)
    if not ctx:fail(409,'该目标仍是旧主题范围，请通过大模型重新解析工程目标，不能用Python基础替代完整工程','PROJECT_SCOPE_REQUIRED')
    analysis=json.loads(ctx['analysis'])
    if write:
        engineering.validate_scope(db,gid)
        if 'opengl' in g['title'].lower() and not any('图形' in s.get('course_name','') for s in analysis['skills']):fail(409,'OpenGL工程范围缺少图形学课程，请重新使用大模型解析目标','PROJECT_SCOPE_REQUIRED')
    if analysis.get('goal_type','project')!='project':fail(409,'课程或知识点目标不需要工程成果验收')
    return g,ctx,analysis


def default_spec(g):
    return {'deliverable':g['title'],'language':'','platform':'','toolchain':'',
            'acceptance_criteria':['源码可构建并说明运行步骤','提交符合目标的运行画面或演示','说明测试结果与已知限制'],
            'excluded_features':[],'auto_replan':False}


def save_spec(gid,user,body):
    with transaction() as db:
        g,_,_=access(db,user,gid,True);old=one(db,'SELECT * FROM project_workspaces WHERE goal_id=:g',g=gid)
        if type(body.get('version')) is not int or body['version']!=(old['version'] if old else 0):fail(409,'工程设定已变化，请刷新')
        spec=body.get('spec',{})
        if not isinstance(spec,dict):fail(422,'工程设定必须为对象')
        for field,limit in [('deliverable',2000),('language',100),('platform',200),('toolchain',500)]:
            if not isinstance(spec.get(field),str) or not spec[field].strip() or len(spec[field])>limit:fail(422,'请填写有效的'+field)
        for field in ('acceptance_criteria','excluded_features'):
            values=spec.get(field)
            if not isinstance(values,list) or len(values)>12 or (field=='acceptance_criteria' and not values) or any(not isinstance(x,str) or not x.strip() or len(x)>500 for x in values):fail(422,'验收条件/不包含功能格式无效')
        if type(spec.get('auto_replan')) is not bool:fail(422,'自动重规划须为布尔值')
        clean={k:spec[k] for k in default_spec(g)}
        if old:run(db,'UPDATE project_workspaces SET spec=:s,version=version+1,auto_last_key=NULL WHERE goal_id=:g',s=dump(clean),g=gid)
        else:insert(db,'project_workspaces',goal_id=gid,spec=dump(clean),created_at=now())
        audit(db,user['id'],'project_spec_saved',gid);touch(db,user['id'])
    return {'ok':True}


def milestone_gate(db,g,m):
    active=one(db,"SELECT * FROM project_delivery_plans WHERE goal_id=:g AND status='active'",g=g['id'])
    if not active or m['milestone_key'] not in {x['key'] for x in json.loads(active['payload'])['milestones']}:fail(409,'阶段不属于当前活动工程计划')
    data=json.loads(m['payload'])
    spec=json.loads(one(db,'SELECT spec FROM project_workspaces WHERE goal_id=:g',g=g['id'])['spec']);frozen=json.loads(active['payload'])['spec']
    if any(spec[k]!=frozen[k] for k in spec if k!='auto_replan'):fail(409,'工程交付设定已变化，请重新生成并接受工程计划')
    accepted={x['milestone_key'] for x in rows(db,"SELECT milestone_key FROM project_milestones WHERE goal_id=:g AND status='accepted'",g=g['id'])}
    if not set(data['depends_on'])<=accepted:fail(409,'前置工程阶段尚未验收')
    from app.services.learning import mastery
    values=mastery(db,g['student_id'])
    if any(values.get(sid,{}).get('probability',0)<.75 for sid in data['knowledge_ids']):fail(409,'阶段所需知识点尚未通过有效测验，请先完成学习或重测')
    return active,data


def submit(gid,mid,user,body):
    with transaction() as db:
        g,_,_=access(db,user,gid,True);m=one(db,'SELECT * FROM project_milestones WHERE id=:m AND goal_id=:g',m=mid,g=gid)
        if not m:fail(404,'工程阶段不存在')
        if m['status']=='accepted':fail(409,'该阶段已验收，原成果保留')
        active,data=milestone_gate(db,g,m);evidence={}
        for field,limit in [('notes',6000),('code',50000),('build_log',20000),('repository_url',2048),('commit_ref',64)]:
            value=body.get(field,'')
            if not isinstance(value,str) or len(value)>limit:fail(422,'提交内容'+field+'无效')
            evidence[field]=value.strip()
        if not evidence['notes']:fail(422,'请说明实现、测试和已知限制')
        if evidence['repository_url']:
            u=urlsplit(evidence['repository_url'])
            import re
            if not re.fullmatch('[0-9a-fA-F]{7,64}',evidence['commit_ref']):fail(422,'提交Git仓库时请填写7至64位提交哈希，避免验收内容随分支变化')
            if u.scheme not in ('http','https') or not u.hostname or u.username or u.password:fail(422,'仓库地址须为无凭据HTTP/HTTPS链接')
        ids=body.get('resource_ids',[])
        if not isinstance(ids,list) or len(ids)>8 or any(not isinstance(x,str) for x in ids) or len(ids)!=len(set(ids)):fail(422,'最多关联8份本人资料')
        artifacts=[]
        for rid in ids:
            r=resource_access(db,user,rid)
            if r['owner_id']!=user['id']:fail(403,'只能提交本人上传的工程附件')
            if r['kind']=='link':fail(422,'网页收藏不是冻结附件，请在仓库字段填写地址与提交哈希')
            v=one(db,'SELECT id,filename,hash FROM resource_versions WHERE id=:v',v=r['current_version'])
            artifacts.append({'resource_id':rid,'version_id':v['id'],'kind':r['kind'],'filename':v['filename'],'sha256':v['hash']})
        evidence['artifacts']=artifacts
        for required in data['evidence_requirements']:
            present=bool(evidence['code'] or evidence['repository_url'] or any(a['filename'].lower().endswith(('.cpp','.c','.h','.hpp','.py','.glsl','.vert','.frag')) for a in artifacts)) if required=='code' else bool(evidence['build_log']) if required=='build_log' else bool(evidence['repository_url']) if required=='repository' else any(a['kind']==required for a in artifacts)
            if not present:fail(422,'缺少本阶段要求的提交物：'+required)
        minutes=body.get('actual_minutes')
        if type(minutes) is not int or not m['actual_minutes']<=minutes<=10080 or minutes-m['actual_minutes']>1440:fail(422,'累计工程分钟不能减少，单次新增最多1440分钟')
        latest=one(db,'SELECT * FROM project_deliveries WHERE milestone_id=:m ORDER BY revision DESC LIMIT 1',m=mid)
        if latest and latest['status']=='pending':fail(409,'已有成果待验收，请等待反馈后再提交')
        ident=uid();insert(db,'project_deliveries',id=ident,milestone_id=mid,plan_id=active['id'],student_id=user['id'],revision=(latest['revision']+1 if latest else 1),snapshot=dump(data),evidence=dump(evidence),created_at=now())
        delta=minutes-m['actual_minutes']
        if delta:
            insert(db,'project_worklogs',id=uid(),student_id=user['id'],goal_id=gid,source_id=mid,class_id=g['class_id'],minutes=delta,created_at=now())
            remaining=delta
            for r in rows(db,"SELECT * FROM reservations WHERE source_type='project' AND source_id=:p AND status='active' ORDER BY local_date,id",p=active['id']):
                amount=min(remaining,r['minutes']);remaining-=amount
                if amount==r['minutes']:run(db,"UPDATE reservations SET status='completed' WHERE id=:i",i=r['id'])
                elif amount:run(db,'UPDATE reservations SET minutes=minutes-:n WHERE id=:i',n=amount,i=r['id'])
                if not remaining:break
        run(db,"UPDATE project_milestones SET status='submitted',actual_minutes=:n WHERE id=:i",n=minutes,i=mid)
        run(db,'UPDATE project_workspaces SET progress_version=progress_version+1 WHERE goal_id=:g',g=gid);touch(db,user['id']);audit(db,user['id'],'project_artifact_submitted',ident)
    return {'id':ident}


def review(delivery,user,body):
    role(user,'teacher','admin')
    with transaction() as db:
        d=one(db,'SELECT * FROM project_deliveries WHERE id=:d',d=delivery)
        if not d:fail(404,'提交不存在')
        m=one(db,'SELECT * FROM project_milestones WHERE id=:i',i=d['milestone_id']);g,_,_=access(db,user,m['goal_id'])
        if g['class_id'] and one(db,'SELECT status FROM classes WHERE id=:c',c=g['class_id'])['status']!='active':fail(409,'关联班级已归档，不能新增验收')
        if g['status']=='archived' or d['status']!='pending':fail(409,'该提交已处理或目标已归档')
        active=one(db,"SELECT id FROM project_delivery_plans WHERE goal_id=:g AND status='active'",g=g['id'])
        if not active or active['id']!=d['plan_id'] or json.loads(m['payload'])!=json.loads(d['snapshot']):fail(409,'工程计划已变更，该提交仅保留历史，请学生重新提交')
        milestone_gate(db,g,m)
        accepted=body.get('accepted');checks=body.get('checks');comment=body.get('comment','')
        if type(accepted) is not bool or not isinstance(checks,list) or any(type(i) is not int for i in checks) or len(checks)!=len(set(checks)) or not isinstance(comment,str) or not comment.strip() or len(comment)>3000:fail(422,'请填写验收结论、逐项检查及具体依据')
        expected=set(range(len(json.loads(d['snapshot'])['criteria'])))
        if not set(checks)<=expected or accepted and set(checks)!=expected:fail(422,'通过前必须核对全部验收标准')
        insert(db,'project_delivery_reviews',id=uid(),delivery_id=delivery,reviewer_id=user['id'],accepted=int(accepted),checks=dump(checks),comment=comment.strip(),created_at=now())
        run(db,'UPDATE project_deliveries SET status=:s WHERE id=:i',s='accepted' if accepted else 'needs_changes',i=delivery)
        run(db,'UPDATE project_milestones SET status=:s WHERE id=:i',s='accepted' if accepted else 'needs_changes',i=m['id'])
        if accepted:
            unused=max(0,json.loads(d['snapshot'])['minutes']-m['actual_minutes'])
            for reservation in rows(db,"SELECT * FROM reservations WHERE source_id=:p AND source_type='project' AND status='active' ORDER BY local_date,id",p=active['id']):
                amount=min(unused,reservation['minutes']);unused-=amount
                if amount==reservation['minutes']:run(db,"UPDATE reservations SET status='completed' WHERE id=:i",i=reservation['id'])
                elif amount:run(db,'UPDATE reservations SET minutes=minutes-:n WHERE id=:i',n=amount,i=reservation['id'])
                if not unused:break
        run(db,'UPDATE project_workspaces SET progress_version=progress_version+1 WHERE goal_id=:g',g=g['id']);touch(db,g['student_id']);audit(db,user['id'],'project_artifact_reviewed',delivery,'accepted' if accepted else 'needs_changes')
    return {'ok':True}


def workspace(gid,user):
    with transaction() as db:
        g,_,_=access(db,user,gid);ws=one(db,'SELECT * FROM project_workspaces WHERE goal_id=:g',g=gid)
        plans=rows(db,"SELECT * FROM project_delivery_plans WHERE goal_id=:g AND status IN ('active','pending_acceptance') ORDER BY created_at DESC",g=gid)
        for p in plans:p['payload']=json.loads(p['payload'])
        milestones=rows(db,'SELECT * FROM project_milestones WHERE goal_id=:g ORDER BY rowid',g=gid)
        for m in milestones:
            m['payload']=json.loads(m['payload']);m['deliveries']=rows(db,'SELECT * FROM project_deliveries WHERE milestone_id=:m ORDER BY revision DESC',m=m['id'])
            for d in m['deliveries']:
                d['snapshot']=json.loads(d['snapshot']);d['evidence']=json.loads(d['evidence']);d['reviews']=rows(db,'SELECT * FROM project_delivery_reviews WHERE delivery_id=:d ORDER BY created_at',d=d['id'])
        active=next((p for p in plans if p['status']=='active'),None)
        from fastapi import HTTPException
        for m in milestones:
            m['locked_reason']=None
            if active and m['status']!='accepted':
                original={**m,'payload':dump(m['payload'])}
                try:milestone_gate(db,g,original)
                except HTTPException as exc:m['locked_reason']=exc.detail.get('message','暂不可提交')
        active_keys={m['key'] for m in active['payload']['milestones']} if active else set()
        relevant=[m for m in milestones if m['milestone_key'] in active_keys]
        material_pack='opengl' if 'opengl' in g['title'].lower() or any(p['mode']=='opengl_template' for p in plans) else None
        return {'has_diagnosis':bool(one(db,'SELECT id FROM diagnoses WHERE goal_id=:g AND goal_version=:v AND attempt_id IS NOT NULL',g=gid,v=g['version'])),'material_pack':material_pack,'goal':g,'spec':json.loads(ws['spec']) if ws else default_spec(g),'version':ws['version'] if ws else 0,
                'plans':plans,'milestones':milestones,'completed':bool(relevant) and all(m['status']=='accepted' for m in relevant) and all(json.loads(ws['spec'])[k]==active['payload']['spec'][k] for k in active['payload']['spec'] if k!='auto_replan'),
                'auto_error':ws['auto_error'] if ws else None,'can_review':user['role'] in ('teacher','admin')}
