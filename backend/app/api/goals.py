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
    return [q if q.get('course_question_version_id') else {**q,'version':version,'rule_version':'assessment-v1','source':{'kind':'curated' if version in ('curated-v1','diagnostic-v1','equivalent-v1') else 'reviewed_graph','id':'zhixing-'+q['id'],'license':'项目自编题' if version in ('curated-v1','diagnostic-v1','equivalent-v1') else '经管理员审核的图谱题库，来源见图谱版本'}} for q in bank]

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
    from app.services.goal_interpretation import interpret as analyze
    return analyze(body.get('text'),user,body.get('cloud_consent'))


@router.post('/goals/from-interpretation',status_code=201)
def create_interpreted(body:dict,user=Depends(current_user)):
    role(user,'student')
    if not isinstance(body.get('proposal_id'),str):fail(422,'请先用大模型解析目标')
    from app.services.goal_interpretation import confirm
    return confirm(body['proposal_id'],user,body)


@router.delete('/goals/{id}')
def delete_archived(id:str,user=Depends(current_user)):
    from app.services.goal_deletion import delete_archived
    return delete_archived(id,user)


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
            fail(409,'等价题库已用尽；不能重复公开试卷刷掌握度','RETEST_BANK_EXHAUSTED')
        graph_id=history[0]['bank_version']
        from app.services.course_planning import binding,bank as course_bank,closure
        cb=binding(db,id)
        graph,_=graph_snapshot(db,id);required=closure(graph,json.loads(g['skills']))
        if cb:
            from app.services.curriculum_structure import extend_graph
            graph=extend_graph(db,cb['course_id'],json.loads(cb['mappings']),graph)
            required=closure(graph,json.loads(g['skills']))
        bank,bank_version=(course_bank(db,cb,'retest',required),'course:'+cb['course_id']) if cb else question_bank(db,'retest',graph_id if graph_id not in ('diagnostic-v1','curated-v1') else None)
        questions=bank if cb else question_snapshot(bank,bank_version)
        questions=[q for q in questions if q['skill'] in required]
        from app.services.engineering_goals import context as project_context
        if cb or project_context(db,id):
            from app.services.assessment_sessions import recover_history,question_keys
            recover_history(db,user['id'])
            seen={r['identity'] for r in rows(db,'SELECT identity FROM question_exposures WHERE student_id=:u',u=user['id'])}
            questions=[q for q in questions if not any(k in seen for k in question_keys(q))]
        if required-{q['skill'] for q in questions}:fail(409,'重测未覆盖目标及全部先修，请补齐未曝光的新题','RETEST_BANK_EXHAUSTED')
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
            from app.services.engineering_goals import context as project_context
            catalog_context=project_context(db,g['id'])
            g['is_engineering']=bool(catalog_context and json.loads(catalog_context['analysis']).get('goal_type','project')=='project')
            parsed=one(db,"SELECT analysis FROM project_goal_proposals WHERE confirmed_goal_id=:g AND mode='unified'",g=g['id'])
            g['goal_type']=json.loads(parsed['analysis']).get('goal_type') if parsed else 'project' if g['is_engineering'] else 'knowledge'
            g['target_skill_ids']=json.loads(g.pop('skills'))
            diagnostic=one(db,'SELECT * FROM diagnoses WHERE goal_id=:g AND goal_version=:v AND attempt_id IS NOT NULL ORDER BY created_at DESC LIMIT 1',g=g['id'],v=g['version'])
            g['requires_diagnosis']=not bool(diagnostic)
            g['diagnoses']=rows(db,'SELECT id,attempt_id FROM diagnoses WHERE goal_id=:id ORDER BY created_at DESC',id=g['id'])
        return goals

