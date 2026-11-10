from datetime import datetime,timedelta,timezone
import json
import pytest
from app.core.db import transaction,one,rows,run
from app.services.learning import bkt,QUESTIONS

P='/api/v1'

def classroom(clients):
    t=clients['teacher'];s=clients['student']
    cid=t.post(P+'/classes',json={'name':'Python班'}).json()['id']
    inv=t.post(P+f'/classes/{cid}/invites',json={'max_uses':2}).json()
    assert s.post(P+'/class-invites/'+inv['code']+'/join').status_code==200
    return cid,inv

def resource(clients,cid):
    t=clients['teacher']
    r=t.post(P+'/resources',data={'description':'函数递归调用栈教学','tags':'Python','source_license':'自编教学资料','class_id':cid},files=[('files',('notes.txt','Python函数 function def return\n递归 recursion 结束条件\n调用栈 stack 后进先出'.encode(),'text/plain'))])
    assert r.status_code==201,r.text
    id=r.json()[0]['id'];assert t.post(P+f'/resources/{id}/publish').status_code==200
    return id

def task(clients,cid):
    due=(datetime.now(timezone.utc)+timedelta(days=5)).isoformat()
    t=clients['teacher']
    r=t.post(P+'/teacher/tasks',json={'class_id':cid,'title':'练习','description':'回答递归问题','due_at':due,'minutes':20,'questions':[QUESTIONS[2]]})
    assert r.status_code==201,r.text
    id=r.json()['id'];r=t.post(P+f'/teacher/tasks/{id}/publish');assert r.status_code==200,r.text
    return id

def goal(clients,cid):
    s=clients['student'];due=(datetime.now(timezone.utc)+timedelta(days=10)).date().isoformat()
    r=s.post(P+'/goals',json={'title':'Python函数递归','weekly_minutes':300,'due_date':due,'class_id':cid})
    assert r.status_code==201,r.text
    gid=r.json()['id'];d=s.post(P+f'/goals/{gid}/diagnoses').json()
    r=s.post(P+f"/diagnoses/{d['id']}/submit",json={'answers':{q['id']:str((int(q['answer'])+1)%len(q['options'])) for q in QUESTIONS},'minutes':5})
    assert r.status_code==200,r.text
    return gid

def planning(s,gid,replan=False):
    import uuid
    r=s.post(P+f'/goals/{gid}/'+('replan-previews' if replan else 'planning-runs'),headers={'Idempotency-Key':uuid.uuid4().hex})
    assert r.status_code==202,r.text
    result=s.get(P+'/runs/'+r.json()['run_id']).json()
    assert result['status']=='succeeded',result
    return result['result_id']

def test_auth_password_lifecycle_and_csrf(clients):
    admin=clients['admin'];s=clients['student']
    assert s.get(P+'/admin/users').status_code==403
    assert s.post(P+'/auth/logout',headers={'Origin':'https://evil.example'}).status_code==403
    r=admin.post(P+'/admin/users',json={'username':'newstudent','name':'新学生','role':'student','password':'TemporaryPassword!1'})
    assert r.status_code==201
    from fastapi.testclient import TestClient
    from app.main import app
    c=TestClient(app)
    assert c.post(P+'/auth/login',json={'username':'newstudent','password':'TemporaryPassword!1'}).json()['must_change']==1
    assert c.get(P+'/resources').status_code==403
    assert c.post(P+'/auth/change-password',json={'old_password':'TemporaryPassword!1','new_password':'OwnPassword!2','confirm_password':'OwnPassword!2'}).status_code==200
    assert c.get(P+'/auth/me').status_code==401
    assert c.post(P+'/auth/login',json={'username':'newstudent','password':'OwnPassword!2'}).status_code==200

def test_reset_and_disable_revoke_sessions(clients):
    admin=clients['admin'];s=clients['student']
    assert admin.post(P+'/admin/users/student/reset-password').status_code==200
    assert s.get(P+'/auth/me').status_code==401
    assert admin.post(P+'/admin/users/teacher/disable').status_code==200
    assert clients['teacher'].get(P+'/auth/me').status_code==401

def test_invites_are_hashed_idempotent_and_scoped(clients):
    cid,inv=classroom(clients)
    assert clients['student'].post(P+'/class-invites/'+inv['code']+'/join').json()['already_joined']
    assert clients['teacher2'].get(P+'/classes/'+cid).status_code==403
    assert clients['student2'].get(P+'/classes/'+cid).status_code==404
    with transaction() as db:
        i=one(db,'SELECT * FROM invites WHERE id=:id',id=inv['id']);assert i['used']==1 and i['code_hash']!=inv['code']
    clients['teacher'].post(P+f"/classes/{cid}/invites/{inv['id']}/revoke")
    assert clients['student2'].post(P+'/class-invites/'+inv['code']+'/join').status_code==410

