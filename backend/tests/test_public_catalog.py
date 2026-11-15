import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.db import transaction,one,run
from app.services.public_catalog import import_catalog

def test_catalog_import_repeat_and_read(clients):
    result=import_catalog()
    assert result=={'courses':36,'skills':377,'created_sources':40,'skipped_sources':0,'questions_imported':0}
    assert import_catalog()['skipped_sources']==40
    assert TestClient(app).get('/api/v1/curriculum/catalog').status_code==401
    for name in ('admin','teacher','student'):
        c=clients[name];r=c.get('/api/v1/curriculum/catalog')
        assert r.status_code==200
        courses=r.json()['courses'];assert len(courses)==36
        assert sum(len(course['skills']) for course in courses)==377
        source=courses[0]['sources'][0]
        detail=c.get('/api/v1/resources/'+source['resource_id']).json()
        assert detail['kind']=='link' and detail['parse_status']=='not_applicable'
        assert '中文资料导读' in detail['body'] and '外部原文未翻译全文' in detail['body']
        assert detail['cloud_allowed'] is False
    with transaction() as db:
        assert one(db,'SELECT COUNT(*) n FROM resources')['n']==40
        assert one(db,'SELECT COUNT(*) n FROM chunks')['n']==0
        assert one(db,'SELECT COUNT(*) n FROM diagnoses')['n']==0

def test_import_does_not_overwrite_edited_resource(clients):
    import_catalog()
    with transaction() as db:run(db,"UPDATE resources SET title='用户编辑的标题' WHERE id='public-source-S01'")
    import_catalog()
    with transaction() as db:assert one(db,"SELECT title FROM resources WHERE id='public-source-S01'")['title']=='用户编辑的标题'
    assert clients['student'].post('/api/v1/resources/public-source-S01/publish').status_code==403

def test_invalid_import_rolls_back(clients,monkeypatch):
    from app.services import public_catalog
    original=public_catalog.chinese_card
    def fail_after_first(source,courses):
        if source['id']=='S02':raise ValueError('test failure')
        return original(source,courses)
    monkeypatch.setattr(public_catalog,'chinese_card',fail_after_first)
    with pytest.raises(ValueError):import_catalog()
    with transaction() as db:
        assert one(db,'SELECT COUNT(*) n FROM resources')['n']==0
        assert one(db,'SELECT COUNT(*) n FROM curriculum_catalog_courses')['n']==0
