import json
from fastapi import APIRouter,Depends
from app.core.db import transaction,one,rows,run,insert,uid,now,dump,audit
from app.core.security import current_user,role,goal_access,resource_access,fail
from app.services import engineering_goals as service
router=APIRouter()

@router.get('/engineering-goals/catalog')
def engineering_catalog(user=Depends(current_user)):
    role(user,'student')
    with transaction() as db:return {'skills':service.catalog(db)}

@router.get('/engineering-goals/drafts')
def drafts(user=Depends(current_user)):
    role(user,'student')
    with transaction() as db:
        records=rows(db,'SELECT id,description,mode,analysis,created_at FROM project_goal_proposals WHERE student_id=:u AND confirmed_goal_id IS NULL ORDER BY created_at DESC LIMIT 100',u=user['id'])
    for r in records:
        a=json.loads(r.pop('analysis'));r['settings']=a.get('draft_settings',{});r['analysed']=r['mode']!='draft'
        if r['analysed']:r['proposal']=a
    return records

@router.post('/engineering-goals/drafts',status_code=201)
def save_draft(body:dict,user=Depends(current_user)):
    role(user,'student');description=body.get('description')
    if not isinstance(description,str) or not 1<=len(description.strip())<=2000:fail(422,'请先填写工程目标描述，最多2000字')
    due=body.get('due_date','');weekly=body.get('weekly_minutes',300)
    if not isinstance(due,str) or type(weekly) is not int or not 1<=weekly<=10080:fail(422,'草稿日期或每周分钟格式不正确')
    if due:
        from datetime import date
        try:date.fromisoformat(due)
        except ValueError:fail(422,'草稿日期格式不正确')
    mode=body.get('mode');selected=body.get('manual_skill_ids')
    if mode is not None and mode not in ('cloud','opengl_template','manual_catalog'):fail(422,'草稿解析方式不合法')
    if selected is not None and (not isinstance(selected,list) or len(selected)>20 or any(not isinstance(x,str) for x in selected)):fail(422,'手动知识点选择格式不合法')
    with transaction() as db:
        existing=one(db,'SELECT * FROM project_goal_proposals WHERE id=:i AND student_id=:u',i=body.get('draft_id',''),u=user['id']) if body.get('draft_id') else None
        if body.get('draft_id') and not existing:fail(404,'草稿不存在')
        if existing and existing['confirmed_goal_id']:fail(409,'该草稿已确认为目标，请新建草稿')
        prior=json.loads(existing['analysis']) if existing else {}
        unchanged=bool(existing and existing['description']==description.strip())
        if existing and mode is not None and existing['mode']!='draft' and mode!=existing['mode']:unchanged=False
        if existing and selected is not None and (mode=='manual_catalog' or existing['mode']=='manual_catalog') and set(selected)!=set(prior.get('skill_ids',[])):unchanged=False
        analysis=prior if unchanged else {}
        settings={**prior.get('draft_settings',{}),'due_date':due,'weekly_minutes':weekly}
        if mode is not None:settings['mode']=mode
        if selected is not None:settings['manual_skill_ids']=selected
        analysis.update(draft_settings=settings,draft_version=prior.get('draft_version',0)+1)
        ident=existing['id'] if existing else uid()
        if existing:
            run(db,'UPDATE project_goal_proposals SET description=:d,mode=:m,analysis=:a WHERE id=:i',d=description.strip(),m=existing['mode'] if unchanged else 'draft',a=dump(analysis),i=ident)
        else:insert(db,'project_goal_proposals',id=ident,student_id=user['id'],description=description.strip(),mode='draft',model_config_id=None,analysis=dump(analysis),created_at=now())
        audit(db,user['id'],'engineering_goal_draft_saved',ident)
    return {'id':ident,'message':'工程草稿已保存，可刷新后恢复；尚未确认能力范围，不会生成诊断或活动路径。'}

