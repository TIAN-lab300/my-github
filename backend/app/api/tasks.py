import json
from datetime import datetime,timezone
from urllib.parse import urlsplit
from fastapi import APIRouter,Depends
from app.core.db import *
from app.core.security import *
from app.schemas import TaskInput,Submission,Review
from app.services.learning import allocate,observations,save_mastery,public_questions

router=APIRouter()

def validate_questions(questions):
    for q in questions:
        if q.get('kind')=='fill' and not str(q.get('answer','')).strip(): fail(422,'填空题必须设置正确答案')
        if q.get('kind','single') in ('single','boolean','multi'):
            options=q.get('options',[])
            if len(options)<2 or any(not str(o).strip() for o in options): fail(422,'选择题至少需要两个非空选项')
            answers=str(q.get('answer','')).split(',')
            if any(a not in {str(i) for i in range(len(options))} for a in answers): fail(422,'正确答案必须指向有效选项')
            if q.get('kind')!='multi' and len(answers)!=1: fail(422,'单选题只能有一个正确答案')

def task_dto(task,teacher=False):
    t=dict(task);q=json.loads(t['questions']);t['questions']=q if teacher else public_questions(q)
    t['recipients']=json.loads(t['recipients']) if teacher else []
    t['code_cases']=json.loads(t.get('code_cases','[]')) if teacher else []
    return t

@router.get('/teacher/tasks')
def teacher_tasks(user=Depends(current_user)):
    role(user,'teacher')
    with transaction() as db:
        result=[]
        for t in rows(db,'SELECT * FROM tasks WHERE owner_id=:u ORDER BY created_at DESC',u=user['id']):
            item=task_dto(t,True)
            item['submissions']=rows(db,'SELECT a.id AS assignment_id,a.student_id,u.name,a.status,at.id AS attempt_id,at.score,at.status AS grade_status,at.answers,at.feedback,at.created_at FROM assignments a JOIN users u ON u.id=a.student_id LEFT JOIN attempts at ON at.assignment_id=a.id WHERE a.task_id=:t',t=t['id'])
            result.append(item)
        return result

@router.post('/teacher/tasks',status_code=201)
def create(body:TaskInput,user=Depends(current_user)):
    role(user,'teacher')
    try:
        due=datetime.fromisoformat(body.due_at)
        if due.tzinfo is None: fail(422,'截止时间需要时区')
    except ValueError: fail(422,'截止时间不合法')
    if due<datetime.now(timezone.utc): fail(422,'截止时间需晚于当前时间')
    if body.mode=='code' and not body.code_cases:fail(422,'代码任务至少需要一个测试用例')
    if body.mode=='quiz' and not body.questions: fail(422,'测验至少需要一道题')
    if len({q.id for q in body.questions})!=len(body.questions): fail(422,'题目编号不能重复')
    validate_questions([q.model_dump() for q in body.questions])
    with transaction() as db:
        class_access(db,user,body.class_id,True)
        if body.resource_id:
            r=resource_access(db,user,body.resource_id)
            if r['class_id']!=body.class_id or r['status']!='published': fail(422,'只能关联本班已发布资料')
        id=uid()
        insert(db,'tasks',code_cases=dump([case.model_dump() for case in body.code_cases]),id=id,owner_id=user['id'],class_id=body.class_id,title=body.title,description=body.description,due_at=due.astimezone(timezone.utc).isoformat(),minutes=body.minutes,mode=body.mode,resource_id=body.resource_id,questions=dump([q.model_dump() for q in body.questions]),recipients=dump(body.recipients),created_at=now())
        audit(db,user['id'],'task_created',id)
    return {'id':id}