def test_resource_permission_search_and_idempotent_reading(clients):
    cid,_=classroom(clients);rid=resource(clients,cid);s=clients['student']
    assert clients['student2'].get(P+f'/resources/{rid}/download').status_code==404
    found=s.post(P+'/retrieval/search',json={'query':'递归'}).json();assert found['results'][0]['resource_id']==rid
    assert clients['student2'].post(P+'/retrieval/search',json={'query':'递归'}).json()['results']==[]
    for minutes in (12,20):
        assert s.post(P+f'/resources/{rid}/study-events',json={'session_id':'stable-session-123','minutes':minutes}).status_code==200
    assert s.get(P+'/learners/me/profile').json()['learning_behavior']['actual_minutes']==20
    clients['teacher'].post(P+f'/resources/{rid}/withdraw')
    assert s.get(P+f'/resources/{rid}').status_code==404

def test_task_real_feedback_and_business_deduplication(clients):
    cid,_=classroom(clients);tid=task(clients,cid);s=clients['student']
    task_dto=s.get(P+'/learners/me/tasks').json()[0]
    assert 'answer' not in task_dto['questions'][0] and 'explanation' not in task_dto['questions'][0]
    payload={'answers':{'q3':'1'},'minutes':15}
    r=s.post(P+f'/tasks/{tid}/attempts',json=payload);assert r.status_code==200,r.text
    assert r.json()['score']==1
    assert s.post(P+f'/tasks/{tid}/attempts',json=payload,headers={'Idempotency-Key':'different'}).json()['id']==r.json()['id']
    p=s.get(P+'/learners/me/profile').json()
    assert p['learning_behavior']['completed']==1 and p['evidence_quality']['valid_observations']==1
    projection=clients['teacher'].get(P+f'/teacher/classes/{cid}/profile').json()
    assert projection['task_metrics']['completion_rate']==1

def test_subjective_review_correction_replays_evidence(clients):
    cid,_=classroom(clients);t=clients['teacher'];s=clients['student'];due=(datetime.now(timezone.utc)+timedelta(days=3)).isoformat()
    body={'class_id':cid,'title':'简答','description':'解释递归','due_at':due,'minutes':10,'questions':[{'id':'subject','skill':'recursion','prompt':'解释递归边界','kind':'subjective'}]}
    tid=t.post(P+'/teacher/tasks',json=body).json()['id'];t.post(P+f'/teacher/tasks/{tid}/publish')
    a=s.post(P+f'/tasks/{tid}/attempts',json={'answers':{'subject':'基本情况结束调用'},'minutes':10}).json()
    assert a['status']=='pending_review'
    assert not s.get(P+'/learners/me/profile').json()['mastery_state']
    assert t.post(P+f"/teacher/submissions/{a['id']}/review",json={'score':1,'comment':'符合rubric'}).status_code==200
    assert t.post(P+f"/teacher/submissions/{a['id']}/review",json={'score':0,'comment':'更正：未能解释基本情况'}).status_code==200
    m=s.get(P+'/learners/me/profile').json()['mastery_state']['recursion']
    assert m['evidence_count']==1 and m['probability']==pytest.approx(bkt(.2,False))

def test_full_planning_accept_reject_and_stale_preview(clients):
    cid,_=classroom(clients);resource(clients,cid);gid=goal(clients,cid);s=clients['student']
    pid=planning(s,gid)
    p=s.get(P+'/paths/'+pid).json();assert p['validation']['is_valid'] and len(p['tasks'])==3
    assert s.post(P+f'/paths/{pid}/accept').status_code==200
    original=pid
    preview=planning(s,gid,True)
    assert s.post(P+f'/paths/{preview}/reject').status_code==200
    assert s.get(P+'/paths/'+original).json()['status']=='active'
    preview=planning(s,gid,True)
    b=s.get(P+'/learners/me/budget').json();b['daily_minutes']+=1
    assert s.patch(P+'/learners/me/budget',json=b).status_code==200
    assert s.post(P+f'/paths/{preview}/accept').status_code==409
    p=s.get(P+'/paths/'+original).json()
    assert s.post(P+'/check-ins',json={'path_id':original,'item_id':p['tasks'][1]['id'],'minutes':10,'proportion':1}).status_code==409

