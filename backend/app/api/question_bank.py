"""Versioned question review and transactionally scored assessment sessions."""
import json
from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.core.db import transaction, one, rows, run, insert, uid, now, dump, audit
from app.core.security import current_user, role, fail, goal_access
from app.services.learning import observations, save_mastery
from app.services.assessment_sessions import begin_session, session_dto, recover_history, refresh_state
from app.services.diagnostic_bank import validate_answers

router = APIRouter()

class Question(BaseModel):
    skill: str = Field(min_length=1, max_length=100)
    prompt: str = Field(min_length=5, max_length=4000)
    options: list[str] = Field(min_length=2, max_length=6)
    answer: str
    explanation: str = Field(min_length=5, max_length=4000)
    difficulty: Literal['easy', 'medium', 'hard'] = 'medium'
    purpose: Literal['diagnostic', 'practice', 'retest', 'both'] = 'both'
    group: str = Field(min_length=1, max_length=100)
    family: str = Field(default='', max_length=100)
    source: str = Field(min_length=1, max_length=500)

class Review(BaseModel):
    action: Literal['submit', 'approve', 'reject', 'publish', 'disable']
    comment: str = Field(default='', max_length=2000)

class Answers(BaseModel):
    answers: dict
    minutes: int = Field(default=5, ge=1, le=1440)


def owned_version(db, id, user):
    role(user, 'teacher', 'admin')
    record = one(db, 'SELECT * FROM bank_versions WHERE id=:id', id=id)
    if not record or (user['role'] != 'admin' and record['owner_id'] != user['id']):
        fail(404, '题目不存在或无权访问')
    return record


def validated(body):
    content = body.model_dump()
    if any(not str(content[key]).strip() for key in ('skill','prompt','explanation','group','source')):
        fail(422, '题目必填内容不能只有空格')
    if len(set(option.strip() for option in body.options)) != len(body.options):
        fail(422, '选项内容不能重复')
    if body.answer not in {str(i) for i in range(len(body.options))} or any(not x.strip() for x in body.options):
        fail(422, '请选择有效答案并填写全部选项')
    return content

@router.get('/question-bank')
def bank(user=Depends(current_user)):
    role(user, 'teacher', 'admin')
    with transaction() as db:
        records = rows(db, 'SELECT * FROM bank_versions WHERE (:admin=1 OR owner_id=:u) ORDER BY created_at DESC, version DESC', admin=int(user['role']=='admin'), u=user['id'])
        for record in records:
            record['content'] = json.loads(record['content'])
            previous = one(db, 'SELECT content FROM bank_versions WHERE question_id=:q AND version<:v ORDER BY version DESC LIMIT 1', q=record['question_id'], v=record['version'])
            record['previous_content'] = json.loads(previous['content']) if previous else None
            record['reviews'] = rows(db, 'SELECT * FROM bank_reviews WHERE version_id=:v ORDER BY created_at', v=record['id'])
        return records

@router.post('/question-bank')
def create_question(body: Question, user=Depends(current_user)):
    role(user, 'teacher', 'admin')
    content = validated(body)
    with transaction() as db:
        from app.services.planning_rules import graph_snapshot
        nodes, _ = graph_snapshot(db)
        if body.skill not in {node['id'] for node in nodes}:
            fail(422, '知识点不在当前知识图谱中')
        id = uid()
        insert(db, 'bank_versions', id=id, question_id=uid(), version=1, owner_id=user['id'], content=dump(content), status='draft', created_at=now())
        audit(db, user['id'], 'question_created', id)
    return {'id': id}

@router.put('/question-bank/{id}')
def edit_question(id: str, body: Question, user=Depends(current_user)):
    content = validated(body)
    with transaction() as db:
        record = owned_version(db, id, user)
        if record['status'] not in ('draft', 'rejected'):
            fail(409, '该版本已冻结，请创建新版本')
        from app.services.planning_rules import graph_snapshot
        nodes, _ = graph_snapshot(db)
        if body.skill not in {node['id'] for node in nodes}:
            fail(422, '知识点不在当前知识图谱中')
        run(db, "UPDATE bank_versions SET content=:c,status='draft' WHERE id=:id", c=dump(content), id=id)
        audit(db, user['id'], 'question_draft_updated', id)
    return {'id': id}

@router.post('/question-bank/{id}/versions')
def new_version(id: str, user=Depends(current_user)):
    with transaction() as db:
        record = owned_version(db, id, user)
        number = one(db, 'SELECT MAX(version) AS n FROM bank_versions WHERE question_id=:q', q=record['question_id'])['n'] + 1
        existing = one(db, "SELECT id FROM bank_versions WHERE question_id=:q AND status IN ('draft','pending','rejected','approved')", q=record['question_id'])
        if existing:
            return {'id':existing['id']}
        new_id = uid()
        insert(db, 'bank_versions', id=new_id, question_id=record['question_id'], version=number, owner_id=record['owner_id'], content=record['content'], status='draft', created_at=now())
    return {'id': new_id}

