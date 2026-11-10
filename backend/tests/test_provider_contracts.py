import json
import pytest
from fastapi import HTTPException
from app.api import models


def test_json_repairs_are_bounded(monkeypatch):
    calls=[]
    class Response:
        status_code=200
        def json(self):return {'choices':[{'message':{'content':'not JSON'}}]}
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,*args,**kwargs):calls.append(kwargs);return Response()
    monkeypatch.setenv('PROVIDER_TEST_KEY','test-only')
    monkeypatch.setattr(models.httpx,'Client',Client)
    with pytest.raises(HTTPException) as error:
        models.call_model({'secret_env':'PROVIDER_TEST_KEY','endpoint':'https://dashscope.aliyuncs.com/compatible-mode/v1','model':'qwen-plus'},'Return JSON')
    assert error.value.detail['code']=='MODEL_JSON_INVALID' and len(calls)==3


def test_native_search_requires_real_source_metadata(monkeypatch):
    from app.services import web_evidence
    calls=[]
    monkeypatch.setenv('ZHIXING_SEARCH_PROVIDER','dashscope')
    monkeypatch.setenv('DASHSCOPE_API_KEY','test-only')
    class Response:
        status_code=200
        def json(self):return {'output':{'choices':[{'message':{'content':'I searched the web'}}]}}
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,*args,**kwargs):calls.append(kwargs);return Response()
    monkeypatch.setattr(web_evidence.httpx,'Client',Client)
    with pytest.raises(ValueError,match='真实搜索来源'):
        web_evidence.search_web('Python')
    assert calls[0]['json']['parameters']['search_options']['forced_search'] is True


def test_html_publication_date_is_declared_not_invented():
    from app.services.web_evidence import PageText
    page=PageText();page.feed('<title>Guide</title><meta property="article:published_time" content="2026-11-01T09:00:00+08:00"><script>private script</script><p>Teaching content</p>')
    assert page.published_at=='2026-11-01T09:00:00+08:00'
    assert 'private script' not in page.parts
    unknown=PageText();unknown.feed('<p>No publication date</p>')
    assert unknown.published_at is None


def test_quality_evaluation_records_all_cases_without_overwrite(monkeypatch,tmp_path):
    from app.core.db import transaction,insert,now
    from app.services.quality_evaluation import evaluate
    monkeypatch.setenv('QUALITY_TEST_KEY','test-only')
    with transaction() as db:
        insert(db,'model_configs',id='quality-test',model='test-model',endpoint='https://dashscope.aliyuncs.com/compatible-mode/v1',secret_env='QUALITY_TEST_KEY',created_at=now())
    def reply(config,prompt):
        case=json.loads(prompt)['case']
        return {'status':case['expected_status'],'tasks':[{'skill_id':case['skill_id'],'minutes':10}] if case['evidence_available'] else [],'reason':'测试契约响应'}
    monkeypatch.setattr(models,'call_model',reply)
    output=tmp_path/'new-folder'/'quality.json'
    report=evaluate('quality-test',output,'contract-test')
    assert report['total']==60 and report['automated_passed']==60
    assert json.loads(output.read_text(encoding='utf-8'))['human_review']=='pending'
    with pytest.raises(ValueError,match='已存在'):evaluate('quality-test',output,'contract-test')
