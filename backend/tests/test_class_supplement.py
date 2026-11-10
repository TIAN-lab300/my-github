from test_platform import classroom,task,P
from app.core.db import transaction,one,rows


def test_late_join_supplement_preserves_original(clients):
    cid,inv=classroom(clients);tid=task(clients,cid)
    t=clients['teacher'];s=clients['student2']
    assert s.post(P+'/class-invites/'+inv['code']+'/join').status_code==200
    assert s.get(P+'/learners/me/tasks').json()==[]
    original=next(x for x in t.get(P+'/teacher/tasks').json() if x['id']==tid)
    body={'student_ids':['student2'],'expected_version':original['version']}
    url=P+f'/teacher/tasks/{tid}/supplement'
    assert clients['teacher2'].post(url,json=body).status_code==404
    assert t.post(url,json={**body,'expected_version':0}).status_code==409
    assert t.post(url,json={**body,'student_ids':['admin']}).status_code==422
    r=t.post(url,json=body);assert r.status_code==201,r.text
    new=r.json()['id']
    assert t.post(url,json=body).json()['id']==new
    assert s.get(P+'/learners/me/tasks').json()==[]
    assert t.post(P+f'/teacher/tasks/{new}/publish').status_code==200
    assert [x['id'] for x in s.get(P+'/learners/me/tasks').json()]==[new]
    with transaction() as db:
        assert len(rows(db,'SELECT * FROM assignments WHERE task_id=:id',id=tid))==1
        assert one(db,'SELECT previous_task_id FROM task_reissues WHERE task_id=:id',id=new)['previous_task_id']==tid


def test_archive_cancels_pending_load_and_keeps_history(clients):
    cid,inv=classroom(clients);tid=task(clients,cid)
    t=clients['teacher'];s=clients['student']
    finished=task(clients,cid)
    assert s.post(P+f'/tasks/{finished}/attempts',json={'answers':{'q3':'0'},'minutes':1}).status_code==200
    c=t.get(P+f'/classes/{cid}').json()
    assert t.patch(P+f'/classes/{cid}',json={'version':c['version'],'status':'archived'}).status_code==200
    with transaction() as db:
        a=one(db,'SELECT * FROM assignments WHERE task_id=:id',id=tid)
        assert a['status']=='cancelled'
        assert not rows(db,"SELECT * FROM reservations WHERE source_id=:id AND status='active'",id=a['id'])
        assert one(db,'SELECT * FROM tasks WHERE id=:id',id=tid)
        assert one(db,'SELECT * FROM assignments WHERE task_id=:id',id=finished)['status']=='completed'
        assert one(db,'SELECT at.id FROM attempts at JOIN assignments a ON a.id=at.assignment_id WHERE a.task_id=:id',id=finished)
    assert t.post(P+f'/classes/{cid}/invites',json={'max_uses':2}).status_code==409
    assert clients['student2'].post(P+'/class-invites/'+inv['code']+'/join').status_code==410
    assert t.post(P+f'/teacher/tasks/{tid}/supplement',json={'student_ids':['student'],'expected_version':2}).status_code==409
