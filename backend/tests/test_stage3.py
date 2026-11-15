"""Stage three acceptance through authenticated HTTP entry points."""
import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from app.core.db import transaction, one, rows, run, insert, uid, now, dump
from app.services.assessment_sessions import recover_history
from test_platform import P
from test_stage2 import setup_item


def question(index=0):
    prompts = ['函数执行到return后会发生什么？', '函数没有返回语句时返回什么？', '函数定义中的参数用于什么？', '函数调用时传入的值叫什么？']
    return dict(skill='functions',prompt=prompts[index],options=['正确选项','错误选项'],answer='0',explanation='这是经核对的测试用答案解析。',group='functions-基础',source='隔离测试',difficulty='medium',purpose='both',family='')


def publish(clients,index=0,body=None):
    response=clients['teacher'].post(P+'/question-bank',json=body or question(index))
    assert response.status_code==200,response.text
    id=response.json()['id']
    assert clients['teacher'].post(P+f'/question-bank/{id}/review',json={'action':'submit'}).status_code==200
    for action in ('approve','publish'):
        response=clients['admin'].post(P+f'/question-bank/{id}/review',json={'action':action,'comment':'测试人员核对答案解析'})
        assert response.status_code==200,response.text
    return id


def setup(clients):
    goal,path,item=setup_item(clients)
    return goal,path,item,P+f'/paths/{path}/items/{item["id"]}'


def begin(student,url):
    response=student.post(url+'/sessions')
    assert response.status_code==200,response.text
    return response.json()


def score(student,session):
    response=student.post(P+f'/assessment-sessions/{session["id"]}/submit',json={'answers':{session['questions'][0]['id']:'0'},'minutes':7})
    assert response.status_code==200,response.text
    return response.json()


def test_review_permissions_versions_and_history(clients):
    id=publish(clients)
    assert clients['student'].get(P+'/question-bank').status_code==403
    assert clients['teacher2'].put(P+'/question-bank/'+id,json=question()).status_code==404
    assert clients['teacher'].put(P+'/question-bank/'+id,json=question()).status_code==409
    assert clients['teacher'].post(P+f'/question-bank/{id}/review',json={'action':'disable','comment':'x'}).status_code==403
    newer=clients['teacher'].post(P+f'/question-bank/{id}/versions').json()['id']
    assert clients['teacher'].post(P+f'/question-bank/{id}/versions').json()['id']==newer
    assert clients['teacher'].put(P+'/question-bank/'+newer,json=question(1)).status_code==200
    assert clients['teacher'].post(P+f'/question-bank/{newer}/review',json={'action':'submit'}).status_code==200
    assert clients['admin'].post(P+f'/question-bank/{newer}/review',json={'action':'reject'}).status_code==422
    assert clients['admin'].post(P+f'/question-bank/{newer}/review',json={'action':'reject','comment':'需调整解析'}).status_code==200
    assert clients['teacher'].put(P+'/question-bank/'+newer,json=question(2)).status_code==200
    records=clients['admin'].get(P+'/question-bank').json()
    assert next(r for r in records if r['id']==newer)['previous_content']['prompt']==question()['prompt']


def test_save_resume_submit_retest_and_shortage(clients):
    first=publish(clients);second=publish(clients,1)
    _,path,item,url=setup(clients);student=clients['student']
    session=begin(student,url)
    assert session['questions'][0]['id']==first
    assert 'answer' not in session['questions'][0] and 'explanation' not in session['questions'][0]
    assert begin(student,url)['id']==session['id']
    endpoint=P+'/assessment-sessions/'+session['id']
    assert student.put(endpoint+'/answers',json={'answers':{first:'0'},'minutes':9}).status_code==200
    loaded=student.get(endpoint).json()
    assert loaded['answers']=={first:'0'} and loaded['minutes']==9
    result=score(student,loaded)
    assert result['result']['score']==1
    repeat=student.post(endpoint+'/submit',json={'answers':{first:'1'},'minutes':1}).json()
    assert repeat['result']['id']==result['result']['id']
    with transaction() as db:
        assert one(db,'SELECT count(*) AS n FROM observations WHERE attempt_id=:a',a=result['attempt_id'])['n']==1
    next_session=student.post(url+'/retests').json()
    assert next_session['previous_id']==session['id'] and next_session['questions'][0]['id']==second
    score(student,next_session)
    assert student.post(url+'/retests').status_code==409
    assert len(student.get(url+'/sessions').json())==2
    assert clients['student2'].get(endpoint).status_code==404
    assert clients['student2'].get(url+'/sessions').status_code==404


@pytest.mark.parametrize('answers',[{}, {'unknown':'0'}, {'placeholder':None}, {'placeholder':'99'}])
def test_invalid_answers_leave_no_evidence(clients,answers):
    id=publish(clients);_,_,_,url=setup(clients);student=clients['student'];session=begin(student,url)
    payload={id:v for k,v in answers.items()} if 'placeholder' in answers else answers
    response=student.post(P+f'/assessment-sessions/{session["id"]}/submit',json={'answers':payload})
    assert response.status_code==422,response.text
    with transaction() as db:
        assert one(db,'SELECT attempt_id FROM assessment_sessions WHERE id=:s',s=session['id'])['attempt_id'] is None


