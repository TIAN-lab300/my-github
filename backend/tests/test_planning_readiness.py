from app.core.db import transaction,insert,now
from datetime import date,timedelta

def test_catalog_and_diagnosis_without_model(clients):
    c=clients['student']
    catalog=c.get('/api/v1/curriculum/skills')
    assert catalog.status_code==200
    assert all(s['diagnostic_available'] for s in catalog.json()['skills'])
    r=c.post('/api/v1/goals',json={'title':'学习函数','target_skill_ids':['functions'],'due_date':(date.today()+timedelta(days=30)).isoformat(),'weekly_minutes':120,'preference':'text'})
    assert r.status_code==201,r.text
    d=c.post('/api/v1/goals/'+r.json()['id']+'/diagnoses')
    assert d.status_code==201,d.text
    assert len(d.json()['questions'])>0
    assert all('answer' not in q for q in d.json()['questions'])

def test_model_status_does_not_expose_secrets(clients,monkeypatch):
    c=clients['student']
    assert c.get('/api/v1/planning/model-status').json()['reason']=='not_active'
    with transaction() as db:
        insert(db,'model_configs',id='test-config',model='test-model',endpoint='https://api.openai.com/v1',secret_env='TEST_MODEL_SECRET',status='active',created_at=now())
    monkeypatch.delenv('TEST_MODEL_SECRET',raising=False)
    assert c.get('/api/v1/planning/model-status').json()['reason']=='missing_key'
    monkeypatch.setenv('TEST_MODEL_SECRET','private-token')
    r=c.get('/api/v1/planning/model-status')
    assert r.json()['ready'] is True
    assert 'private-token' not in r.text and 'TEST_MODEL_SECRET' not in r.text