def test_missing_sources_do_not_create_verified_path(clients):
    cid,_=classroom(clients);gid=goal(clients,cid);s=clients['student']
    r=s.post(P+f'/goals/{gid}/planning-runs',headers={'Idempotency-Key':'missing-evidence'})
    result=s.get(P+'/runs/'+r.json()['run_id']).json()
    assert result['status']=='failed' and result['result_id'] is None

def test_private_goal_excluded_from_teacher_projection(clients):
    cid,_=classroom(clients);s=clients['student'];due=(datetime.now(timezone.utc)+timedelta(days=3)).date().isoformat()
    s.post(P+'/goals',json={'title':'私人学习目标Python','due_date':due,'weekly_minutes':60})
    p=clients['teacher'].get(P+f'/teacher/classes/{cid}/students/student/profile').json()
    assert p['learning_context']['goals']==[]
    first=s.get(P+'/learners/me/profile').json();second=s.get(P+'/learners/me/profile').json()
    assert first['snapshot_id']==second['snapshot_id']

def test_bkt_reference():
    assert bkt(.62,False)==pytest.approx(.34293948,abs=1e-7)

def test_model_missing_secret_is_explicit(clients):
    admin=clients['admin']
    r=admin.post(P+'/admin/model-configs',json={'model':'qwen-plus','secret_env':'ZHIXING_NONEXISTENT_KEY'})
    assert r.status_code==201
    assert admin.post(P+f"/admin/model-configs/{r.json()['id']}/evaluate").status_code==503
    assert admin.post(P+f"/admin/model-configs/{r.json()['id']}/activate").status_code==409

def test_path_practice_updates_once_and_preserves_checkin_boundary(clients):
    cid,_=classroom(clients);resource(clients,cid);gid=goal(clients,cid);s=clients['student']
    pid=planning(s,gid);s.post(P+f'/paths/{pid}/accept')
    item=s.get(P+'/paths/'+pid).json()['tasks'][0]['id']
    before=s.get(P+'/learners/me/profile').json()['evidence_quality']['valid_observations']
    r=s.post(P+'/check-ins',json={'path_id':pid,'item_id':item,'minutes':20,'proportion':1})
    assert r.status_code==200,r.text
    assert s.get(P+'/learners/me/profile').json()['evidence_quality']['valid_observations']==before
    q=s.get(P+f'/paths/{pid}/items/{item}/assessment').json()['questions'][0]
    for _ in range(2):
        r=s.post(P+f'/paths/{pid}/items/{item}/attempts',json={'answers':{q['id']:'0'},'minutes':4})
        assert r.status_code==200,r.text
    assert s.get(P+'/learners/me/profile').json()['evidence_quality']['valid_observations']==before+1

def test_graph_cycle_and_draft_edit_guard(clients):
    admin=clients['admin']
    r=admin.post(P+'/admin/graphs',json={'nodes':[{'id':'a','minutes':10},{'id':'b','minutes':20}],'edges':[['a','b'],['b','a']]})
    assert r.status_code==422
    assert admin.post(P+'/admin/graphs',json={'nodes':[{'id':'a','minutes':10},{'id':'b','minutes':20}],'edges':[['a','b']]}).status_code==201
    cid,_=classroom(clients);tid=task(clients,cid)
    assert clients['teacher'].patch(P+'/teacher/tasks/'+tid,json={'version':2,'title':'不允许改发布题目'}).status_code==409

def test_backup_restore_and_restart_persistence(clients):
    from app.cli import backup,restore
    from app.core.db import DATA
    from fastapi.testclient import TestClient
    from app.main import app
    cid,_=classroom(clients);rid=resource(clients,cid)
    destination=DATA/'backup-test';restored=DATA/'restored-test'
    backup(destination);restore(destination,restored)
    assert (restored/'zhixing.db').is_file()
    with TestClient(app) as client:
        assert client.post(P+'/auth/login',json={'username':'student','password':'TestPassword123!'}).status_code==200
        assert client.get(P+'/resources/'+rid).json()['title']=='notes.txt'