def validate_goal(db,user,body,goal_id=None):
    if not body.title.strip(): fail(422,'目标标题不能为空')
    try: due=date.fromisoformat(body.due_date)
    except ValueError: fail(422,'截止日期格式错误')
    settings=one(db,'SELECT timezone FROM budgets WHERE user_id=:u',u=user['id'])
    today=datetime.now(ZoneInfo(settings['timezone'])).date()
    if due<today or due>today+timedelta(days=730): fail(422,'截止日期须在未来两年内')
    if body.class_id:
        c=class_access(db,user,body.class_id)
        if c['status']!='active': fail(409,'不能关联归档班级')
    graph,_=graph_snapshot(db,goal_id)
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
        from app.services.course_planning import binding
        cb=binding(db,id)
        from app.services.engineering_goals import context as project_context
        if project_context(db,id) and 'target_skill_ids' in body and set(body['target_skill_ids'])!=set(json.loads(g['skills'])):
            fail(409,'工程能力范围已冻结，请重新解析并确认新目标；时间预算和截止日期仍可修改')
        if cb and 'target_skill_ids' in body and set(body['target_skill_ids'])!=set(json.loads(g['skills'])):
            fail(409,'课程目标的知识点绑定不可直接改写，请完成新的课程初测并创建新目标')
        if body.get('version')!=g['version']: fail(409,'目标版本已变化')
        if g['status']=='archived': fail(409,'归档目标只读')
        if set(body)-{'version','status','title','target_skill_ids','weekly_minutes','due_date','class_id','preference'}: fail(422,'目标包含不支持的字段')
        if body.get('status',g['status']) not in (g['status'],'archived'): fail(422,'目标状态不合法')
        preserve_goal(db,g)
        if body.get('status')=='archived':
            run(db,"UPDATE goals SET status='archived',version=version+1 WHERE id=:id",id=id)
            run(db,"UPDATE reservations SET status='cancelled' WHERE goal_id IN (:id,:project) AND status='active'",id=id,project='project:'+id)
        else:
            try:
                merged=GoalInput(title=body.get('title',g['title']),target_skill_ids=body.get('target_skill_ids',json.loads(g['skills'])),weekly_minutes=body.get('weekly_minutes',g['weekly_minutes']),due_date=body.get('due_date',g['due_date']),class_id=body.get('class_id',g['class_id']),preference=body.get('preference',g['preference']))
            except ValidationError: fail(422,'目标字段不合法')
            skills=validate_goal(db,user,merged,id)
            run(db,'UPDATE goals SET title=:t,skills=:s,weekly_minutes=:w,due_date=:d,class_id=:c,version=version+1 WHERE id=:id',t=merged.title,s=dump(skills),w=merged.weekly_minutes,d=merged.due_date,c=merged.class_id,id=id)
            run(db,'UPDATE goals SET preference=:p WHERE id=:id',p=merged.preference,id=id)
        touch(db,user['id'])
        updated=one(db,'SELECT * FROM goals WHERE id=:id',id=id)
        preserve_goal(db,updated)
        if project_context(db,id) and updated['status']!='archived':
            prior=one(db,'SELECT * FROM diagnoses WHERE goal_id=:g AND attempt_id IS NOT NULL ORDER BY created_at DESC LIMIT 1',g=id)
            if prior and prior['goal_version']!=updated['version']:
                insert(db,'diagnoses',id=uid(),goal_id=id,student_id=user['id'],questions=prior['questions'],attempt_id=prior['attempt_id'],
                    goal_version=updated['version'],bank_version=prior['bank_version'],mastery_snapshot=prior['mastery_snapshot'],created_at=now())
    return {'ok':True,'message':'目标版本已更新，已完成记录保留'}

@router.post('/goals/{id}/curriculum-snapshot')
def accept_curriculum_snapshot(id:str,user=Depends(current_user)):
    from app.services.curriculum_governance import changes,save_snapshot,snapshot
    from app.services.engineering_goals import context,validate_scope
    with transaction() as db:
        goal=goal_access(db,user,id)
        ctx=context(db,id)
        if not ctx or goal['status']=='archived':fail(409,'目标不可更新依赖')
        validate_scope(db,id)
        delta=changes(db,id)
        if not delta:return {'curriculum_snapshot_id':one(db,'SELECT curriculum_snapshot_id FROM goals WHERE id=:g',g=id)['curriculum_snapshot_id'],'changes':[]}
        ident=save_snapshot(db,id,snapshot(db,id,json.loads(ctx['skill_ids'])))
        audit(db,user['id'],'goal_curriculum_snapshot_accepted',id,detail=ident)
        return {'curriculum_snapshot_id':ident,'changes':delta}