@router.post('/teacher/tasks/{id}/publish')
def publish(id:str,user=Depends(current_user)):
    role(user,'teacher')
    with transaction() as db:
        t=one(db,'SELECT * FROM tasks WHERE id=:id AND owner_id=:u',id=id,u=user['id'])
        if not t: fail(404,'任务不存在')
        class_access(db,user,t['class_id'],True)
        if t['status']=='published': return {'ok':True}
        if t['status']!='draft': fail(409,'只有草稿可以发布')
        if datetime.fromisoformat(t['due_at'])<=datetime.now(timezone.utc): fail(422,'截止时间已过，请先修改草稿')
        validate_questions(json.loads(t['questions']))
        if t['mode']=='code' and not json.loads(t['code_cases']):fail(422,'代码任务缺少测试用例')
        if t['resource_id']:
            resource=resource_access(db,user,t['resource_id'])
            if resource['status']!='published' or resource['class_id']!=t['class_id']: fail(409,'关联资料已下架或不属于本班，不能发布任务')
            run(db,'UPDATE tasks SET resource_version_id=:v WHERE id=:id',v=resource['current_version'],id=id)
        members={m['user_id'] for m in rows(db,"SELECT user_id FROM memberships WHERE class_id=:c AND status='active'",c=t['class_id'])}
        recipients=json.loads(t['recipients']) or list(members)
        if not recipients or not set(recipients)<=members: fail(422,'接收人必须是本班有效成员')
        conflicts=[]
        for student in set(recipients):
            aid=uid();insert(db,'assignments',id=aid,task_id=id,student_id=student)
            try: schedule=allocate(db,student,t['minutes'],t['due_at'])
            except Exception as exc:
                if not hasattr(exc,'status_code') or exc.status_code!=409: raise
                # Mandatory teacher work remains explicit, even if over budget.
                schedule=[{'date':t['due_at'][:10],'minutes':t['minutes']}];conflicts.append(student)
            for s in schedule: insert(db,'reservations',id=uid(),student_id=student,source_type='teacher',source_id=aid,goal_id=None,local_date=s['date'],minutes=s['minutes'])
            touch(db,student)
        run(db,"UPDATE tasks SET status='published',version=version+1 WHERE id=:id",id=id)
        audit(db,user['id'],'task_published',id)
    return {'ok':True,'budget_conflicts':conflicts,'message':'冲突学生需查看重规划建议，原AI路径未改动'}

@router.post('/teacher/tasks/{id}/supplement',status_code=201)
def supplement(id:str,body:dict,user=Depends(current_user)):
    role(user,'teacher')
    recipients=body.get('student_ids')
    if not isinstance(recipients,list) or not recipients or any(not isinstance(s,str) for s in recipients):
        fail(422,'请选择补发学生')
    with transaction() as db:
        old=one(db,'SELECT * FROM tasks WHERE id=:id AND owner_id=:u',id=id,u=user['id'])
        if not old: fail(404,'任务不存在')
        class_access(db,user,old['class_id'],True)
        if body.get('expected_version')!=old['version']: fail(409,'任务已更新，请刷新')
        if old['status'] not in ('published','closed','revoked'): fail(409,'草稿不能补发')
        members={m['user_id'] for m in rows(db,"SELECT user_id FROM memberships WHERE class_id=:c AND status='active'",c=old['class_id'])}
        if not set(recipients)<=members: fail(422,'补发学生必须是本班有效成员')
        # Reuse an identical pending supplement on network retry or double click.
        selected=sorted(set(recipients))
        for existing in rows(db,"SELECT t.* FROM tasks t JOIN task_reissues r ON r.task_id=t.id WHERE r.previous_task_id=:id AND t.status='draft'",id=id):
            if sorted(json.loads(existing['recipients']))==selected:
                return {'id':existing['id'],'reused':True}
        new_id=uid()
        old.update(id=new_id,status='draft',version=1,recipients=dump(selected),created_at=now())
        insert(db,'tasks',**old)
        insert(db,'task_reissues',task_id=new_id,previous_task_id=id,created_at=now())
        audit(db,user['id'],'task_supplement_created',new_id,id)
    return {'id':new_id,'reused':False}

