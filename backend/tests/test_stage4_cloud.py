"""Tests for bounded cloud evidence and actionable provider errors."""
import pytest
from fastapi import HTTPException
from app.core.db import transaction,one
from app.api import models
from app.services.cloud_planning import authorized_sources
from test_platform import classroom,P


def test_cloud_sends_only_cited_tail_fragment(clients):
    cid,_=classroom(clients)
    teacher=clients['teacher']
    body='无关开头'*1600+'递归函数必须有基本情况。'
    response=teacher.post(P+'/resources',data={'description':'函数资料','tags':'递归','source_license':'自编','class_id':cid,'cloud_allowed':'true'},files=[('files',('tail.txt',body.encode(),'text/plain'))])
    assert response.status_code==201,response.text
    rid=response.json()[0]['id']
    assert teacher.post(P+'/resources/'+rid+'/publish').status_code==200
    with transaction() as db:
        resource=one(db,'SELECT * FROM resources WHERE id=:id',id=rid)
        version=one(db,'SELECT * FROM resource_versions WHERE id=:id',id=resource['current_version'])
        student=one(db,"SELECT * FROM users WHERE username='student'")
    start=version['body'].index('递归函数')
    state={'actor':student,'execution':[{'skill_id':'recursion'}],
           'sources':[{'resource_id':rid,'version_id':version['id'],'supported_skills':['recursion'],
                       'locations':[{'skill':'recursion','start':start,'end':start+len('递归函数必须有基本情况。')}]}]}
    result=authorized_sources(state)
    assert len(result)==1
    assert result[0]['excerpt']=='递归函数必须有基本情况。'
    assert '无关开头' not in str(result)
    assert result[0]['locations'][0]['start']==start
    assert len(result[0]['excerpt_sha256'])==64


@pytest.mark.parametrize('status,code',[(400,'MODEL_REQUEST_INVALID'),(404,'MODEL_NOT_FOUND'),(413,'MODEL_CONTEXT_TOO_LONG'),(503,'MODEL_PROVIDER_UNAVAILABLE')])
def test_provider_errors_are_specific_without_response_leak(monkeypatch,status,code):
    class Response:
        status_code=status
        def json(self):return {'error':{'message':'secret-provider-detail'}}
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,*args,**kwargs):return Response()
    monkeypatch.setenv('TEST_CLOUD_KEY','test-only')
    monkeypatch.setattr(models.httpx,'Client',Client)
    with pytest.raises(HTTPException) as error:
        models.call_model({'model':'qwen-plus','endpoint':'https://dashscope.aliyuncs.com/compatible-mode/v1','secret_env':'TEST_CLOUD_KEY'},'JSON')
    assert error.value.detail['code']==code
    assert 'secret-provider-detail' not in str(error.value.detail)