@router.post('/goals/{id}/diagnoses',status_code=201)
def diagnose(id:str,user=Depends(current_user)):
    with transaction() as db:
        g=goal_access(db,user,id)
        from app.services.engineering_goals import validate_scope
        validate_scope(db,id)
        if g['status']=='archived': fail(409,'目标已归档')
        graph,graph_version=graph_snapshot(db,id)
        if not json.loads(g['skills']) or not set(json.loads(g['skills']))<=set(s['id'] for s in graph): fail(409,'该主题缺少可用题库')
        # Do not allow infinite replay of identical disclosed questions as new evidence.
        existing=one(db,'SELECT * FROM diagnoses WHERE goal_id=:id AND goal_version=:v ORDER BY created_at DESC',id=id,v=g['version'])
        if existing: return {'id':existing['id'],'questions':public_questions(json.loads(existing['questions'])),'attempt_id':existing['attempt_id']}
        from app.services.course_planning import binding,attach_diagnosis,closure
        from app.services.engineering_goals import context
        catalog_context=context(db,id)
        if catalog_context and json.loads(catalog_context['analysis']).get('goal_type')=='course':
            previous=one(db,"SELECT * FROM diagnoses WHERE goal_id=:g AND attempt_id IS NOT NULL AND bank_version LIKE 'course:%' ORDER BY goal_version DESC LIMIT 1",g=id)
            if previous:
                did=uid()
                insert(db,'diagnoses',id=did,goal_id=id,student_id=user['id'],goal_version=g['version'],
                       bank_version=previous['bank_version'],questions=previous['questions'],
                       attempt_id=previous['attempt_id'],mastery_snapshot=previous['mastery_snapshot'],created_at=now())
                return {'id':did,'questions':public_questions(json.loads(previous['questions'])),'attempt_id':previous['attempt_id']}
        cb=binding(db,id)
        if cb:
            latest=one(db,"SELECT * FROM learning_assessments WHERE student_id=:u AND course_id=:c AND phase='diagnostic' AND status='submitted' ORDER BY submitted_at DESC,rowid DESC LIMIT 1",u=user['id'],c=cb['course_id'])
            if not latest:fail(409,'请先在课程知识库完成首次诊断')
            did=attach_diagnosis(db,g,latest,cb)
            d=one(db,'SELECT * FROM diagnoses WHERE id=:i',i=did)
            return {'id':did,'questions':public_questions(json.loads(d['questions'])),'attempt_id':d['attempt_id']}
        bank,bank_version=question_bank(db,'diagnostic',graph_version)
        questions=question_snapshot(bank,bank_version)
        published = rows(db, "SELECT * FROM bank_versions WHERE status='published' ORDER BY created_at,id")
        managed = []
        for version in published:
            content = json.loads(version['content'])
            if content['purpose']=='diagnostic' and content['skill'] in {node['id'] for node in graph}:
                managed.append({**content, 'id':version['id'], 'question_id':version['question_id'], 'version':version['version']})
        if managed:
            managed_skills = {question['skill'] for question in managed}
            questions = [question for question in questions if question['skill'] not in managed_skills] + managed
            bank_version = 'managed-diagnostic-v1'
        required=closure(graph,json.loads(g['skills']))
        questions=[q for q in questions if q['skill'] in required]
        missing=required-{q['skill'] for q in questions}
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
        from app.services.course_planning import validate_versions,binding
        binding(db,g['id'])
        validate_versions(db,json.loads(d['questions']))
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
        from app.services.course_planning import binding,validate_versions
        binding(db,g['id']);validate_versions(db,questions)
        validate_answers(questions,body.answers)
        aid=uid();insert(db,'attempts',id=aid,student_id=user['id'],goal_id=g['id'],class_id=g['class_id'],answers=dump(body.answers),feedback='[]',status='scored',minutes=body.minutes,created_at=now())
        f,s=observations(db,aid,questions,body.answers,user['id'],g['class_id'])
        run(db,'UPDATE attempts SET feedback=:f,score=:s WHERE id=:id',f=dump(f),s=s,id=aid)
        run(db,'UPDATE diagnoses SET attempt_id=:a WHERE id=:id',a=aid,id=id)
        run(db,'UPDATE diagnoses SET mastery_snapshot=:m WHERE id=:id',m=dump(mastery(db,user['id'])),id=id)
        save_mastery(db,user['id']);return one(db,'SELECT * FROM attempts WHERE id=:id',id=aid)


def assessment_item(db,user,path_id,item_id):
    p=one(db,"SELECT * FROM paths WHERE id=:id AND student_id=:u AND status='active'",id=path_id,u=user['id'])
    if not p: fail(404,'活动路径不存在')
    if goal_access(db,user,p['goal_id'])['status']=='archived':fail(409,'归档目标不能提交新测验')
    item=next((t for t in json.loads(p['tasks'])+json.loads(p['validation']).get('remediations',[]) if t['id']==item_id),None)
    if not item: fail(404,'任务不存在')
    m=mastery(db,user['id'])
    if any(m.get(s,{}).get('probability',.2)<.75 for s in item['prerequisites']): fail(409,'先修尚未达标')
    return p,item


@router.post('/goals/interpretations/{id}/supplement',status_code=201)
def supplement_goal(id:str,body:dict,user=Depends(current_user)):
    role(user,'student')
    if body.get('cloud_consent') is not True:fail(422,'请允许模型分析目标并生成补充草稿')
    from app.services.goal_supplement import generate
    return generate(id,user)