@router.post('/teacher/tasks/{id}/{action}')
def action(id:str,action:str,user=Depends(current_user)):
    role(user,'teacher')
    if action=='reissue':
        with transaction() as db:
            old=one(db,'SELECT * FROM tasks WHERE id=:id AND owner_id=:u',id=id,u=user['id'])
            if not old: fail(404,'任务不存在')
            class_access(db,user,old['class_id'],True)
            if old['status'] not in ('revoked','closed'): fail(409,'请先撤回或关闭原任务再建立修订版')
            new_id=uid();old.update(id=new_id,status='draft',version=1,created_at=now())
            insert(db,'tasks',**old)
            insert(db,'task_reissues',task_id=new_id,previous_task_id=id,created_at=now())
            audit(db,user['id'],'task_reissued',new_id,id)
        return {'id':new_id,'previous_task_id':id,'status':'draft','message':'修订草稿已创建，请更新截止、接收人与题目后重新发布'}
    if action not in ('withdraw','close'): fail(404,'操作不存在')
    with transaction() as db:
        t=one(db,'SELECT * FROM tasks WHERE id=:id AND owner_id=:u',id=id,u=user['id'])
        if not t: fail(404,'任务不存在')
        class_access(db,user,t['class_id'],True)
        if t['status']!='published': fail(409,'任务当前不可撤回或关闭')
        run(db,'UPDATE tasks SET status=:s,version=version+1 WHERE id=:id',s='revoked' if action=='withdraw' else 'closed',id=id)
        if action=='withdraw':
            for a in rows(db,'SELECT * FROM assignments WHERE task_id=:id',id=id):
                if a['status']!='completed':
                    run(db,"UPDATE assignments SET status='cancelled' WHERE id=:id",id=a['id'])
                    run(db,"UPDATE reservations SET status='cancelled' WHERE source_type='teacher' AND source_id=:id",id=a['id'])
                touch(db,a['student_id'])
        audit(db,user['id'],'task_'+action,id)
    return {'ok':True}

@router.get('/learners/me/tasks')
def student_tasks(status:str='',class_id:str='',user=Depends(current_user)):
    role(user,'student')
    if status not in ('','not_started','in_progress','completed','overdue','cancelled'): fail(422,'任务状态无效')
    with transaction() as db:
        tasks=rows(db,"SELECT t.*,a.id AS assignment_id,a.status AS assignment_status,a.first_completed_at,a.draft FROM tasks t JOIN assignments a ON a.task_id=t.id JOIN memberships m ON m.class_id=t.class_id AND m.user_id=a.student_id WHERE a.student_id=:u AND m.status='active' ORDER BY t.due_at,t.id",u=user['id'])
        output=[]
        for t in tasks:
            d=task_dto(t)
            d['draft']=json.loads(t['draft'])
            if d['assignment_status'] not in ('completed','cancelled') and t['due_at']<now(): d['assignment_status']='overdue'
            attempt=one(db,'SELECT * FROM attempts WHERE assignment_id=:a',a=t['assignment_id'])
            if attempt:
                attempt['answers']=json.loads(attempt['answers']);attempt['feedback']=json.loads(attempt['feedback'])
            d['attempt']=attempt
            if (not status or d['assignment_status']==status) and (not class_id or t['class_id']==class_id):
                output.append(d)
        return output

@router.put('/tasks/{id}/draft')
def save_draft(id:str,body:Submission,user=Depends(current_user)):
    role(user,'student')
    with transaction() as db:
        task=one(db,'SELECT t.*,a.id AS aid,a.status AS assignment_status FROM tasks t JOIN assignments a ON a.task_id=t.id WHERE t.id=:id AND a.student_id=:u',id=id,u=user['id'])
        if not task: fail(404,'任务未分配给你')
        class_access(db,user,task['class_id'])
        classroom=one(db,'SELECT status FROM classes WHERE id=:id',id=task['class_id'])
        if classroom['status']!='active' or task['status']!='published' or task['assignment_status'] in ('completed','cancelled'):
            fail(409,'任务不接受暂存')
        validate_submission_answers(json.loads(task['questions']),body.answers,False)
        run(db,"UPDATE assignments SET draft=:d,status='in_progress' WHERE id=:id",d=dump(body.model_dump()),id=task['aid'])
    return {'ok':True,'status':'in_progress'}

def validate_submission_answers(questions,answers,complete=True):
    known={q['id']:q for q in questions}
    if set(answers)-set(known): fail(422,'答案包含未知题目')
    for q in questions:
        value=answers.get(q['id'],'')
        if complete and not value.strip(): fail(422,'请完成所有题目')
        if value and q.get('kind','single') in ('single','boolean','multi'):
            values=value.split(',')
            allowed={str(i) for i in range(len(q['options']))}
            if not set(values)<=allowed or len(values)!=len(set(values)): fail(422,'选项无效')
            if q.get('kind')!='multi' and len(values)!=1: fail(422,'单选题只能选择一项')