def test_edit_and_targeted_assignment(clients):
    cid,_=classroom(clients);t=clients['teacher'];s=clients['student']
    due=(datetime.now(timezone.utc)+timedelta(days=3)).isoformat()
    tid=t.post(P+'/teacher/tasks',json={'class_id':cid,'title':'草稿','description':'定向任务','due_at':due,'minutes':20,'mode':'text'}).json()['id']
    assert t.patch(P+'/teacher/tasks/'+tid,json={'version':1,'recipients':['teacher2']}).status_code==422
    assert t.patch(P+'/teacher/tasks/'+tid,json={'version':1,'due_at':'2000-01-01T00:00:00+00:00'}).status_code==422
    assert t.patch(P+'/teacher/tasks/'+tid,json={'version':1,'title':'修订任务','recipients':['student']}).status_code==200
    assert t.patch(P+'/teacher/tasks/'+tid,json={'version':1,'title':'旧版本'}).status_code==409
    assert t.post(P+f'/teacher/tasks/{tid}/publish').status_code==200
    assert len(s.get(P+'/learners/me/tasks').json())==1
    assert clients['student2'].get(P+'/learners/me/tasks').json()==[]
    rid=resource(clients,cid)
    r=t.get(P+'/resources/'+rid).json()
    assert t.patch(P+'/resources/'+rid,json={'version':r['version'],'title':'修订资料','cloud_allowed':False}).status_code==200
    assert s.get(P+'/resources/'+rid).json()['title']=='修订资料'

def test_resource_version_replacement_is_atomic_and_requires_publication(clients):
    cid,_=classroom(clients);rid=resource(clients,cid);t=clients['teacher'];s=clients['student']
    original=t.get(P+'/resources/'+rid).json()
    url=P+f'/resources/{rid}/versions'
    assert t.post(url,data={'expected_version':original['version']},files={'file':('bad.txt',b'\xff','text/plain')}).status_code==422
    assert s.get(P+'/resources/'+rid).json()['current_version']==original['current_version']
    r=t.post(url,data={'expected_version':original['version']},files={'file':('new.txt','修订函数递归调用栈'.encode(),'text/plain')})
    assert r.status_code==201,r.text
    assert s.get(P+'/resources/'+rid).status_code==404
    assert t.post(url,data={'expected_version':original['version']},files={'file':('old.txt',b'old','text/plain')}).status_code==409
    versions=t.get(url).json();assert len(versions)==2
    assert any(v['id']==original['current_version'] for v in versions)
    assert t.post(P+f'/resources/{rid}/publish').status_code==200
    assert s.get(P+'/resources/'+rid).json()['body']=='修订函数递归调用栈'
    assert clients['student2'].get(url).status_code in (403,404)

def test_profile_refresh_failure_preserves_valid_snapshot(clients,monkeypatch):
    from app.api import profiles
    s=clients['student'];cid,_=classroom(clients)
    saved=s.get(P+'/learners/me/profile').json()
    with transaction() as db:
        assert one(db,"SELECT count(*) AS n FROM profile_refresh_events WHERE student_id='student' AND status='processed'")['n']>0
        from app.core.db import touch
        touch(db,'student')
    def broken(*args,**kwargs): raise RuntimeError('injected refresh failure')
    monkeypatch.setattr(profiles,'calculate',broken)
    result=s.post(P+'/learners/me/profile/refresh').json()
    assert result['snapshot_id']==saved['snapshot_id'] and result['data_quality']['status']=='stale'
    assert s.get(P+'/learners/me/profile/refresh-events').json()[0]['status']=='failed'
    monkeypatch.undo()
    current=s.post(P+'/learners/me/profile/refresh').json()
    assert current['data_quality']['status']=='current'
    assert s.get(P+'/learners/me/profile/refresh-events').json()[0]['status']=='processed'

def test_preferences_and_weekday_validation(clients):
    s=clients['student'];assert s.patch(P+'/users/me',json={'name':'新姓名'}).status_code==200
    assert s.get(P+'/auth/me').json()['name']=='新姓名'
    budget=s.get(P+'/learners/me/budget').json()
    budget['days']=[];assert s.patch(P+'/learners/me/budget',json=budget).status_code==422
    budget['days']=[0,2,4];assert s.patch(P+'/learners/me/budget',json=budget).status_code==200
    assert s.get(P+'/learners/me/budget').json()['days']==[0,2,4]

