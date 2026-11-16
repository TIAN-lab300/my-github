"""Read-only, answer-free learner evidence shared by planning agents."""
import json
from app.core.db import rows
from app.services.learning import mastery


def learner_evidence(db, student, goal, graph, diagnosis):
    scope = set(json.loads(goal['skills']))
    # Include all transitive prerequisites without relying on graph ordering.
    while True:
        expanded = scope | {p for node in graph if node['id'] in scope for p in node['prerequisites']}
        if expanded == scope:
            break
        scope = expanded
    current = mastery(db, student)
    initial = json.loads(diagnosis['mastery_snapshot'] or '{}')
    skills = []
    for node in graph:
        sid = node['id']
        if sid not in scope:
            continue
        value = current.get(sid, {'probability': .2, 'evidence_count': 0})
        results = rows(db, 'SELECT correct FROM observations WHERE student_id=:u AND attempt_id=:a AND skill=:s ORDER BY sequence',
                       u=student, a=diagnosis['attempt_id'], s=sid)
        reused=False
        if sid.startswith('catalog:') and not results:
            import json as _json
            for q in _json.loads(diagnosis['questions']):
                if q['skill']!=sid:continue
                result=rows(db,'''SELECT o.correct FROM project_evidence_links l JOIN observations o ON o.id=l.observation_id WHERE l.student_id=:u AND l.question_id=:q''',u=student,q=q.get('question_id') or q.get('course_question_version_id') or q['id'])
                results+=result;reused=reused or bool(result)
        skills.append({'skill_id': sid, 'name': node['name'], 'prerequisites': node['prerequisites'],
                       'probability': value['probability'], 'evidence_count': value['evidence_count'],
                       'status': 'unknown' if not value['evidence_count'] else 'mastered' if value['probability'] >= .75 else 'weak' if value['probability'] < .45 else 'developing',
                       'diagnostic_correct': sum(r['correct'] for r in results), 'diagnostic_total': len(results),'reused_scored_evidence':reused,
                       'diagnostic_probability': initial.get(sid, {}).get('probability'),
                       'latest_evidence_id': value.get('last_update', {}).get('evidence_id')})
    activity = rows(db, '''SELECT c.id,c.item_id,c.minutes,c.proportion FROM checkins c
        JOIN paths p ON p.id=c.path_id WHERE c.student_id=:u AND p.goal_id=:g ORDER BY c.id''', u=student, g=goal['id'])
    cb=rows(db,'SELECT course_id FROM course_goal_bindings WHERE goal_id=:g',g=goal['id'])
    if cb:
        activity+=rows(db,'''SELECT s.id,s.material_link_id AS item_id,s.minutes,0 AS proportion
            FROM learning_sessions s JOIN learning_material_links l ON l.id=s.material_link_id
            WHERE s.student_id=:u AND l.course_id=:c ORDER BY s.id''',u=student,c=cb[0]['course_id'])
    context=None
    if cb:
        from app.services.curriculum_structure import structure
        course_structure=structure(db,cb[0]['course_id'])
        context={'relation_version':course_structure['version']['id'] if course_structure['version'] else None,
            'course_prerequisites':[{'course_id':p['before_id'],'name':p['name'],'kind':p['kind'],'mastery_verified':False} for p in course_structure['course_prerequisites']],
            'external_requirements':[{'name':p['name'],'mastery_verified':False} for p in course_structure['external_requirements']],
            'instruction':'这些是项目课程基础建议，不是该学生已完成或未完成的证明；仅按有效知识点证据判定掌握度'}
    from app.services.engineering_goals import context as project_context
    pc=project_context(db,goal['id'])
    if pc:
        context={'kind':'engineering_foundation_scope','summary':json.loads(pc['analysis'])['summary'],
            'uncovered_capabilities':json.loads(pc['analysis'])['uncovered_capabilities'],
            'instruction':'只覆盖已确认的课程基础，不得声称未映射的OpenGL专项或整个工程已完成。数学与前置课程未检测不代表已掌握。'}
    return {'contract_version': 'learner-evidence-v1', 'diagnosis_id': diagnosis['id'],
            'attempt_id': diagnosis['attempt_id'], 'goal_version': diagnosis['goal_version'],
            'bank_version': diagnosis['bank_version'], 'mastery_rule': 'bkt-v1',
            'mastered_threshold': .75, 'weak_threshold': .45, 'skills': skills,
            'activity': activity, 'activity_minutes': sum(r['minutes'] for r in activity),
            'scope': 'goal_and_prerequisites', 'catalog_evidence_integrated': bool(cb or pc),'course_context':context}


def evidence_changes(before, after):
    if not before:
        return []
    changes = []
    if before.get('diagnosis_id') != after['diagnosis_id'] or before.get('skills') != after['skills']:
        changes.append('有效测验证据变化')
    if before.get('activity') != after['activity']:
        changes.append('学习执行记录变化')
    return changes
