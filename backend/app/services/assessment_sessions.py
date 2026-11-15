"""Shared session state, legacy compatibility and conservative exposure recovery."""
import json
import re
from fastapi import HTTPException
from app.core.db import one, rows, run, insert, uid, now, dump
from app.core.security import fail
from app.services.learning import public_questions, mastery


def question_keys(question):
    # Ignore whitespace, punctuation and option order when comparing exact content.
    prompt = re.sub(r'[\W_]+', '', question['prompt'].casefold())
    keys = ['prompt:' + prompt]
    if question.get('question_id'):
        keys.append(question['question_id'])
    if question.get('family'):
        keys.append('family:' + question['skill'] + ':' + question['family'])
    return keys


def expose(db, student, questions, session_id=None, source='session', timestamp=None):
    for question in questions:
        for key in question_keys(question):
            run(db, '''INSERT OR IGNORE INTO question_exposures
                (student_id,identity,session_id,created_at,source) VALUES(:u,:k,:s,:t,:origin)''',
                u=student, k=key, s=session_id, t=timestamp or now(), origin=source)


def recover_history(db, student):
    for record in rows(db, 'SELECT questions,created_at FROM diagnoses WHERE student_id=:u', u=student):
        expose(db, student, json.loads(record['questions']), source='diagnosis_snapshot', timestamp=record['created_at'])
    # Assigned questions may already have been displayed. Treat them conservatively as exposed.
    for record in rows(db, '''SELECT t.questions,t.created_at FROM tasks t
            JOIN assignments a ON a.task_id=t.id WHERE a.student_id=:u''', u=student):
        expose(db, student, json.loads(record['questions']), source='assigned_task_conservative', timestamp=record['created_at'])
    for record in rows(db, '''SELECT pa.*,a.created_at,a.answers,p.goal_id FROM path_assessments pa
            JOIN attempts a ON a.id=pa.attempt_id JOIN paths p ON p.id=pa.path_id
            WHERE a.student_id=:u''', u=student):
        if one(db, 'SELECT id FROM assessment_sessions WHERE attempt_id=:a', a=record['attempt_id']):
            continue
        frozen = one(db, 'SELECT questions FROM path_question_bank WHERE path_id=:p AND item_id=:i', p=record['path_id'], i=record['item_id'])
        if not frozen:
            continue  # Do not invent a historical snapshot if it was never retained.
        questions = json.loads(frozen['questions'])
        id = uid()
        insert(db, 'assessment_sessions', id=id, student_id=student, path_id=record['path_id'], item_id=record['item_id'],
               questions=dump(questions), answers=record['answers'], status='submitted', attempt_id=record['attempt_id'],
               created_at=record['created_at'], submitted_at=record['created_at'], rule_version='legacy-snapshot')
        expose(db, student, questions, id, 'legacy_path_snapshot', record['created_at'])
    for record in rows(db, 'SELECT id,questions,created_at FROM assessment_sessions WHERE student_id=:u', u=student):
        expose(db, student, json.loads(record['questions']), record['id'], timestamp=record['created_at'])
    seen = {row['identity'] for row in rows(db, 'SELECT identity FROM question_exposures WHERE student_id=:u', u=student)}
    for version in rows(db, 'SELECT question_id,content FROM bank_versions'):
        question = {**json.loads(version['content']), 'question_id':version['question_id']}
        if any(key in seen for key in question_keys(question)):
            expose(db, student, [question], source='historical_identity_match')


def refresh_state(db, session):
    if session['status'] != 'open':
        return session
    from app.api.goals import assessment_item
    user = one(db, 'SELECT * FROM users WHERE id=:u', u=session['student_id'])
    reason = ''
    try:
        path, _ = assessment_item(db, user, session['path_id'], session['item_id'])
        goal = one(db, 'SELECT version FROM goals WHERE id=:id', id=path['goal_id'])
        if session['goal_version'] and goal['version'] != session['goal_version']:
            reason = '学习目标已修改，请重新生成并接受学习路径'
    except HTTPException as error:
        reason = error.detail.get('message', '路径或先修条件已变化')
    if reason:
        run(db, "UPDATE assessment_sessions SET status='invalid',invalid_reason=:r WHERE id=:id", r=reason, id=session['id'])
        session = {**session, 'status':'invalid', 'invalid_reason':reason}
    return session


def session_dto(db, session):
    session = refresh_state(db, session)
    result = dict(session)
    questions = json.loads(session['questions'])
    result['questions'] = public_questions(questions)
    result['answers'] = json.loads(session['answers'])
    result['result'] = one(db, 'SELECT * FROM attempts WHERE id=:id', id=session['attempt_id']) if session['attempt_id'] else None
    if result['result']:
        result['review_questions'] = questions
    result['mastery'] = mastery(db, session['student_id'])
    return result


def begin_session(db, path_id, item_id, user, repeat=False):
    from app.api.goals import assessment_item
    path, task = assessment_item(db, user, path_id, item_id)
    recover_history(db, user['id'])
    sessions = rows(db, '''SELECT * FROM assessment_sessions WHERE student_id=:u AND path_id=:p
        AND item_id=:i ORDER BY created_at DESC,id DESC''', u=user['id'], p=path_id, i=item_id)
    for session in sessions:
        session = refresh_state(db, session)
        if session['status'] == 'open':
            return session
    if sessions and not repeat:
        return sessions[0]
    previous = next((s for s in sessions if s['status']=='submitted'), None)
    seen = {r['identity'] for r in rows(db, 'SELECT identity FROM question_exposures WHERE student_id=:u', u=user['id'])}
    candidates = []
    for version in rows(db, "SELECT * FROM bank_versions WHERE status='published' ORDER BY created_at,id"):
        question = json.loads(version['content'])
        if question['skill'] == task['skill_id'] and question['purpose'] in ('both', 'retest' if previous else 'practice'):
            candidates.append({**question, 'id':version['id'], 'question_id':version['question_id'], 'version':version['version']})
    # Existing path snapshots remain usable as the first assessment, including custom graph topics.
    if not candidates and not previous:
        frozen = one(db, 'SELECT questions FROM path_question_bank WHERE path_id=:p AND item_id=:i', p=path_id, i=item_id)
        if frozen:
            candidates = json.loads(frozen['questions'])
    previous_question = json.loads(previous['questions'])[0] if previous else None
    selected = None
    for question in candidates:
        if any(key in seen for key in question_keys(question)):
            continue
        if previous_question:
            if question.get('difficulty','medium') != previous_question.get('difficulty','medium'):
                continue
            if previous_question.get('group') and question.get('group') != previous_question['group']:
                continue
        selected = question
        break
    if not selected:
        fail(409, '当前知识点暂无可用的新测验题，请教师补充并发布题目', 'QUESTION_SHORTAGE')
    id = uid()
    goal = one(db, 'SELECT version FROM goals WHERE id=:g', g=path['goal_id'])
    insert(db, 'assessment_sessions', id=id, student_id=user['id'], path_id=path_id, item_id=item_id,
           previous_id=previous['id'] if previous else None, questions=dump([selected]), goal_version=goal['version'], created_at=now())
    expose(db, user['id'], [selected], id)
    return one(db, 'SELECT * FROM assessment_sessions WHERE id=:id', id=id)
