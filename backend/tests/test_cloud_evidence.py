import json
import pytest
from app.core.db import transaction,one,run
from test_platform import classroom,resource,goal,P


def activate_cloud(clients,monkeypatch):
    from app.api import models
    def reply(config,prompt):
        if prompt.startswith('{') and 'case' in json.loads(prompt):
            case=json.loads(prompt)['case']
            return {'status':case['expected_status'],'tasks':[{'skill_id':case['skill_id'],'minutes':10}] if case['evidence_available'] else [],'reason':'测试契约响应'}
        if 'agent' not in prompt:return {'ok':True}
        request=json.loads(prompt);task=request['task'];agent=request['agent']
        if agent=='GoalDiagnosisAgent':return {'summary':'根据诊断安排先修知识','risks':[]}
        if agent=='PathBuildingAgent':
            return {'tasks':[{'skill_id':item['skill_id'],'minutes':item['minutes']+1,'instructions':'阅读例题并解释运行步骤','citation_version_ids':[source['version_id'] for source in task['sources'] if item['skill_id'] in source['supported_skills']]} for item in task['tasks']],'reason':'按诊断补强'}
        if agent=='PlanReviewAgent':return {'approved':True,'issues':[]}
        return {'reason':'按证据和预算安排学习','recommendations':['完成后重测']}
    monkeypatch.setattr(models,'call_model',reply)
    admin=clients['admin'];created=admin.post(P+'/admin/model-configs',json={'model':'qwen-plus'}).json()['id']
    assert admin.post(P+f'/admin/model-configs/{created}/evaluate').status_code==200
    assert admin.post(P+f'/admin/model-configs/{created}/activate').status_code==409
    monkeypatch.setenv('DASHSCOPE_API_KEY','test-only')
    from app.services.quality_evaluation import evaluate
    from app.core.db import DATA
    report=evaluate(created,DATA/(created+'-quality.json'),'contract-test')
    assert admin.post(P+f'/admin/model-configs/{created}/quality-reports/'+report['quality_report_id']+'/review',json={'approved':True,'comment':'契约测试替身，仅验证接口流程','reviewed_case_ids':[entry['case']['id'] for entry in report['results']]}).status_code==200
    assert admin.post(P+f'/admin/model-configs/{created}/activate').status_code==200
    return created,reply


def test_cloud_four_agent_entry_and_privacy(clients,monkeypatch):
    config,_=activate_cloud(clients,monkeypatch)
    cid,_=classroom(clients);rid=resource(clients,cid);gid=goal(clients,cid)
    student=clients['student'];teacher=clients['teacher']
    result=student.post(P+f'/goals/{gid}/planning-runs?engine=cloud',headers={'Idempotency-Key':'privacy'}).json()
    failed=student.get(P+'/runs/'+result['run_id']).json()
    assert failed['status']=='failed' and '授权' in failed['error']
    current=teacher.get(P+'/resources/'+rid).json()
    assert teacher.patch(P+'/resources/'+rid,json={'version':current['version'],'cloud_allowed':True}).status_code==200
    result=student.post(P+f'/goals/{gid}/planning-runs?engine=cloud',headers={'Idempotency-Key':'cloud'}).json()
    completed=student.get(P+'/runs/'+result['run_id']).json()
    assert completed['status']=='succeeded',completed
    assert len(completed['steps'])==4
    path=student.get(P+'/paths/'+completed['result_id']).json()
    assert path['validation']['cloud_called'] is True
    assert path['validation']['model_config_id']==config
    assert all(item['instructions'] for item in path['tasks'])
    assert student.post(P+'/paths/'+path['id']+'/accept').status_code==200


def test_upload_only_and_bounded_search(clients,monkeypatch):
    from app.api import evidence
    calls=[]
    monkeypatch.setattr(evidence,'search_web',lambda query:calls.append(query) or [])
    student=clients['student']
    assert student.post(P+'/retrieval/supplement',json={'query':'递归','mode':'upload_only'}).json()['rounds']==0
    assert not calls
    result=student.post(P+'/retrieval/supplement',json={'query':'递归','mode':'web_allowed'}).json()
    assert result['rounds']==2 and len(calls)==2 and result['status']=='draft'
    result=student.post(P+'/retrieval/supplement',json={'query':'递归','mode':'web_allowed','nodes':[{'id':'recursion','title':'递归','minutes':0,'question_count':0}]}).json()
    assert result['web_search_executed'] is False and len(calls)==2


def test_authorized_link_import_and_audit_result(clients,monkeypatch):
    from app.api import evidence
    cid,_=classroom(clients);teacher=clients['teacher']
    rid=teacher.post(P+'/resources/links',json={'class_id':cid,'url':'https://example.edu/lesson','title':'递归','description':'课程来源'}).json()['id']
    monkeypatch.setattr(evidence,'fetch_page',lambda url:{'url':url,'title':'递归','body':'递归函数需要终止条件，这是教师授权导入的课程正文。','domain':'example.edu','published_at':None})
    current=teacher.get(P+'/resources/'+rid).json()
    url=P+'/resources/'+rid+'/import-link'
    assert clients['student'].post(url,json={'authorized':True,'version':current['version']}).status_code==403
    assert teacher.post(url,json={'authorized':False,'version':current['version']}).status_code==422
    assert teacher.post(url,json={'authorized':True,'version':current['version']}).status_code==201
    assert not clients['student'].post(P+'/retrieval/search',json={'query':'递归'}).json()['results']
    assert teacher.post(P+'/resources/'+rid+'/publish').status_code==200
    assert clients['student'].post(P+'/retrieval/search',json={'query':'递归'}).json()['results']
    assert not clients['student2'].post(P+'/retrieval/search',json={'query':'递归'}).json()['results']
    clients['student'].post(P+'/auth/login',json={'username':'student','password':'bad'})
    logs=clients['admin'].get(P+'/admin/audit?result=failed').json()
    assert logs and all(log['result']=='failed' for log in logs)


@pytest.mark.parametrize('url',['http://127.0.0.1/','http://[::1]/','http://169.254.169.254/','https://user:pass@example.com/','file:///etc/passwd'])
def test_fetch_rejects_private_and_credential_urls(url):
    from app.services.web_evidence import public_target
    with pytest.raises(ValueError):public_target(url)
