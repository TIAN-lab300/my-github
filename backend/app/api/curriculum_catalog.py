from fastapi import APIRouter,Depends
from sqlalchemy import inspect
from app.core.db import engine,transaction,rows
from app.core.security import current_user,fail
from app.core.security import role
import json
router=APIRouter()

@router.get('/admin/question-candidates')
def question_candidates(user=Depends(current_user)):
    role(user,'admin')
    if not inspect(engine).has_table('question_review_candidates'):fail(503,'待审核题库尚未部署')
    with transaction() as db:
        packs=rows(db,'SELECT id,payload FROM question_source_packs ORDER BY id')
        items=rows(db,'SELECT id,payload,status FROM question_review_candidates ORDER BY id')
    return {'packs':[json.loads(p['payload']) for p in packs],
            'items':[{**json.loads(q['payload']),'status':q['status']} for q in items],
            'published_questions':0}

@router.get('/curriculum/catalog')
def catalog(user=Depends(current_user)):
    if not inspect(engine).has_table('curriculum_catalog_courses'):
        fail(503,'课程资料目录尚未部署，请先完成数据库迁移','CATALOG_NOT_DEPLOYED')
    with transaction() as db:
        courses=rows(db,'SELECT * FROM curriculum_catalog_courses ORDER BY elective,year,id')
        for c in courses:
            from app.core.db import one
            c['chapter_count']=one(db,'SELECT count(*) n FROM learning_chapters WHERE course_id=:c',c=c['id'])['n']
            c['readable_material_count']=one(db,"SELECT count(DISTINCT r.id) n FROM learning_material_links m JOIN resources r ON r.id=m.resource_id JOIN resource_versions v ON v.id=m.resource_version_id WHERE m.course_id=:c AND r.scope='school' AND r.status='published' AND r.current_version=v.id AND v.parse_status='ready'",c=c['id'])['n']
            c['external_courses']=rows(db,'SELECT * FROM curriculum_course_links WHERE course_id=:c ORDER BY title,id',c=c['id'])
            c['skills']=rows(db,'SELECT id,name,status FROM curriculum_catalog_skills WHERE course_id=:c ORDER BY id',c=c['id'])
            c['sources']=rows(db,"SELECT s.id,s.resource_id,s.url,r.title,r.description,s.original_language FROM curriculum_catalog_sources m JOIN public_source_catalog s ON s.id=m.source_id JOIN resources r ON r.id=s.resource_id WHERE m.course_id=:c AND r.status='published' AND r.scope='school' ORDER BY s.id",c=c['id'])
    return {'courses':courses,'scope':'用户指定课程范围，候选知识点待审核','questions_ready':False}
