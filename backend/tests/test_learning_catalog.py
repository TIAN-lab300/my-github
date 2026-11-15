import pytest
from app.services.public_catalog import import_catalog
from app.core.db import transaction,one,run,insert,now
from app.api.learning_catalog import Question,create_question,publish_question,Review
P='/api/v1'

@pytest.fixture
def bank(clients):
    import_catalog();c=clients['admin'];cid='public-C03';sid=cid+'-K001'
    versions=[]
    for phase in ('practice','diagnostic','retest'):
        for n in range(2):
            r=c.post(P+'/learning/questions',json={'course_id':cid,'skill_id':sid,'prompt':phase+str(n),'options':['正确','错误'],'answer':0,'explanation':'测试题解释','source':'隔离测试原创，不导入正式库','phase':phase})
            assert r.status_code==201,r.text
            v=r.json()['id'];assert c.post(P+'/learning/questions/'+v+'/publish',json={'confirmed':True}).status_code==200;versions.append(v)
    return cid,sid,versions

def test_learning_test_evaluation_chain(clients,bank):
    cid,sid,versions=bank;a=clients['admin'];s=clients['student']
    with transaction() as db:
        insert(db,'resources',id='teaching',owner_id='admin',scope='school',title='真实正文',description='学习',tags='知识',source_license='自编',cloud_allowed=0,kind='text',status='published',current_version='teaching-v1',created_at=now())
        insert(db,'resource_versions',id='teaching-v1',resource_id='teaching',filename='lesson.txt',bytes=1,hash='test',body='学习资料正文',parse_status='ready',index_status='indexed',created_at=now())
    link=a.post(P+f'/learning/courses/{cid}/materials',json={'skill_id':sid,'resource_id':'teaching','locator':'第1段'})
    assert link.status_code==201
    route=P+'/learning/materials/'+link.json()['id']+'/study'
    for _ in range(2):assert s.post(route,json={'session_id':'same-session','minutes':10}).status_code==200
    assert s.get(P+f'/learning/courses/{cid}/progress').json()['skills'][0]['study_minutes']==10
    payload={'course_id':cid,'skill_ids':[sid],'phase':'practice','per_skill':2}
    r=s.post(P+'/learning/assessments',json=payload);assert r.status_code==201
    ident=r.json()['id'];route=P+'/learning/assessments/'+ident
    paper=s.get(route).json();assert all('answer' not in q and 'explanation' not in q for q in paper['questions'])
    assert clients['student2'].get(route).status_code==404
    answers={q['id']:0 for q in paper['questions']}
    assert s.put(route+'/draft',json={'answers':answers}).status_code==200
    assert s.get(route).json()['draft_answers']==answers
    for _ in range(2):assert s.post(route+'/submit',json={'answers':answers}).status_code==200
    result=s.get(route).json();assert result['evaluation']['score']==100 and result['skill_evaluations'][0]['evidence_count']==2
    with transaction() as db:assert one(db,'SELECT COUNT(*) n FROM learning_responses')['n']==2
    answers[next(iter(answers))]=1
    assert s.post(route+'/submit',json={'answers':answers}).status_code==409

def test_coverage_retest_and_disabled_versions(clients,bank):
    cid,sid,versions=bank;s=clients['student']
    assert s.post(P+'/learning/assessments',json={'course_id':cid,'skill_ids':[sid],'per_skill':3}).status_code==409
    r=s.post(P+'/learning/assessments',json={'course_id':cid,'skill_ids':[sid],'phase':'retest','per_skill':2});assert r.status_code==201
    assert s.post(P+'/learning/assessments',json={'course_id':cid,'skill_ids':[sid],'phase':'retest','per_skill':2}).status_code==409
    route=P+'/learning/assessments/'+r.json()['id'];paper=s.get(route).json()
    assert clients['admin'].post(P+'/learning/questions/'+versions[-1]+'/disable').status_code==200
    assert s.post(route+'/submit',json={'answers':{q['id']:0 for q in paper['questions']}}).status_code==409
    with transaction() as db:assert one(db,'SELECT COUNT(*) n FROM learning_responses')['n']==0

def test_course_constraints_and_authorization(clients,bank):
    cid,sid,_=bank;a=clients['admin'];s=clients['student']
    body={'course_id':cid,'skill_id':'public-C01-K001','prompt':'题目','options':['A','B'],'answer':0,'explanation':'解析','source':'原创'}
    assert a.post(P+'/learning/questions',json=body).status_code==422
    body['skill_id']=sid
    assert s.post(P+'/learning/questions',json=body).status_code==403
    assert a.post(P+f'/learning/courses/{cid}/materials',json={'skill_id':sid,'resource_id':'public-source-S03'}).status_code==409
    assert a.post(P+f'/learning/courses/{cid}/chapters',json={'title':'算法基础','position':0,'skill_ids':[sid]}).status_code==201
    assert a.post(P+f'/learning/courses/{cid}/chapters',json={'title':'重复','position':0,'skill_ids':[sid]}).status_code==409
    assert s.post(P+'/learning/assessments',json={'course_id':cid,'skill_ids':['public-C01-K001']}).status_code==422

def test_drafts_never_become_questions(clients):
    import_catalog()
    assert clients['student'].post(P+'/learning/assessments',json={'course_id':'public-C03','skill_ids':['public-C03-K001']}).status_code==409
    assert clients['student'].post(P+'/learning/assessments',json={'course_id':'public-C17','skill_ids':['public-C17-K001']}).status_code==409