@router.post('/engineering-goals/{id}/materials',status_code=201)
def private_material(id:str,body:dict,user=Depends(current_user)):
    role(user,'student')
    with transaction() as db:
        goal_access(db,user,id);ctx=service.context(db,id)
        if not ctx or body.get('skill_id') not in json.loads(ctx['skill_ids']):fail(422,'请选择本工程范围内的知识点')
        if body.get('confirmed') is not True:fail(422,'请确认正文与知识点对应且有权用于个人学习')
        r=resource_access(db,user,body.get('resource_id',''))
        if r['scope']!='private' or r['owner_id']!=user['id']:fail(403,'这里只能关联本人私有资料')
        v=one(db,'SELECT * FROM resource_versions WHERE id=:i',i=r['current_version'])
        if not v or v['parse_status']!='ready' or v['index_status']!='indexed' or not v['body'].strip():fail(409,'该资料尚无已确认正文；仅有网页收藏或图片原文件不能直接作为正文')
        old=one(db,'SELECT id FROM learning_material_links WHERE skill_id=:s AND resource_version_id=:v',s=body['skill_id'],v=v['id'])
        if old:return {'id':old['id']}
        s=one(db,'SELECT course_id FROM curriculum_catalog_skills WHERE id=:i',i=body['skill_id']);ident=uid()
        insert(db,'learning_material_links',id=ident,course_id=s['course_id'],skill_id=body['skill_id'],resource_id=r['id'],resource_version_id=v['id'],locator='本人确认的工程目标学习资料，不作为学校共享正文')
        audit(db,user['id'],'engineering_private_material_linked',id,ident)
    return {'id':ident}

@router.get('/admin/engineering-question-drafts')
def engineering_drafts(offset:int=0,user=Depends(current_user)):
    role(user,'admin')
    if not 0<=offset<=100000:fail(422,'分页位置不合法')
    with transaction() as db:
        result=rows(db,"""SELECT v.*,c.name course_name,s.name skill_name FROM learning_question_versions v
            JOIN curriculum_catalog_courses c ON c.id=v.course_id JOIN curriculum_catalog_skills s ON s.id=v.skill_id
            WHERE v.status='draft' AND v.source LIKE '工程目标AI出题草稿%' ORDER BY v.created_at,v.id LIMIT 50 OFFSET :o""",o=offset)
        for q in result:q['options']=json.loads(q['options'])
        total=one(db,"SELECT COUNT(*) n FROM learning_question_versions WHERE status='draft' AND source LIKE '工程目标AI出题草稿%'")['n']
    return {'items':result,'total':total}

@router.post('/engineering-goals/interpret',status_code=201)
def interpret(body:dict,user=Depends(current_user)):
    role(user,'student');text=body.get('description')
    if not isinstance(text,str) or not 1<=len(text.strip())<=2000:fail(422,'请输入1至2000字的工程目标')
    with transaction() as db:
        existing=one(db,'SELECT * FROM project_goal_proposals WHERE id=:i AND student_id=:u',i=body.get('draft_id',''),u=user['id']) if body.get('draft_id') else None
        if body.get('draft_id') and not existing:fail(404,'草稿不存在')
        if existing and existing['confirmed_goal_id']:fail(409,'目标已确认，请新建草稿')
        expected_version=json.loads(existing['analysis']).get('draft_version',0) if existing else 0
    analysis,config_id=service.interpret(text.strip(),body.get('mode','cloud'),body.get('cloud_consent'),body.get('skill_ids'))
    with transaction() as db:
        if existing:
            current=one(db,'SELECT * FROM project_goal_proposals WHERE id=:i',i=existing['id'])
            if current['confirmed_goal_id'] or json.loads(current['analysis']).get('draft_version',0)!=expected_version:fail(409,'解析期间草稿已修改，请重试')
            analysis.update(draft_settings=json.loads(current['analysis']).get('draft_settings',{}),draft_version=expected_version+1)
            ident=existing['id'];run(db,'UPDATE project_goal_proposals SET description=:d,mode=:m,analysis=:a,model_config_id=:c WHERE id=:i',d=text.strip(),m=analysis['mode'],a=dump(analysis),c=config_id,i=ident)
        else:
            ident=uid();insert(db,'project_goal_proposals',id=ident,student_id=user['id'],description=text.strip(),mode=analysis['mode'],model_config_id=config_id,analysis=dump(analysis),created_at=now())
        audit(db,user['id'],'engineering_goal_interpreted',ident,dump({'mode':analysis['mode'],'model_called':analysis['model_called']}))
    return {'id':ident,**analysis}

