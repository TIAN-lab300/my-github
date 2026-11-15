from app.services.public_catalog import import_catalog
from app.services.question_candidates import import_candidates
from app.core.db import transaction,one

def test_import_candidates_is_private_and_repeatable(clients):
    import_catalog()
    assert import_candidates()=={'created_packs':37,'created_drafts':15,'published_questions':0}
    assert import_candidates()['created_drafts']==0
    for name in ('teacher','student'):
        assert clients[name].get('/api/v1/admin/question-candidates').status_code==403
    r=clients['admin'].get('/api/v1/admin/question-candidates')
    assert r.status_code==200 and len(r.json()['items'])==15
    assert all(q['status']=='pending_teacher_review' and not q['approved_for_scoring'] for q in r.json()['items'])
    with transaction() as db:
        assert one(db,'SELECT COUNT(*) n FROM diagnoses')['n']==0
        assert one(db,'SELECT COUNT(*) n FROM observations')['n']==0
