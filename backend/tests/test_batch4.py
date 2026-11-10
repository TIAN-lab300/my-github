from datetime import datetime,timedelta,timezone
import json
import pytest
from app.core.db import transaction,one,rows,run,touch
from app.services.learning import QUESTIONS
from test_platform import P,classroom,resource,task,goal,planning
import test_platform as existing

IDS=[f'SF-GOAL-{i:02}' for i in range(1,8)]+[f'SF-DIAG-{i:02}' for i in range(1,8)]+[f'SF-PROFILE-{i:02}' for i in range(4,10)]
def payload(**overrides):
    return {'title':'Python函数递归','weekly_minutes':300,'due_date':(datetime.now(timezone.utc)+timedelta(days=10)).date().isoformat(),**overrides}
def new_goal(client,**overrides):
    response=client.post(P+'/goals',json=payload(**overrides))
    assert response.status_code==201,response.text
    return response.json()['id']
def sheet(client,gid):
    response=client.post(P+f'/goals/{gid}/diagnoses')
    assert response.status_code==201,response.text
    return client.get(P+'/diagnoses/'+response.json()['id']).json()
def submit(client,d):
    answers={q['id']:str((int(next(x for x in QUESTIONS if x['id']==q['id'])['answer'])+1)%len(q['options'])) for q in d['questions']}
    return client.post(P+'/diagnoses/'+d['id']+'/submit',json={'answers':answers,'minutes':5})

