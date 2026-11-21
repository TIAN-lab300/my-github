"""Resume evidence-only teaching reviews of published curriculum questions."""
import argparse
import os
from collections import Counter

from app.core.db import dump, insert, now, one, rows, transaction, uid
from app.services.curriculum_governance import check_question, review_question_content


def review_batch(limit):
    counts=Counter()
    with transaction() as db:
        config=one(db,"SELECT id,secret_env FROM model_configs WHERE status='active' ORDER BY created_at DESC LIMIT 1")
        if not config or not os.getenv(config['secret_env']):
            return {'unavailable':'MODEL_KEY_MISSING'}
        candidates=rows(db,"SELECT id FROM learning_question_versions WHERE status='published' ORDER BY id")
    for candidate in candidates:
        if sum(counts.values())>=limit:break
        with transaction() as db:
            question=one(db,"SELECT * FROM learning_question_versions WHERE id=:i AND status='published'",i=candidate['id'])
            if not question:continue
            validation=check_question(db,question['id'],reuse=True)
            revision_id=validation['revision_id']
            if validation['status']!='passed':continue
            existing=one(db,"""SELECT id FROM curriculum_validation_events WHERE revision_id=:r
                AND method='automatic_teaching_v1' AND status IN ('passed','failed')
                AND json_extract(checks,'$.model_config_id')=:c""",r=revision_id,c=config['id'])
            if existing:continue
            knowledge=one(db,'SELECT name FROM curriculum_catalog_skills WHERE id=:i',i=question['skill_id'])
        result=review_question_content(question,knowledge['name'])
        with transaction() as db:
            if one(db,'SELECT * FROM learning_question_versions WHERE id=:i',i=question['id'])!=question:
                counts['changed']+=1
                continue
            insert(db,'curriculum_validation_events',id=uid(),revision_id=revision_id,
                   method='automatic_teaching_v1',status=result['status'],checks=dump(result),
                   reviewer_id=None,created_at=now())
        counts[result['status']]+=1
        if result['status']=='unavailable':
            return {**counts,'error_code':result['error_code']}
    return dict(counts)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit',type=int,default=20,help='Maximum model calls in this invocation')
    args=parser.parse_args()
    if args.limit<1:parser.error('--limit must be positive')
    result=review_batch(args.limit)
    print(result)
    raise SystemExit(1 if result.get('unavailable') or result.get('error_code') else 0)