@router.post('/tasks/{id}/attempts')
def submit(id:str,body:Submission,user=Depends(current_user)):
    role(user,'student')
    with transaction() as db:
        code_task=one(db,"SELECT id FROM tasks WHERE id=:id AND mode='code'",id=id)
    if code_task:
        from app.services.code_judge import submit_code
        return submit_code(id,body,user)
    with transaction() as db:
        t=one(db,'SELECT t.*,a.id AS aid,a.status AS astatus FROM tasks t JOIN assignments a ON a.task_id=t.id WHERE t.id=:id AND a.student_id=:u',id=id,u=user['id'])
        if not t: fail(404,'任务未分配给你')
        c=class_access(db,user,t['class_id'])
        if c['status']!='active': fail(409,'归档班级不接受新提交')
        previous=one(db,'SELECT * FROM attempts WHERE assignment_id=:a',a=t['aid'])
        if previous: return previous
        if t['status']!='published' or t['astatus']=='cancelled': fail(409,'任务不接受新提交')
        questions=json.loads(t['questions'])
        if t['mode']=='quiz': validate_submission_answers(questions,body.answers)
        if t['mode'] in ('text','link') and not body.text.strip(): fail(422,'提交内容不能为空')
        if t['mode']=='link':
            link=urlsplit(body.text.strip())
            if link.scheme not in ('http','https') or not link.hostname or link.username or link.password: fail(422,'请输入HTTP/HTTPS链接')
        aid=uid();pending=any(q.get('kind')=='subjective' for q in questions)
        # Insert the attempt first, so evidence foreign keys always reference a fact.
        insert(db,'attempts',id=aid,assignment_id=t['aid'],student_id=user['id'],goal_id=None,class_id=t['class_id'],answers=dump({'answers':body.answers,'text':body.text}),feedback='[]',status='pending_review' if pending else 'scored',score=None,minutes=body.minutes,created_at=now())
        run(db,'UPDATE attempts SET late=:late WHERE id=:id',late=int(now()>t['due_at']),id=aid)
        feedback,score=observations(db,aid,questions,body.answers,user['id'],t['class_id']) if t['mode']=='quiz' else ([{'message':'提交已保存，不将普通任务完成作为掌握证据'}],None)
        if pending: score=None
        run(db,'UPDATE attempts SET feedback=:f,score=:s WHERE id=:id',f=dump(feedback),s=score,id=aid)
        run(db,"UPDATE assignments SET status='completed',first_completed_at=:time,draft='{}' WHERE id=:id",time=now(),id=t['aid'])
        run(db,"UPDATE reservations SET status='completed' WHERE source_type='teacher' AND source_id=:id",id=t['aid'])
        save_mastery(db,user['id'],t['class_id'])
        return one(db,'SELECT * FROM attempts WHERE id=:id',id=aid)

@router.post('/teacher/submissions/{id}/review')
def review(id:str,body:Review,user=Depends(current_user)):
    role(user,'teacher')
    if not body.comment.strip(): fail(422,'评分依据不能为空')
    with transaction() as db:
        a=one(db,'SELECT at.*,t.questions,t.owner_id FROM attempts at JOIN assignments aa ON aa.id=at.assignment_id JOIN tasks t ON t.id=aa.task_id WHERE at.id=:id',id=id)
        if not a or a['owner_id']!=user['id']: fail(404,'提交不存在')
        class_access(db,user,a['class_id'],True)
        questions=[q for q in json.loads(a['questions']) if q.get('kind')=='subjective']
        if not questions: fail(409,'该任务没有主观题')
        version=one(db,'SELECT count(*) AS n FROM grades WHERE attempt_id=:id',id=id)['n']+1
        insert(db,'grades',id=uid(),attempt_id=id,version=version,score=body.score,comment=body.comment,grader_id=user['id'],created_at=now())
        for i,q in enumerate(questions):
            run(db,'INSERT INTO observations VALUES(:id,:a,:u,:c,:s,:v,:seq) ON CONFLICT(attempt_id,skill,sequence) DO UPDATE SET correct=:v',id=uid(),a=id,u=a['student_id'],c=a['class_id'],s=q['skill'],v=int(body.score>=.75),seq=1000+i)
        feedback=json.loads(a['feedback']);feedback.append({'review_version':version,'score':body.score,'comment':body.comment,'rubric':'0至1分；达到0.75映射为达标观察（rubric-v1）'})
        run(db,"UPDATE attempts SET status='scored',score=:s,feedback=:f WHERE id=:id",s=body.score,f=dump(feedback),id=id)
        save_mastery(db,a['student_id'],a['class_id']);audit(db,user['id'],'grade_reviewed',id)
    return {'ok':True,'grade_version':version}