@router.post('/engineering-goals/proposals/{id}/confirm',status_code=201)
def confirm(id:str,body:dict,user=Depends(current_user)):
    role(user,'student');return service.confirm(id,user,body)

@router.post('/engineering-goals/proposals/{id}/question-drafts',status_code=201)
def draft_questions(id:str,body:dict,user=Depends(current_user)):
    role(user,'student')
    if body.get('cloud_consent') is not True:fail(422,'请允许向模型发送本工程目标与公开知识点名称')
    with transaction() as db:
        p=one(db,'SELECT * FROM project_goal_proposals WHERE id=:i AND student_id=:u',i=id,u=user['id'])
        if not p:fail(404,'提案不存在')
        analysis=json.loads(p['analysis'])
    response,config_id=service.model_call('GoalDiagnosisAgent',{'description':p['description'],'skills':analysis['skills'],
        'instruction':'编写与工程情境相关且对应给定真实知识点的完整中文单选题。每题应只有一个正确答案，条件自足，不依赖未给出的图或代码。题目只作为待审核草稿，不能声称已获得教师审核。',
        'output':{'questions':[{'skill_id':'给定skills中的id','prompt':'题干不超过4000字','options':['2至6个不同选项'],'answer':'从0开始的整数','explanation':'明确解释，不超过2000字','phase':'diagnostic或practice或retest'}]}})
    qs=response.get('questions') if isinstance(response,dict) else None
    if not isinstance(qs,list) or not 1<=len(qs)<=12:fail(503,'模型题目数量格式错误','MODEL_SCHEMA_INVALID')
    allowed={s['id']:s for s in analysis['skills']};seen=set()
    from app.api.learning_catalog import Question
    parsed=[]
    for q in qs:
        try:valid=Question(**{**q,'course_id':allowed[q['skill_id']]['course_id'],'source':'工程目标AI出题草稿；模型配置'+config_id+'；须管理员核对内容、答案和教学适用性后发布。'})
        except Exception:fail(503,'模型题目知识点或字段格式错误','MODEL_SCHEMA_INVALID')
        if not valid.prompt.strip() or valid.prompt in seen or not valid.explanation.strip() or not 2<=len(valid.options)<=6 or len(set(valid.options))!=len(valid.options) or any(not o.strip() for o in valid.options) or not 0<=valid.answer<len(valid.options):fail(503,'模型题干、选项或答案未通过检查','MODEL_SCHEMA_INVALID')
        seen.add(valid.prompt);parsed.append(valid)
    with transaction() as db:
        created=[]
        for q in parsed:
            if one(db,"SELECT v.id FROM learning_question_versions v JOIN learning_questions q ON q.id=v.question_id WHERE q.owner_id=:u AND v.skill_id=:s AND v.phase=:p AND v.prompt=:t",u=user['id'],s=q.skill_id,p=q.phase,t=q.prompt):continue
            qid=uid();vid=uid();insert(db,'learning_questions',id=qid,course_id=q.course_id,owner_id=user['id'],created_at=now())
            insert(db,'learning_question_versions',id=vid,question_id=qid,course_id=q.course_id,skill_id=q.skill_id,version=1,phase=q.phase,prompt=q.prompt,options=dump(q.options),answer=q.answer,explanation=q.explanation,source=q.source,created_at=now())
            created.append(vid)
        audit(db,user['id'],'engineering_question_drafts_created',id,dump({'model_config_id':config_id,'count':len(created)}))
    # Do not disclose generated answers to the student and then test on them.
    return {'created':len(created),'status':'draft','message':'模型题目已进入对应课程的管理员审核队列，发布前不参与诊断和掌握度计算。'}

