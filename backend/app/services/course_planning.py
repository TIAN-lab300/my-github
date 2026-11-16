"""Reviewed mappings adapt course banks to the existing four-agent pipeline."""
import json
from app.core.db import one,rows,run,insert,uid,now,dump
from app.core.security import fail
from app.services.planning_rules import graph_snapshot
from app.services.learning import mastery,save_mastery


def closure(graph,skills):
    result=set(skills)
    while True:
        expanded=result|{p for n in graph if n['id'] in result for p in n['prerequisites']}
        if expanded==result:return result
        result=expanded


def binding(db,goal_id,validate=True):
    b=one(db,'SELECT * FROM course_goal_bindings WHERE goal_id=:g',g=goal_id)
    if b and validate:
        _,version=graph_snapshot(db)
        if b['graph_version']!=version:fail(409,'课程目标绑定的图谱已变化，请由管理员核对映射并创建新课程目标','COURSE_GRAPH_CHANGED')
    return b


def bank(db,b,phase,skills=None):
    mapping=json.loads(b['mappings']);result=[]
    for m in mapping:
        if skills is not None and m['graph_skill_id'] not in skills:continue
        for q in rows(db,"""SELECT v.* FROM learning_question_versions v WHERE skill_id=:s AND status='published'
            AND phase=:p AND NOT EXISTS(SELECT 1 FROM learning_question_versions n WHERE n.question_id=v.question_id
            AND n.version>v.version AND n.status='published') ORDER BY question_id""",s=m['skill_id'],p=phase):
            result.append({'id':q['id'],'question_id':q['question_id'],'course_question_version_id':q['id'],
                'skill':m['graph_skill_id'],'prompt':q['prompt'],'options':json.loads(q['options']),
                'answer':str(q['answer']),'explanation':q['explanation'],'source':q['source'],
                'purpose':phase,'version':q['version']})
    return result


def validate_versions(db,questions):
    for q in questions:
        if q.get('course_question_version_id'):
            v=one(db,'SELECT status FROM learning_question_versions WHERE id=:i',i=q['course_question_version_id'])
            if not v or v['status']!='published':fail(409,'课程题目已停用，请重新领取测验','COURSE_QUESTION_DISABLED')


def sync_assessment(db,assessment_id):
    """Only explicitly bound courses; each displayed item contributes at most once."""
    from app.services.engineering_goals import sync_course_evidence
    sync_course_evidence(db,assessment_id)
    a=one(db,"SELECT * FROM learning_assessments WHERE id=:i AND status='submitted'",i=assessment_id)
    if not a:return None
    old=one(db,'SELECT attempt_id FROM course_evidence_attempts WHERE assessment_id=:i',i=assessment_id)
    if old:return old['attempt_id']
    _,version=graph_snapshot(db)
    bindings=rows(db,'''SELECT b.*,g.student_id,g.status FROM course_goal_bindings b JOIN goals g ON g.id=b.goal_id
        WHERE b.course_id=:c AND g.student_id=:u AND g.status!='archived' AND b.graph_version=:v
        ORDER BY b.created_at''',c=a['course_id'],u=a['student_id'],v=version)
    if not bindings:return None
    mapping={m['skill_id']:m for b in bindings for m in json.loads(b['mappings'])}
    items=rows(db,'''SELECT i.*,r.correct,r.selected_option FROM learning_assessment_items i
        JOIN learning_responses r ON r.item_id=i.id WHERE i.assessment_id=:a ORDER BY i.position''',a=a['id'])
    selected=[i for i in items if i['skill_id'] in mapping and not one(db,
        'SELECT item_id FROM learning_evidence_links WHERE student_id=:u AND question_id=:q',
        u=a['student_id'],q=json.loads(i['snapshot'])['question_id'])]
    if not selected:return None
    aid=uid()
    insert(db,'attempts',id=aid,student_id=a['student_id'],goal_id=bindings[0]['goal_id'],
        answers=dump({i['id']:str(i['selected_option']) for i in selected}),feedback='[]',
        status='scored',minutes=0,score=sum(i['correct'] for i in selected)/len(selected),created_at=now())
    for seq,i in enumerate(selected):
        oid=uid();m=mapping[i['skill_id']]
        insert(db,'observations',id=oid,attempt_id=aid,student_id=a['student_id'],skill=m['graph_skill_id'],correct=i['correct'],sequence=seq)
        insert(db,'learning_evidence_links',item_id=i['id'],observation_id=oid,mapping_id=m['id'],
            student_id=a['student_id'],question_id=json.loads(i['snapshot'])['question_id'])
    insert(db,'course_evidence_attempts',assessment_id=a['id'],attempt_id=aid)
    save_mastery(db,a['student_id'])
    return aid


def attach_diagnosis(db,g,a,b):
    """Reuse scored evidence without replaying it when the goal version changes."""
    graph,_=graph_snapshot(db);needed=closure(graph,json.loads(g['skills']))
    from app.services.curriculum_structure import extend_graph
    graph=extend_graph(db,b['course_id'],json.loads(b['mappings']),graph)
    needed=closure(graph,json.loads(g['skills']))
    mapping={m['skill_id']:m['graph_skill_id'] for m in json.loads(b['mappings'])}
    items=rows(db,'SELECT * FROM learning_assessment_items WHERE assessment_id=:a ORDER BY position',a=a['id'])
    if not needed<={mapping.get(i['skill_id']) for i in items}:fail(409,'初测尚未覆盖目标及全部先修知识点','PREREQUISITE_DIAGNOSIS_GAP')
    validate_versions(db,[{'course_question_version_id':i['question_version_id']} for i in items])
    aid=sync_assessment(db,a['id'])
    if not aid:fail(409,'课程测验尚未形成有效映射证据')
    questions=[]
    for i in items:
        if mapping.get(i['skill_id']) not in needed:continue
        q=json.loads(i['snapshot'])
        questions.append({'id':i['id'],'skill':mapping[i['skill_id']],'prompt':q['prompt'],
            'options':json.loads(q['options']),'answer':str(q['answer']),'explanation':q['explanation'],
            'course_question_version_id':q['id'],'source':q['source']})
    existing=one(db,'SELECT id FROM diagnoses WHERE goal_id=:g AND goal_version=:v AND attempt_id=:a',g=g['id'],v=g['version'],a=aid)
    if existing:return existing['id']
    did=uid();insert(db,'diagnoses',id=did,goal_id=g['id'],student_id=g['student_id'],goal_version=g['version'],
        bank_version='course:'+b['course_id'],questions=dump(questions),attempt_id=aid,
        mastery_snapshot=dump(mastery(db,g['student_id'])),created_at=now())
    return did


def fingerprint_data(db,goal_id):
    b=binding(db,goal_id,False)
    if not b:return None
    return {'binding':b,'curriculum_relations':one(db,'SELECT id,payload_hash FROM curriculum_relation_versions WHERE active=1'),'questions':rows(db,'''SELECT id,status,version FROM learning_question_versions
        WHERE course_id=:c AND status='published' ORDER BY id''',c=b['course_id']),
        'materials':rows(db,"SELECT m.* FROM learning_material_links m JOIN resources r ON r.id=m.resource_id WHERE m.course_id=:c AND (r.scope='school' OR (r.scope='private' AND r.owner_id=(SELECT student_id FROM goals WHERE id=:g))) ORDER BY m.id",c=b['course_id'],g=goal_id)}