def test_persistent_profile_worker_and_record_filters(clients):
    from app.services.profile_worker import drain_once
    cid,_=classroom(clients);rid=resource(clients,cid);s=clients['student']
    assert s.post(P+f'/resources/{rid}/study-events',json={'session_id':'filter-session-001','minutes':17}).status_code==200
    assert drain_once()>=1
    events=s.get(P+'/learners/me/profile/refresh-events').json()
    assert all(e['status']=='processed' for e in events)
    assert drain_once()==0
    reading=s.get(P+'/learning-records',params={'source':'reading','class_id':cid}).json()
    assert len(reading['study_sessions'])==1 and reading['attempts']==[]
    assert s.get(P+'/learning-records',params={'source':'assessment'}).json()['study_sessions']==[]
    assert clients['student2'].get(P+'/learning-records',params={'class_id':cid}).json()['study_sessions']==[]
    assert s.get(P+'/learning-records',params={'start':'2099-01-01'}).json()['study_sessions']==[]
    assert s.get(P+'/learning-records',params={'source':'reading','page':2}).json()['study_sessions']==[]
    assert s.get(P+'/learning-records',params={'start':'wrong'}).status_code==422
    assert s.get(P+'/learning-records',params={'start':'2026-11-03','end':'2026-11-01'}).status_code==422

def test_diagnostic_draft_and_equivalent_retest(clients):
    from app.services.diagnostic_bank import RETEST
    cid,_=classroom(clients);resource(clients,cid);gid=goal(clients,cid);s=clients['student']
    assert s.post(P+f'/goals/{gid}/diagnoses/retest').status_code==409
    pid=planning(s,gid);assert s.post(P+f'/paths/{pid}/accept').status_code==200
    item=s.get(P+'/paths/'+pid).json()['tasks'][0]['id']
    assert s.post(P+'/check-ins',json={'path_id':pid,'item_id':item,'minutes':12,'proportion':1}).status_code==200
    r=s.post(P+f'/goals/{gid}/diagnoses/retest');assert r.status_code==201,r.text
    did=r.json()['id']
    assert s.post(P+f'/goals/{gid}/diagnoses/retest').json()['id']==did
    qs=s.get(P+'/diagnoses/'+did).json()['questions']
    assert len(qs)==6 and all('answer' not in q for q in qs)
    assert s.put(P+f'/diagnoses/{did}/draft',json={'bad':'0'}).status_code==422
    assert s.put(P+f'/diagnoses/{did}/draft',json={qs[0]['id']:'99'}).status_code==422
    partial={qs[0]['id']:'0'}
    assert s.put(P+f'/diagnoses/{did}/draft',json=partial).status_code==200
    assert s.get(P+'/diagnoses/'+did).json()['draft_answers']==partial
    assert clients['student2'].get(P+'/diagnoses/'+did).status_code==404
    count=s.get(P+'/learners/me/profile').json()['evidence_quality']['valid_observations']
    payload={'answers':{q['id']:q['answer'] for q in RETEST},'minutes':5}
    a=s.post(P+f'/diagnoses/{did}/submit',json=payload);assert a.status_code==200,a.text
    assert s.post(P+f'/diagnoses/{did}/submit',json=payload).json()['id']==a.json()['id']
    assert s.get(P+'/learners/me/profile').json()['evidence_quality']['valid_observations']==count+6
    assert s.put(P+f'/diagnoses/{did}/draft',json=partial).status_code==409
    assert s.post(P+f'/goals/{gid}/diagnoses/retest').status_code==409
    assert len(s.get(P+f'/goals/{gid}/diagnoses').json())==2

def test_task_reissue_preserves_original_and_rechecks_resource(clients):
    cid,_=classroom(clients);rid=resource(clients,cid);t=clients['teacher']
    payload={'class_id':cid,'title':'关联练习','description':'阅读后作答','due_at':(datetime.now(timezone.utc)+timedelta(days=3)).isoformat(),'minutes':10,'questions':[QUESTIONS[0]],'resource_id':rid}
    bad={**payload,'questions':[{**QUESTIONS[0],'answer':'99'}]}
    assert t.post(P+'/teacher/tasks',json=bad).status_code==422
    tid=t.post(P+'/teacher/tasks',json=payload).json()['id']
    t.post(P+f'/resources/{rid}/withdraw')
    assert t.post(P+f'/teacher/tasks/{tid}/publish').status_code in (404,409)
    t.post(P+f'/resources/{rid}/publish')
    assert t.post(P+f'/teacher/tasks/{tid}/publish').status_code==200
    assert t.post(P+f'/teacher/tasks/{tid}/reissue').status_code==409
    t.post(P+f'/teacher/tasks/{tid}/withdraw')
    r=t.post(P+f'/teacher/tasks/{tid}/reissue');assert r.status_code==200,r.text
    new_id=r.json()['id'];assert new_id!=tid
    assert t.get(P+'/teacher/tasks/'+tid).json()['status']=='revoked'
    assert t.get(P+'/teacher/tasks/'+new_id).json()['status']=='draft'
    assert clients['teacher2'].post(P+f'/teacher/tasks/{tid}/reissue').status_code==404