def test_published_snapshot_survives_new_version(clients):
    id=publish(clients);_,_,_,url=setup(clients);student=clients['student'];session=begin(student,url)
    new=clients['teacher'].post(P+f'/question-bank/{id}/versions').json()['id']
    clients['teacher'].put(P+'/question-bank/'+new,json=question(1))
    clients['teacher'].post(P+f'/question-bank/{new}/review',json={'action':'submit'})
    for action in ('approve','publish'):clients['admin'].post(P+f'/question-bank/{new}/review',json={'action':action,'comment':'核对通过'})
    result=score(student,session)
    assert result['review_questions'][0]['prompt']==question()['prompt']
    assert student.post(url+'/retests').status_code==409  # Same question identity across versions.


def test_exposure_across_paths_and_near_variants(clients):
    publish(clients,body={**question(),'family':'same-template'})
    publish(clients,body={**question(1),'family':'same-template'})
    _,_,_,url=setup(clients);student=clients['student'];score(student,begin(student,url))
    assert student.post(url+'/retests').status_code==409


def test_goal_change_invalidates_session(clients):
    publish(clients);goal,_,_,url=setup(clients);student=clients['student'];session=begin(student,url)
    with transaction() as db:run(db,'UPDATE goals SET version=version+1 WHERE id=:id',id=goal)
    endpoint=P+'/assessment-sessions/'+session['id']
    assert student.get(endpoint).json()['status']=='invalid'
    assert student.post(endpoint+'/submit',json={'answers':{session['questions'][0]['id']:'0'}}).status_code==409


def test_legacy_interface_uses_same_session(clients):
    _,_,_,url=setup(clients);student=clients['student']
    legacy=student.get(url+'/assessment').json()
    current=begin(student,url)
    assert legacy['id']==current['id']
    result=score(student,current)
    old=student.post(url+'/attempts',json={'answers':{current['questions'][0]['id']:'1'},'minutes':1})
    assert old.status_code==200 and old.json()['id']==result['attempt_id']


def test_concurrent_start_and_submit(clients):
    publish(clients);_,_,_,url=setup(clients);student=clients['student']
    with ThreadPoolExecutor(max_workers=2) as pool:
        sessions=list(pool.map(lambda _:begin(student,url),range(2)))
        assert sessions[0]['id']==sessions[1]['id']
        results=list(pool.map(lambda _:score(student,sessions[0]),range(2)))
    assert results[0]['attempt_id']==results[1]['attempt_id']
    with transaction() as db:
        assert one(db,'SELECT count(*) AS n FROM observations WHERE attempt_id=:a',a=results[0]['attempt_id'])['n']==1


def test_teacher_history_permissions(clients):
    publish(clients);_,path,_,url=setup(clients);score(clients['student'],begin(clients['student'],url))
    with transaction() as db:cid=one(db,'SELECT g.class_id FROM goals g JOIN paths p ON p.goal_id=g.id WHERE p.id=:p',p=path)['class_id']
    assert len(clients['teacher'].get(P+f'/teacher/classes/{cid}/assessment-sessions').json())==1
    assert clients['teacher2'].get(P+f'/teacher/classes/{cid}/assessment-sessions').status_code==403


def test_historical_diagnosis_exposure_recovery(clients):
    _,_,_,url=setup(clients)
    with transaction() as db:
        before=one(db,'SELECT count(*) AS n FROM observations')['n']
        recover_history(db,'student');recover_history(db,'student')
        assert one(db,"SELECT count(*) AS n FROM question_exposures WHERE source='diagnosis_snapshot'")['n']>0
        assert one(db,'SELECT count(*) AS n FROM observations')['n']==before

def test_managed_diagnostic_is_frozen(clients):
    from test_platform import classroom
    from datetime import date,timedelta
    id=publish(clients,body={**question(),'purpose':'diagnostic'})
    cid,_=classroom(clients)
    student=clients['student']
    goal=student.post(P+'/goals',json={'title':'Python函数递归','weekly_minutes':300,'due_date':(date.today()+timedelta(days=10)).isoformat(),'class_id':cid}).json()['id']
    diagnosis=student.post(P+f'/goals/{goal}/diagnoses').json()
    assert id in {q['id'] for q in diagnosis['questions']}
    assert 'answer' not in next(q for q in diagnosis['questions'] if q['id']==id)
    clients['admin'].post(P+f'/question-bank/{id}/review',json={'action':'disable','comment':'版本调整'})
    assert student.get(P+'/diagnoses/'+diagnosis['id']).json()['questions']==diagnosis['questions']

def test_scoring_invalidates_previous_replan_preview(clients):
    from test_platform import planning
    publish(clients)
    goal,_,_,url=setup(clients)
    student=clients['student']
    preview=planning(student,goal,True)
    score(student,begin(student,url))
    response=student.post(P+'/paths/'+preview+'/accept')
    assert response.status_code==409 and response.json()['code']=='STALE_PREVIEW'


def test_question_exposure_survives_new_goal_and_path(clients):
    from test_platform import classroom,resource,goal,planning
    publish(clients)
    _,_,_,url=setup(clients)
    student=clients['student']
    score(student,begin(student,url))
    cid,_=classroom(clients)
    resource(clients,cid)
    gid=goal(clients,cid)
    pid=planning(student,gid)
    assert student.post(P+'/paths/'+pid+'/accept').status_code==200
    task=next(item for item in student.get(P+'/paths/'+pid).json()['tasks'] if item['skill_id']=='functions')
    response=student.post(P+f'/paths/{pid}/items/{task["id"]}/sessions')
    assert response.status_code==409 and response.json()['code']=='QUESTION_SHORTAGE'
