import json
from pathlib import Path
from app.core.db import transaction,one,insert,now,dump,audit

def import_candidates():
    base=Path(__file__).resolve().parents[3]/'docs'/'curriculum'
    packs=json.loads((base/'question-answer-sources.json').read_text(encoding='utf-8'))['packs']
    items=json.loads((base/'question-review-drafts.json').read_text(encoding='utf-8'))['items']
    added_packs=added_items=0
    with transaction() as db:
        admin=one(db,"SELECT id FROM users WHERE role='admin' AND status='active' ORDER BY created_at LIMIT 1")
        if not admin:raise ValueError('需要已有管理员账号')
        for p in packs:
            if not one(db,'SELECT id FROM question_source_packs WHERE id=:i',i=p['id']):
                insert(db,'question_source_packs',id=p['id'],payload=dump(p),imported_at=now());added_packs+=1
        for q in items:
            if q.get('published') or q.get('approved_for_scoring'):raise ValueError('只能导入待审核摘要')
            skill='public-'+q['candidate_skill_id']
            if not one(db,'SELECT id FROM curriculum_catalog_skills WHERE id=:i',i=skill):raise ValueError('缺少课程知识点：'+skill)
            if not one(db,'SELECT id FROM question_review_candidates WHERE id=:i',i=q['id']):
                insert(db,'question_review_candidates',id=q['id'],pack_id=q['pack_id'],skill_id=skill,payload=dump(q),status='pending_teacher_review',imported_at=now());added_items+=1
        if added_packs or added_items:audit(db,admin['id'],'question_candidates_imported','public-questions',dump({'packs':added_packs,'drafts':added_items}))
    return {'created_packs':added_packs,'created_drafts':added_items,'published_questions':0}
