import pytest
from app.api import models
from app.core.db import transaction,one
from test_platform import P


@pytest.mark.parametrize('endpoint',['https://api.deepseek.com','https://api.deepseek.com/'])
def test_deepseek_registration_and_missing_key(clients,monkeypatch,endpoint):
    admin=clients['admin']
    response=admin.post(P+'/admin/model-configs',json={'model':'deepseek-flash','endpoint':endpoint})
    assert response.status_code==201,response.text
    identifier=response.json()['id']
    with transaction() as db:
        config=one(db,'SELECT * FROM model_configs WHERE id=:id',id=identifier)
    assert config['secret_env']=='DEEPSEEK_API_KEY'
    monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
    assert admin.post(P+f'/admin/model-configs/{identifier}/evaluate').json()['code']=='MODEL_KEY_MISSING'
    assert admin.post(P+f'/admin/model-configs/{identifier}/activate').status_code==409


def test_deepseek_custom_secret_variable_is_preserved(clients):
    response=clients['admin'].post(P+'/admin/model-configs',json={'model':'deepseek-flash','endpoint':'https://api.deepseek.com','secret_env':'PROJECT_DEEPSEEK_KEY'})
    assert response.status_code==201
    with transaction() as db:
        assert one(db,'SELECT secret_env FROM model_configs WHERE id=:id',id=response.json()['id'])['secret_env']=='PROJECT_DEEPSEEK_KEY'


@pytest.mark.parametrize('endpoint',['http://api.deepseek.com','https://api.deepseek.com.evil.example','https://api.deepseek.com/beta','https://api.deepseek.com?key=x'])
def test_invalid_deepseek_endpoint_is_rejected(clients,endpoint):
    assert clients['admin'].post(P+'/admin/model-configs',json={'model':'deepseek-flash','endpoint':endpoint}).status_code==422


def test_deepseek_blank_json_repair_and_parameters(monkeypatch):
    calls=[]
    class Response:
        status_code=200
        headers={'x-request-id':'deepseek-contract'}
        def __init__(self,content):self.content=content
        def json(self):return {'choices':[{'message':{'content':self.content,'reasoning_content':'unused'}}],'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}}
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,**kwargs):
            calls.append((url,kwargs))
            return Response('   ' if len(calls)==1 else '{"ok":true}')
    monkeypatch.setenv('DEEPSEEK_API_KEY','test-only')
    monkeypatch.setattr(models.httpx,'Client',Client)
    result=models.call_model({'model':'deepseek-flash','endpoint':'https://api.deepseek.com/','secret_env':'DEEPSEEK_API_KEY','max_tokens':2048,'temperature':.2},'Return JSON')
    assert result['ok'] is True and len(calls)==2
    url,request=calls[-1]
    assert url=='https://api.deepseek.com/chat/completions'
    assert request['json']['max_tokens']==2048
    assert request['json']['thinking']=={'type':'disabled'}
    assert request['json']['response_format']=={'type':'json_object'}
    assert 'max_completion_tokens' not in request['json']
    assert 'reasoning_content' not in result
