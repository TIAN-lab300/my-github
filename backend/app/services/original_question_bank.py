"""Idempotent, immutable foundation-bank releases with explicit non-official provenance."""
import hashlib,json
from pathlib import Path
from app.core.db import transaction,one,rows,insert,now,dump,audit

ROOT=Path(__file__).resolve().parents[3]
BANK=ROOT/'docs/curriculum/original-foundations-bank.json'

def load_bank():
    raw=BANK.read_bytes();bank=json.loads(raw)
    if len(bank['questions'])!=1071 or len(bank['project_rubrics'])!=20:raise ValueError('基础题库数量与发布清单不符')
    identities=set();prompts=set();coverage={}
    for q in bank['questions']:
        if q['id'] in identities or q['prompt'] in prompts:raise ValueError('题目标识或题干重复')
        identities.add(q['id']);prompts.add(q['prompt'])
        if q['phase'] not in ('diagnostic','practice','retest'):raise ValueError('用途不合法')
        if len(q['options'])!=2 or set(q['options'])!={'正确','错误'} or type(q['answer']) is not int or q['answer'] not in (0,1):raise ValueError('选项与答案不合法')
        if not q['explanation'].strip() or not q['source'].strip():raise ValueError('解析和来源不可为空')
        if q['explanation'].startswith('该说法正确。')!=(q['options'][q['answer']]=='正确'):raise ValueError('答案与解释矛盾')
        key=(q['course_id'],q['skill_id'],q['phase'])
        if key in coverage:raise ValueError('同一用途知识点重复')
        coverage[key]=q['id']
    if len({q['skill_id'] for q in bank['questions']})!=357:raise ValueError('知识点覆盖不完整')
    for q in bank['questions']:
        if any((q['course_id'],q['skill_id'],p) not in coverage for p in ('diagnostic','practice','retest')):raise ValueError('知识点缺少测验用途')
    return bank,hashlib.sha256(raw).hexdigest()

def import_bank():
    bank,digest=load_bank();version=bank['version']
    with transaction() as db:
        old=one(db,'SELECT * FROM learning_bank_releases WHERE id=:i',i=version)
        if old:
            if old['content_hash']!=digest:raise ValueError('同一题库版本内容已改变，请创建新版本，不能静默覆盖历史')
            return {'release':version,'created_questions':0,'created_rubrics':0,'already_imported':True}
        admin=one(db,"SELECT id FROM users WHERE role='admin' AND status='active' ORDER BY created_at,id LIMIT 1")
        if not admin:raise ValueError('需要先初始化管理员账号')
        for q in bank['questions']:
            s=one(db,'SELECT s.name,c.assessment_mode FROM curriculum_catalog_skills s JOIN curriculum_catalog_courses c ON c.id=s.course_id WHERE s.id=:s AND s.course_id=:c',s=q['skill_id'],c=q['course_id'])
            if not s or s['name']!=q['skill_name'] or s['assessment_mode']=='project_rubric':raise ValueError('题目与课程知识点不一致：'+q['id'])
        for rubric in bank['project_rubrics']:
            s=one(db,'SELECT s.name,c.assessment_mode FROM curriculum_catalog_skills s JOIN curriculum_catalog_courses c ON c.id=s.course_id WHERE s.id=:s AND s.course_id=:c',s=rubric['skill_id'],c=rubric['course_id'])
            if not s or s['name']!=rubric['skill_name'] or s['assessment_mode']!='project_rubric':raise ValueError('项目量规与课程知识点不一致')
        insert(db,'learning_bank_releases',id=version,content_hash=digest,provenance=bank['provenance'],review_kind=bank['review'],created_at=now())
        for q in bank['questions']:
            insert(db,'learning_questions',id=q['id'],course_id=q['course_id'],owner_id=admin['id'],created_at=now())
            vid=q['id']+'-v1'
            # User requested a usable foundation bank. Technical publication is recorded
            # explicitly; no teacher identity or teacher approval is fabricated.
            insert(db,'learning_question_versions',id=vid,question_id=q['id'],course_id=q['course_id'],skill_id=q['skill_id'],version=1,
                phase=q['phase'],prompt=q['prompt'],options=dump(q['options']),answer=q['answer'],explanation=q['explanation'],source=q['source'],
                status='published',reviewer_id=None,created_at=now())
            insert(db,'learning_bank_release_items',release_id=version,question_version_id=vid)
        for rubric in bank['project_rubrics']:
            insert(db,'learning_project_rubrics',id=rubric['id'],release_id=version,course_id=rubric['course_id'],skill_id=rubric['skill_id'],payload=dump(rubric))
        audit(db,None,'original_foundation_bank_imported',version,dump({'questions':len(bank['questions']),'rubrics':len(bank['project_rubrics']),'review_kind':bank['review'],'teacher_approved':False}))
    return {'release':version,'created_questions':len(bank['questions']),'created_rubrics':len(bank['project_rubrics']),'already_imported':False}