@router.post('/question-bank/{id}/review')
def review(id: str, body: Review, user=Depends(current_user)):
    transitions = {'submit': ('draft', 'pending'), 'approve': ('pending', 'approved'), 'reject': ('pending', 'rejected'), 'publish': ('approved', 'published'), 'disable': ('published', 'disabled')}
    with transaction() as db:
        record = owned_version(db, id, user)
        if body.action != 'submit':
            role(user, 'admin')
        if body.action in ('approve', 'reject', 'disable') and not body.comment.strip():
            fail(422, '请填写审核或停用依据')
        before, after = transitions[body.action]
        if record['status'] != before:
            fail(409, '题目状态已变化，请刷新')
        if body.action == 'publish':
            newer = one(db, "SELECT id FROM bank_versions WHERE question_id=:q AND version>:v AND status='published'", q=record['question_id'], v=record['version'])
            if newer:
                fail(409, '已有更新版本发布，请基于最新版本修改')
            run(db, "UPDATE bank_versions SET status='disabled' WHERE question_id=:q AND status='published'", q=record['question_id'])
        run(db, 'UPDATE bank_versions SET status=:s WHERE id=:id', s=after, id=id)
        insert(db, 'bank_reviews', id=uid(), version_id=id, actor_id=user['id'], action=body.action, comment=body.comment, created_at=now())
        audit(db, user['id'], 'question_'+body.action, id, body.comment)
    return {'status': after}


def session_owned(db, id, user):
    role(user, 'student')
    result = one(db, 'SELECT * FROM assessment_sessions WHERE id=:id AND student_id=:u', id=id, u=user['id'])
    if not result:
        fail(404, '测验不存在')
    return result


@router.get('/assessment-sessions/{id}')
def get_session(id: str, user=Depends(current_user)):
    with transaction() as db:
        return session_dto(db, session_owned(db, id, user))

@router.get('/paths/{path}/items/{item}/sessions')
def history(path: str, item: str, user=Depends(current_user)):
    role(user, 'student')
    with transaction() as db:
        owned = one(db, 'SELECT id FROM paths WHERE id=:p AND student_id=:u', p=path, u=user['id'])
        if not owned:
            fail(404, '路径不存在')
        recover_history(db, user['id'])
        return [session_dto(db, session) for session in rows(db,
            'SELECT * FROM assessment_sessions WHERE student_id=:u AND path_id=:p AND item_id=:i ORDER BY created_at DESC,id DESC',
            u=user['id'], p=path, i=item)]

@router.post('/paths/{path}/items/{item}/sessions')
def start(path: str, item: str, user=Depends(current_user)):
    with transaction() as db:
        return session_dto(db, begin_session(db, path, item, user))

@router.post('/paths/{path}/items/{item}/retests')
def retest(path: str, item: str, user=Depends(current_user)):
    with transaction() as db:
        return session_dto(db, begin_session(db, path, item, user, repeat=True))

@router.get('/teacher/classes/{class_id}/assessment-sessions')
def teacher_history(class_id: str, user=Depends(current_user)):
    from app.core.security import class_access
    role(user, 'teacher')
    with transaction() as db:
        class_access(db, user, class_id, True)
        records = rows(db, """SELECT s.*,u.name AS student_name FROM assessment_sessions s
            JOIN paths p ON p.id=s.path_id JOIN goals g ON g.id=p.goal_id
            JOIN users u ON u.id=s.student_id WHERE g.class_id=:c ORDER BY s.created_at DESC""", c=class_id)
        return [session_dto(db, record) for record in records]

@router.put('/assessment-sessions/{id}/answers')
def save_answers(id: str, body: Answers, user=Depends(current_user)):
    from app.api.goals import assessment_item
    with transaction() as db:
        session = refresh_state(db, session_owned(db, id, user))
        assessment_item(db, user, session['path_id'], session['item_id'])
        if session['status'] != 'open':
            fail(409, '测验已提交')
        validate_answers(json.loads(session['questions']), body.answers, partial=True)
        run(db, 'UPDATE assessment_sessions SET answers=:a,minutes=:m WHERE id=:id', a=dump(body.answers), m=body.minutes, id=id)
    return {'ok': True}

@router.post('/assessment-sessions/{id}/submit')
def submit(id: str, body: Answers, user=Depends(current_user)):
    from app.api.goals import assessment_item
    with transaction() as db:
        session = session_owned(db, id, user)
        if session['status'] == 'submitted':
            return session_dto(db, session)
        session = refresh_state(db, session)
        if session['status'] != 'open':
            fail(409, session['invalid_reason'] or '测验已失效')
        p, task = assessment_item(db, user, session['path_id'], session['item_id'])
        questions = json.loads(session['questions'])
        from app.services.course_planning import validate_versions,binding
        binding(db,p['goal_id'])
        validate_versions(db,questions)
        validate_answers(questions, body.answers)
        goal = goal_access(db, user, p['goal_id'])
        aid = uid()
        insert(db, 'attempts', id=aid, student_id=user['id'], goal_id=goal['id'], class_id=goal['class_id'], answers=dump(body.answers), feedback='[]', status='scored', minutes=body.minutes, created_at=now())
        feedback, score = observations(db, aid, questions, body.answers, user['id'], goal['class_id'])
        run(db, 'UPDATE attempts SET feedback=:f,score=:s WHERE id=:id', f=dump(feedback), s=score, id=aid)
        run(db, "UPDATE assessment_sessions SET answers=:a,minutes=:m,status='submitted',attempt_id=:aid,submitted_at=:t WHERE id=:id", a=dump(body.answers), m=body.minutes, aid=aid, t=now(), id=id)
        run(db, 'INSERT OR IGNORE INTO path_assessments(path_id,item_id,attempt_id) VALUES(:p,:i,:a)', p=session['path_id'], i=session['item_id'], a=aid)
        save_mastery(db, user['id'])
        return session_dto(db, session_owned(db, id, user))
