from datetime import datetime,timedelta,timezone
import json
import pytest
from app.core.db import transaction,one,rows,run
from test_platform import P,classroom,resource,task,goal,planning
import test_platform as existing

IDS=[f'SF-TASK-{n:02}' for n in range(1,11)]+[f'SF-ASSESS-{n:02}' for n in [1,2,3,4,5,7,8]]+[f'SF-PROFILE-{n:02}' for n in range(1,4)]

def create_task(clients,cid,mode='text',questions=None,recipients=None):
    body={'class_id':cid,'title':'Batch3 '+mode,'description':'Practice','due_at':(datetime.now(timezone.utc)+timedelta(days=3)).isoformat(),'minutes':10,'mode':mode,'questions':questions or [],'recipients':recipients or []}
    result=clients['teacher'].post(P+'/teacher/tasks',json=body)
    assert result.status_code==201,result.text
    return result.json()['id']

@pytest.mark.parametrize('sf',IDS)
def test_batch3(sf,clients):
    teacher=clients['teacher'];student=clients['student']
    if sf=='SF-TASK-01':
        existing.test_edit_and_targeted_assignment(clients)
    elif sf=='SF-TASK-02':
        cid,invite=classroom(clients)
        assert clients['student2'].post(P+'/class-invites/'+invite['code']+'/join').status_code==200
        tid=create_task(clients,cid,recipients=['student'])
        assert teacher.post(P+f'/teacher/tasks/{tid}/publish').status_code==200
        assert [t['id'] for t in student.get(P+'/learners/me/tasks').json()]==[tid]
        assert clients['student2'].get(P+'/learners/me/tasks').json()==[]
    elif sf=='SF-TASK-03':
        cid,_=classroom(clients);rid=resource(clients,cid)
        original=teacher.get(P+'/resources/'+rid).json()
        tid=create_task(clients,cid)
        with transaction() as db:run(db,'UPDATE tasks SET resource_id=:r WHERE id=:id',r=rid,id=tid)
        assert teacher.post(P+f'/teacher/tasks/{tid}/publish').status_code==200
        assert teacher.patch(P+'/teacher/tasks/'+tid,json={'version':2,'minutes':99}).status_code==409
        detail=teacher.get(P+'/teacher/tasks/'+tid).json()
        assert detail['resource_version_id']==original['current_version']
        with transaction() as db:assert len(rows(db,'SELECT * FROM assignments WHERE task_id=:id',id=tid))==1
    elif sf=='SF-TASK-04':
        cid,_=classroom(clients);tid=create_task(clients,cid)
        teacher.post(P+f'/teacher/tasks/{tid}/publish')
        assert student.get(P+'/learners/me/tasks',params={'status':'not_started'}).json()[0]['id']==tid
        assert student.put(P+f'/tasks/{tid}/draft',json={'text':'saved','minutes':3}).status_code==200
        result=student.get(P+'/learners/me/tasks',params={'status':'in_progress'}).json()[0]
        assert result['draft']['text']=='saved'
        assert student.get(P+'/learners/me/tasks',params={'status':'completed'}).json()==[]
        assert student.get(P+'/learners/me/tasks',params={'status':'invalid'}).status_code==422
    elif sf=='SF-TASK-05':
        cid,_=classroom(clients)
        for mode,text in [('text','answer'),('link','https://example.com/work'),('checkin','')]:
            tid=create_task(clients,cid,mode);teacher.post(P+f'/teacher/tasks/{tid}/publish')
            assert clients['student2'].post(P+f'/tasks/{tid}/attempts',json={'text':text,'minutes':5}).status_code==404
            result=student.post(P+f'/tasks/{tid}/attempts',json={'text':text,'minutes':5})
            assert result.status_code==200 and result.json()['score'] is None
        bad=create_task(clients,cid,'link');teacher.post(P+f'/teacher/tasks/{bad}/publish')
        assert student.post(P+f'/tasks/{bad}/attempts',json={'text':'https:invalid','minutes':5}).status_code==422
    elif sf=='SF-TASK-06':
        cid,_=classroom(clients);tid=task(clients,cid)
        with transaction() as db:run(db,'UPDATE tasks SET due_at=:d WHERE id=:id',d=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(),id=tid)
        assert student.get(P+'/learners/me/tasks',params={'status':'overdue'}).json()[0]['id']==tid
        submitted=student.post(P+f'/tasks/{tid}/attempts',json={'answers':{'q3':'1'},'minutes':5})
        assert submitted.status_code==200 and submitted.json()['late']==1
        first=student.get(P+'/learners/me/tasks').json()[0]['first_completed_at']
        student.post(P+f'/tasks/{tid}/attempts',json={'answers':{'q3':'0'},'minutes':8})
        assert student.get(P+'/learners/me/tasks').json()[0]['first_completed_at']==first
        assert student.get(P+'/learners/me/profile').json()['learning_behavior']['on_time_rate']==0
    elif sf=='SF-TASK-07':
        cid,_=classroom(clients)
        for action in ['withdraw','close']:
            tid=task(clients,cid)
            assert teacher.post(P+f'/teacher/tasks/{tid}/{action}').status_code==200
            assert student.post(P+f'/tasks/{tid}/attempts',json={'answers':{'q3':'1'},'minutes':5}).status_code==409
            if action=='withdraw':
                with transaction() as db:
                    assignment=one(db,'SELECT * FROM assignments WHERE task_id=:id',id=tid)
                    assert assignment['status']=='cancelled'
                    assert not rows(db,"SELECT id FROM reservations WHERE source_id=:id AND status='active'",id=assignment['id'])
    elif sf=='SF-TASK-08':
        existing.test_task_reissue_preserves_original_and_rechecks_resource(clients)
    elif sf=='SF-TASK-09':
        cid,_=classroom(clients);tid=task(clients,cid)
        student.post(P+f'/tasks/{tid}/attempts',json={'answers':{'q3':'1'},'minutes':5})
        assert teacher.get(P+'/teacher/tasks').json()[0]['submissions'][0]['attempt_id']
        assert clients['teacher2'].get(P+'/teacher/tasks/'+tid).status_code==404
        assert clients['teacher2'].get(P+'/teacher/tasks').json()==[]
    elif sf=='SF-TASK-10':
        cid,_=classroom(clients)
        with transaction() as db:run(db,'UPDATE budgets SET daily_minutes=1,weekly_minutes=1 WHERE user_id=:u',u='student')
        tid=create_task(clients,cid)
        result=teacher.post(P+f'/teacher/tasks/{tid}/publish')
        assert result.status_code==200 and result.json()['budget_conflicts']==['student']
        with transaction() as db:assert rows(db,"SELECT id FROM reservations WHERE student_id='student' AND source_type='teacher' AND status='active'")
    elif sf=='SF-ASSESS-01':
        cid,_=classroom(clients)
        questions=[{'id':kind,'kind':kind,'skill':'functions','prompt':kind,'options':['A','B'] if kind!='fill' else [],'answer':'0,1' if kind=='multi' else 'def' if kind=='fill' else '1','explanation':'rule'} for kind in ['single','boolean','fill','multi']]
        tid=create_task(clients,cid,'quiz',questions);teacher.post(P+f'/teacher/tasks/{tid}/publish')
        result=student.post(P+f'/tasks/{tid}/attempts',json={'answers':{'single':'1','boolean':'1','fill':' def ','multi':'1,0'},'minutes':5})
        assert result.status_code==200 and result.json()['score']==1
        assert result.json()['scoring_version']=='assessment-v1'
    elif sf=='SF-ASSESS-02':
        cid,_=classroom(clients);tid=task(clients,cid)
        result=student.post(P+f'/tasks/{tid}/attempts',json={'answers':{'q3':'0'},'minutes':5}).json()
        feedback=json.loads(result['feedback'])[0]
        assert all(k in feedback for k in ['answer','explanation','skill','recommendation'])
        assert student.get(P+'/learners/me/tasks').json()[0]['attempt']['feedback']==[feedback]
    elif sf in ('SF-ASSESS-03','SF-ASSESS-04','SF-ASSESS-05'):
        existing.test_subjective_review_correction_replays_evidence(clients)
        with transaction() as db:
            attempt=one(db,'SELECT * FROM attempts')
            versions=rows(db,'SELECT * FROM grades WHERE attempt_id=:id ORDER BY version',id=attempt['id'])
            assert [g['version'] for g in versions]==[1,2] and versions[1]['comment']
        assert clients['teacher2'].post(P+'/teacher/submissions/'+attempt['id']+'/review',json={'score':1,'comment':'foreign'}).status_code==404
    elif sf=='SF-ASSESS-07':
        cid,_=classroom(clients);tid=task(clients,cid)
        assert student.get(P+'/learners/me/profile').json()['mastery_state']=={}
        student.post(P+f'/tasks/{tid}/attempts',json={'answers':{'q3':'1'},'minutes':5})
        updated=student.get(P+'/learners/me/profile').json()['mastery_state']['recursion']['last_update']
        assert updated['prior']==.2 and updated['posterior']>updated['prior']
        assert updated['parameter_version']=='bkt-v1' and updated['mastery_threshold']==.75 and updated['evidence_id']
    elif sf=='SF-ASSESS-08':
        existing.test_path_practice_updates_once_and_preserves_checkin_boundary(clients)
        with transaction() as db:path=one(db,"SELECT * FROM paths WHERE status='active'")
        item=json.loads(path['tasks'])[0]['id']
        for minutes,proportion in [(0,.5),(5,-.1),(5,1.1)]:
            assert student.post(P+'/check-ins',json={'path_id':path['id'],'item_id':item,'minutes':minutes,'proportion':proportion}).status_code==422
        assert student.post(P+'/check-ins',json={'path_id':path['id'],'item_id':item,'minutes':5,'proportion':1,'difficulty':'hard','note':'review'}).status_code==200
        with transaction() as db:
            saved=one(db,'SELECT * FROM checkins WHERE path_id=:p AND item_id=:i',p=path['id'],i=item)
            assert saved['difficulty']=='hard' and saved['note']=='review'
    elif sf=='SF-PROFILE-01':
        cid,_=classroom(clients);rid=resource(clients,cid);tid=task(clients,cid)
        student.post(P+f'/resources/{rid}/study-events',json={'session_id':'filter-reading','minutes':3})
        student.post(P+f'/tasks/{tid}/attempts',json={'answers':{'q3':'1'},'minutes':4})
        read=student.get(P+'/learning-records',params={'resource_id':rid}).json()
        assert len(read['study_sessions'])==1 and read['attempts']==[]
        work=student.get(P+'/learning-records',params={'task_id':tid}).json()
        assert len(work['attempts'])==1 and work['study_sessions']==[]
        assert clients['student2'].get(P+'/learning-records',params={'resource_id':rid}).json()['study_sessions']==[]
        assert student.get(P+'/learning-records',params={'page':0}).status_code==422
    elif sf=='SF-PROFILE-02':
        cid,_=classroom(clients);rid=resource(clients,cid);task(clients,cid)
        student.post(P+f'/resources/{rid}/study-events',json={'session_id':'layer-reading','minutes':5,'completed':True})
        layers=student.get(P+'/learners/me/profile').json()['progress_layers']
        assert layers['reading']['completed']==1
        assert layers['submission']['completed']==0 and layers['mastery']['tested']==0
    elif sf=='SF-PROFILE-03':
        empty=student.get(P+'/learners/me/profile').json()['learning_behavior']
        assert empty['completion_rate'] is None and empty['on_time_rate'] is None
        existing.test_task_real_feedback_and_business_deduplication(clients)

def test_task_frozen_source_remains_readable_to_assignee(clients):
    cid,_=classroom(clients);rid=resource(clients,cid);teacher=clients['teacher'];student=clients['student']
    tid=create_task(clients,cid)
    with transaction() as db:run(db,'UPDATE tasks SET resource_id=:r WHERE id=:id',r=rid,id=tid)
    teacher.post(P+f'/teacher/tasks/{tid}/publish')
    before=teacher.get(P+'/resources/'+rid).json()
    teacher.post(P+f'/resources/{rid}/versions',data={'expected_version':before['version']},files={'file':('new.txt',b'replacement','text/plain')})
    url=P+f"/resources/{rid}/versions/{before['current_version']}/content"
    assert student.get(url).json()['body']==before['body']
    assert clients['student2'].get(url).status_code==404
    teacher.post(P+f'/teacher/tasks/{tid}/withdraw')
    assert student.get(url).status_code==404
