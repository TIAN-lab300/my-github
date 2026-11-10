import pytest
from app.api import models
from app.core.db import transaction,one
from test_platform import P


def test_openai_registration_and_missing_key(clients,monkeypatch):
    admin=clients['admin']
    response=admin.post(P+'/admin/model-configs',json={'model':'gpt-test','endpoint':'https://api.openai.com/v1'})
    assert response.status_code==201,response.text
    identifier=response.json()['id']
    with transaction() as db:
        config=one(db,'SELECT * FROM model_configs WHERE id=:id',id=identifier)
    assert config['secret_env']=='OPENAI_API_KEY'
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    assert admin.post(P+f'/admin/model-configs/{identifier}/evaluate').json()['code']=='MODEL_KEY_MISSING'
    assert admin.post(P+f'/admin/model-configs/{identifier}/activate').status_code==409


@pytest.mark.parametrize('endpoint',['https://api.openai.com.evil.example/v1','http://api.openai.com/v1','https://api.openai.com/other','https://api.openai.com/v1?secret=x'])
def test_invalid_openai_endpoint_is_rejected(clients,endpoint):
    assert clients['admin'].post(P+'/admin/model-configs',json={'model':'gpt-test','endpoint':endpoint}).status_code==422


def test_openai_request_parameters(monkeypatch):
    calls=[]
    class Response:
        status_code=200
        headers={'x-request-id':'request-test'}
        def json(self):return {'choices':[{'message':{'content':'{"ok":true}'}}],'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}}
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,**kwargs):calls.append((url,kwargs));return Response()
    monkeypatch.setenv('OPENAI_API_KEY','test-only')
    monkeypatch.setattr(models.httpx,'Client',Client)
    result=models.call_model({'model':'gpt-test','endpoint':'https://api.openai.com/v1','secret_env':'OPENAI_API_KEY','max_tokens':2048,'temperature':.2},'Return JSON')
    assert result['ok'] is True
    url,request=calls[0]
    assert url=='https://api.openai.com/v1/chat/completions'
    assert request['json']['max_completion_tokens']==2048
    assert 'max_tokens' not in request['json'] and 'temperature' not in request['json']
    assert result['_provider_meta']['usage']['total_tokens']==15