@router.get('/engineering-goals/{id}/readiness')
def readiness(id:str,user=Depends(current_user)):
    with transaction() as db:
        g=goal_access(db,user,id);ctx=service.context(db,id)
        if not ctx:fail(404,'不是工程目标')
        graph,_=service.graph_for(db,id);mappings={n['native_skill_id']:n for n in graph}
        current=one(db,'SELECT id FROM curriculum_relation_versions WHERE active=1')
        scope_stale=ctx['relation_version']!=(current['id'] if current else None)
        from app.services.learning import mastery
        evidence=mastery(db,user['id'])
        all_counts={phase:{} for phase in ('diagnostic','practice','retest')}
        for phase in all_counts:
            for q in service.bank(db,ctx['graph_version'],phase):all_counts[phase][q['skill']]=all_counts[phase].get(q['skill'],0)+1
        result=[]
        for sid,node in mappings.items():
            counts={p:all_counts[p].get(node['id'],0) for p in all_counts}
            links=rows(db,"""SELECT m.*,r.title FROM learning_material_links m JOIN resources r ON r.id=m.resource_id JOIN resource_versions v ON v.id=m.resource_version_id
                WHERE m.skill_id=:s AND ((r.scope='school' AND r.status='published') OR (r.scope='private' AND r.owner_id=:u)) AND r.current_version=v.id AND v.parse_status='ready' AND v.index_status='indexed'""",s=sid,u=user['id'])
            gaps=[p+'题缺失' for p,n in counts.items() if not n]
            if not links:gaps.append('缺少关联的授权正文')
            value=evidence.get(node['id'],{'probability':.2,'evidence_count':0})
            status='unknown' if not value['evidence_count'] else 'mastered' if value['probability']>=.75 else 'weak' if value['probability']<.45 else 'developing'
            result.append({'id':sid,'graph_skill_id':node['id'],'name':node['name'],'course_id':node['course_id'],'question_counts':counts,'materials':links,'gaps':gaps,'evidence_status':status,'evidence_count':value['evidence_count']})
        from app.services.curriculum_search import search_courses
        courses=[]
        for cid in dict.fromkeys(n['course_id'] for n in graph):
            c=one(db,'SELECT id,name FROM curriculum_catalog_courses WHERE id=:i',i=cid)
            matches=search_courses(db,c['name']);c['links']=next((x['links'] for x in matches if x['course_id']==cid),[])
            relevant=[s for s in result if s['course_id']==cid]
            c['recommendation_reason']='本阶段涉及'+str(len(relevant))+'个知识点：需补强'+str(sum(s['evidence_status']=='weak' for s in relevant))+'个，发展中'+str(sum(s['evidence_status']=='developing' for s in relevant))+'个，尚无证据'+str(sum(s['evidence_status']=='unknown' for s in relevant))+'个。只推荐相关章节，不要求整门课全部重学。'
            courses.append(c)
        recent=rows(db,"SELECT id,status,error,result_id,kind FROM agent_runs WHERE goal_id=:g ORDER BY created_at DESC LIMIT 5",g=id)
        return {'goal_id':id,'skills':result,'courses':courses,'analysis':json.loads(ctx['analysis']),
            'auto_enabled':bool(ctx['auto_enabled']),'auto_mode':ctx['auto_mode'],'auto_error':ctx['auto_error'],'recent_runs':recent,
            'scope_stale':scope_stale,'ready':not scope_stale and all(not s['gaps'] for s in result),'note':'课程推荐不等于已导入正文；仅确认的基础范围参与本次路径。'}

@router.patch('/engineering-goals/{id}/automation')
def automation(id:str,body:dict,user=Depends(current_user)):
    with transaction() as db:
        g=goal_access(db,user,id)
        if not service.context(db,id):fail(404,'不是工程目标')
        if type(body.get('enabled')) is not bool or body.get('mode','local') not in ('local','cloud'):fail(422,'自动重规划设置不合法')
        run(db,'UPDATE project_goal_contexts SET auto_enabled=:e,auto_mode=:m,auto_last_key=NULL,auto_error=NULL WHERE goal_id=:g',e=int(body['enabled']),m=body.get('mode','local'),g=id)
        audit(db,user['id'],'engineering_auto_replan_changed',id,dump(body))
    return {'ok':True,'message':'系统仅生成重规划候选，不自动接受；后台服务运行时检查变化。'}