@pytest.mark.parametrize('sf',IDS)
def test_batch4(sf,clients,monkeypatch):
    student=clients['student'];teacher=clients['teacher']
    if sf=='SF-GOAL-01':
        a=new_goal(student);b=new_goal(student,title='第二个Python目标')
        assert a!=b and len(student.get(P+'/goals').json())==2
        old=student.get(P+'/goals/'+a).json()
        assert clients['student2'].get(P+'/goals/'+a).status_code==404
        assert student.patch(P+'/goals/'+a,json={'version':old['version'],'status':'archived'}).status_code==200
        assert student.get(P+'/goals/'+a).json()['status']=='archived'
        assert student.patch(P+'/goals/'+a,json={'version':2,'title':'revive'}).status_code==409
        assert len(student.get(P+'/goals/'+a+'/history').json())==2
    elif sf=='SF-GOAL-02':
        text='在2027-01-01前掌握Python，每周3小时，偏好视频'
        parsed=student.post(P+'/goals/interpret',json={'text':text}).json()
        assert set(parsed['target_skill_ids'])=={'functions','recursion','stack'}
        assert parsed['weekly_minutes']==180 and parsed['due_date']=='2027-01-01'
        assert parsed['preference']=='video' and parsed['confirmed'] is False
        gid=new_goal(student,target_skill_ids=['functions'],preference='text',weekly_minutes=120)
        detail=student.get(P+'/goals/'+gid).json()
        assert detail['target_skill_ids']==['functions'] and detail['preference']=='text'
    elif sf=='SF-GOAL-03':
        for body in [payload(title=' '),payload(weekly_minutes=0),payload(due_date='bad'),payload(target_skill_ids=['unknown']),payload(due_date='2000-01-01')]:
            assert student.post(P+'/goals',json=body).status_code==422
        gid=new_goal(student)
        assert student.patch(P+'/goals/'+gid,json={'version':1,'weekly_minutes':0}).status_code==422
        result=student.post(P+'/goals/interpret',json={'text':'学习一些未知内容'}).json()
        assert result['needs_clarification'] and result['target_skill_ids']==[]
    elif sf=='SF-GOAL-04':
        existing.test_preferences_and_weekday_validation(clients)
        cid,_=classroom(clients);resource(clients,cid);gid=goal(clients,cid);pid=planning(student,gid)
        assert student.post(P+'/paths/'+pid+'/accept').status_code==200
        settings=student.get(P+'/learners/me/budget').json()
        assert student.patch(P+'/learners/me/budget',json={**settings,'daily_minutes':1,'weekly_minutes':1,'timezone':'America/New_York','days':[0,2,4]}).status_code==200
        second=new_goal(student)
        assert student.get(P+'/goals/'+second+'/feasibility').json()['status']=='budget_conflict'
        assert student.patch(P+'/learners/me/budget',json=settings).status_code==409
        assert student.get(P+'/paths/'+pid).json()['status']=='active'
    elif sf=='SF-GOAL-05':
        cid,_=classroom(clients);gid=new_goal(student)
        assert teacher.get(P+f'/teacher/classes/{cid}/students/student/profile').json()['learning_context']['goals']==[]
        assert student.patch(P+'/goals/'+gid,json={'version':1,'class_id':cid}).status_code==200
        assert teacher.get(P+f'/teacher/classes/{cid}/students/student/profile').json()['learning_context']['goals'][0]['id']==gid
        assert student.patch(P+'/goals/'+gid,json={'version':2,'class_id':None}).status_code==200
        assert teacher.get(P+f'/teacher/classes/{cid}/students/student/profile').json()['learning_context']['goals']==[]
        assert clients['student2'].post(P+'/goals',json=payload(class_id=cid)).status_code==404
    elif sf=='SF-GOAL-06':
        cid,_=classroom(clients);resource(clients,cid);gid=goal(clients,cid);pid=planning(student,gid)
        assert student.post(P+'/paths/'+pid+'/accept').status_code==200
        original=student.get(P+'/paths/'+pid).json()
        assert student.patch(P+'/goals/'+gid,json={'version':1,'weekly_minutes':180,'target_skill_ids':['functions']}).status_code==200
        current=next(g for g in student.get(P+'/goals').json() if g['id']==gid)
        assert current['version']==2 and current['requires_replan']
        assert student.get(P+'/paths/'+pid).json()['tasks']==original['tasks']
        assert len(student.get(P+'/goals/'+gid+'/history').json())==2
        assert student.patch(P+'/goals/'+gid,json={'version':1,'title':'stale'}).status_code==409
    elif sf=='SF-GOAL-07':
        gid=new_goal(student)
        evidence=student.get(P+'/goals/'+gid+'/feasibility').json()
        assert evidence['status']=='evidence_gap' and evidence['missing_skills']
        settings=student.get(P+'/learners/me/budget').json()
        student.patch(P+'/learners/me/budget',json={**settings,'daily_minutes':1,'weekly_minutes':1})
        budget=student.get(P+'/goals/'+gid+'/feasibility').json()
        assert budget['status']=='budget_conflict' and budget['required_minutes']==120 and budget['reasons']
        unknown=new_goal(student,title='未知主题')
        assert student.get(P+'/goals/'+unknown+'/feasibility').json()['status']=='missing_structure'
    elif sf=='SF-DIAG-01':
        gid=new_goal(student);d=sheet(student,gid)
        assert 6<=len(d['questions'])<=12
        assert set(q['skill'] for q in d['questions'])=={'functions','recursion','stack'}
        assert all(q['source']['id'] and q['version'] and q['rule_version'] for q in d['questions'])
        assert all('answer' not in q and 'explanation' not in q for q in d['questions'])
    elif sf=='SF-DIAG-02':
        gid=new_goal(student);d=sheet(student,gid)
        assert sheet(student,gid)['id']==d['id']
        assert d['coverage']['confidence']=='normal'
        assert clients['student2'].get(P+'/diagnoses/'+d['id']).status_code==404
    elif sf=='SF-DIAG-03':
        gid=new_goal(student);d=sheet(student,gid);answer={d['questions'][0]['id']:'0'}
        assert student.put(P+'/diagnoses/'+d['id']+'/draft',json=answer).status_code==200
        assert student.get(P+'/diagnoses/'+d['id']).json()['draft_answers']==answer
        assert student.get(P+'/learners/me/profile').json()['evidence_quality']['valid_observations']==0
        assert student.put(P+'/diagnoses/'+d['id']+'/draft',json={'unknown':'0'}).status_code==422
    elif sf=='SF-DIAG-04':
        gid=new_goal(student);d=sheet(student,gid)
        assert student.post(P+'/diagnoses/'+d['id']+'/submit',json={'answers':{},'minutes':5}).status_code==422
        result=submit(student,d);assert result.status_code==200
        assert submit(student,d).json()['id']==result.json()['id']
        assert student.get(P+'/learners/me/profile').json()['evidence_quality']['valid_observations']==6
        next_goal=new_goal(student);old=sheet(student,next_goal)
        student.patch(P+'/goals/'+next_goal,json={'version':1,'weekly_minutes':200})
        assert submit(student,old).status_code==409
        assert sheet(student,next_goal)['id']!=old['id']
    elif sf=='SF-DIAG-05':
        gid=new_goal(student);d=sheet(student,gid);result=submit(student,d)
        assert result.status_code==200
        decoded=student.get(P+'/diagnoses/'+d['id']).json()
        feedback=json.loads(decoded['result']['feedback'])
        assert all('correct' in f and f['explanation'] and f['skill'] for f in feedback)
        original=decoded['mastery']
        new=new_goal(student);submit(student,sheet(student,new))
        assert student.get(P+'/diagnoses/'+d['id']).json()['mastery']==original
    elif sf=='SF-DIAG-06':
        existing.test_diagnostic_draft_and_equivalent_retest(clients)
    elif sf=='SF-DIAG-07':
        gid=new_goal(student,title='未覆盖主题')
        response=student.post(P+'/goals/'+gid+'/diagnoses')
        assert response.status_code==409
        assert student.get(P+'/goals/'+gid+'/diagnoses').json()==[]
        assert student.patch(P+'/goals/'+gid,json={'version':1,'target_skill_ids':['functions']}).status_code==200
        assert len(sheet(student,gid)['questions'])==6
    elif sf=='SF-PROFILE-04':
        profile=student.get(P+'/learners/me/profile').json()
        assert all(key in profile for key in ['learning_context','learning_behavior','mastery_state','evidence_quality','risk_summary','data_quality'])
        assert teacher.get(P+'/learners/me/profile').status_code==403
        assert student.get(P+'/learners/me/profile',params={'student_id':'student2'}).json()['snapshot_id']==profile['snapshot_id']
    elif sf=='SF-PROFILE-05':
        cid,_=classroom(clients);tid=task(clients,cid)
        student.post(P+f'/tasks/{tid}/attempts',json={'answers':{'q3':'0'},'minutes':7})
        profile=teacher.get(P+f'/teacher/classes/{cid}/profile').json()
        assert profile['task_metrics']['completion_rate']==1 and profile['learning_time']==7
        assert profile['mastery_distribution']['recursion']['weak']==1
        assert profile['students'][0]['risk_summary'][0]['observed_at']
        assert clients['teacher2'].get(P+f'/teacher/classes/{cid}/profile').status_code==403
    elif sf=='SF-PROFILE-06':
        existing.test_private_goal_excluded_from_teacher_projection(clients)
        cid=teacher.get(P+'/classes').json()[0]['id']
        assert clients['teacher2'].get(P+f'/teacher/classes/{cid}/students/student/profile').status_code==403
        assert teacher.delete(P+f'/classes/{cid}/members/student').status_code==200
        assert teacher.get(P+f'/teacher/classes/{cid}/students/student/profile').status_code==404
    elif sf=='SF-PROFILE-07':
        existing.test_profile_refresh_failure_preserves_valid_snapshot(clients,monkeypatch)
    elif sf=='SF-PROFILE-08':
        before=student.get(P+'/learners/me/profile').json()
        gid=new_goal(student);d=sheet(student,gid);submit(student,d)
        after=student.get(P+'/learners/me/profile').json()
        assert after['version']>before['version'] and 'query_window' in after
        history=student.get(P+'/learners/me/profile/history').json()
        old=next(h for h in history if h['id']==before['snapshot_id'])
        assert json.loads(old['payload'])['mastery_state']=={}
        assert student.get(P+'/learners/me/profile').json()['snapshot_id']==after['snapshot_id']
    elif sf=='SF-PROFILE-09':
        unknown=student.get(P+'/learners/me/profile').json()
        assert unknown['mastery_state']=={} and unknown['risk_summary']==[]
        gid=new_goal(student);submit(student,sheet(student,gid))
        current=student.get(P+'/learners/me/profile').json()
        assert current['risk_summary'] and all(r['evidence_ids'] and r['observed_at'] for r in current['risk_summary'])

def test_class_refresh_failure_and_history_respect_goal_unlink(clients,monkeypatch):
    from app.api import profiles
    cid,_=classroom(clients);student=clients['student'];teacher=clients['teacher']
    gid=new_goal(student,class_id=cid)
    before=teacher.get(P+f'/teacher/classes/{cid}/profile').json()
    assert before['students'][0]['learning_context']['goals']
    student.patch(P+'/goals/'+gid,json={'version':1,'class_id':None})
    def broken(*args,**kwargs):raise RuntimeError('injected failure')
    monkeypatch.setattr(profiles,'calculate',broken)
    stale=teacher.get(P+f'/teacher/classes/{cid}/profile').json()
    assert stale['snapshot_id']==before['snapshot_id'] and stale['data_quality']['status']=='stale'
    assert stale['students'][0]['learning_context']['goals']==[]
    history=teacher.get(P+f'/teacher/classes/{cid}/profile/history').json()
    assert all(json.loads(h['payload'])['students'][0]['learning_context']['goals']==[] for h in history)
    assert clients['teacher2'].get(P+f'/teacher/classes/{cid}/profile').status_code==403

def test_goal_archive_preserves_completed_reservations_and_blocks_new_work(clients):
    cid,_=classroom(clients);resource(clients,cid);student=clients['student']
    gid=goal(clients,cid);pid=planning(student,gid);student.post(P+'/paths/'+pid+'/accept')
    path=student.get(P+'/paths/'+pid).json()
    with transaction() as db:
        reservation=one(db,'SELECT id FROM reservations WHERE goal_id=:g LIMIT 1',g=gid)
        run(db,"UPDATE reservations SET status='completed' WHERE id=:id",id=reservation['id'])
    assert student.patch(P+'/goals/'+gid,json={'version':1,'status':'archived'}).status_code==200
    with transaction() as db:
        assert one(db,'SELECT status FROM reservations WHERE id=:id',id=reservation['id'])['status']=='completed'
    assert student.get(P+'/paths/'+pid).status_code==200
    assert student.post(P+'/check-ins',json={'path_id':pid,'item_id':path['tasks'][0]['id'],'minutes':5,'proportion':1}).status_code==409
