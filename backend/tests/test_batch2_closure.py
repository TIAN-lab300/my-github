import pytest
from app.core.db import transaction,one,rows,run
from test_platform import P,classroom,resource,task

def test_sf_account_01_initialize_is_idempotent(capsys):
    from app.cli import initialize
    with transaction() as db:
        run(db,"DELETE FROM users WHERE username='admin'")
    initialize()
    capsys.readouterr()
    with transaction() as db:
        before=one(db,"SELECT * FROM users WHERE username='admin'")
        assert before['role']=='admin' and before['must_change']==1
    initialize()
    initialize()
    with transaction() as db:
        after=one(db,"SELECT * FROM users WHERE username='admin'")
        assert before==after
        assert len(rows(db,"SELECT id FROM users WHERE username='admin'"))==1
    assert 'TestPassword123!' not in capsys.readouterr().out

def test_sf_account_04_validation_and_persistence(clients):
    student=clients['student']
    for name in ['', ' ', 'a'*81]:
        assert student.patch(P+'/users/me',json={'name':name}).status_code==422
    assert student.patch(P+'/users/me',json={'name':'Verified Student','role':'admin'}).status_code==200
    current=student.get(P+'/auth/me').json()
    assert current['name']=='Verified Student' and current['role']=='student'
    assert student.get(P+'/admin/users').status_code==403

@pytest.mark.parametrize('operation',['leave','remove'])
def test_sf_class_07_cancels_only_unfinished(clients,operation):
    cid,_=classroom(clients);rid=resource(clients,cid);pending=task(clients,cid);finished=task(clients,cid)
    student=clients['student']
    assert student.post(P+f'/tasks/{finished}/attempts',json={'answers':{'q3':'1'},'minutes':5}).status_code==200
    if operation=='leave':
        response=student.post(P+f'/classes/{cid}/leave')
    else:
        response=clients['teacher'].delete(P+f'/classes/{cid}/members/student')
    assert response.status_code==200
    assert student.get(P+f'/resources/{rid}/download').status_code==404
    assert student.post(P+f'/tasks/{pending}/attempts',json={'answers':{'q3':'1'},'minutes':5}).status_code==404
    with transaction() as db:
        assert one(db,'SELECT status FROM assignments WHERE task_id=:id',id=pending)['status']=='cancelled'
        assert one(db,'SELECT status FROM assignments WHERE task_id=:id',id=finished)['status']=='completed'
        assert one(db,'SELECT at.id FROM attempts at JOIN assignments a ON at.assignment_id=a.id WHERE a.task_id=:id',id=finished)
        assert not rows(db,"SELECT r.id FROM reservations r JOIN assignments a ON a.id=r.source_id WHERE a.task_id=:id AND r.status='active'",id=pending)

def test_sf_resource_08_download_and_secret_fields(clients):
    cid,_=classroom(clients);rid=resource(clients,cid)
    student=clients['student'];url=P+f'/resources/{rid}'
    detail=student.get(url).json()
    for secret in ('storage_key','password_hash','token_hash'):
        assert secret not in detail
    response=student.get(url+'/download')
    assert response.status_code==200
    assert response.headers['x-content-type-options']=='nosniff'
    assert 'attachment' in response.headers['content-disposition']
    assert response.content.decode('utf-8')==detail['body']
    clients['teacher'].post(url+'/withdraw')
    assert student.get(url+'/download').status_code==404

def test_sf_resource_11_link_review(clients):
    cid,_=classroom(clients);teacher=clients['teacher'];student=clients['student']
    payload={'class_id':cid,'title':'Reference','description':'Teacher recommendation','url':'https://example.com/course'}
    for url in ['javascript:alert(1)','ftp://example.com','https://user:password@example.com']:
        assert teacher.post(P+'/resources/links',json={**payload,'url':url}).status_code==422
    created=teacher.post(P+'/resources/links',json=payload)
    assert created.status_code==201
    target=P+'/resources/'+created.json()['id']
    assert student.get(target).status_code==404
    assert clients['teacher2'].post(target+'/publish').status_code==403
    assert teacher.post(target+'/publish').status_code==200
    detail=student.get(target).json()
    assert detail['body']=='' and detail['parse_status']=='not_applicable'
    assert detail['filename']==payload['url']
    assert not student.post(P+'/retrieval/search',json={'query':'Reference'}).json()['results']

def test_sf_resource_13_session_update_and_isolation(clients):
    cid,_=classroom(clients);rid=resource(clients,cid)
    student=clients['student'];url=P+f'/resources/{rid}/study-events'
    for minutes in [0,-1,1441]:
        assert student.post(url,json={'session_id':'reading-session','minutes':minutes}).status_code==422
    for minutes,completed in [(7,False),(17,True),(17,True)]:
        assert student.post(url,json={'session_id':'reading-session','minutes':minutes,'completed':completed}).status_code==200
    with transaction() as db:
        records=rows(db,"SELECT * FROM study_sessions WHERE id='reading-session'")
        assert len(records)==1 and records[0]['minutes']==17 and records[0]['completed']==1
    teacher=clients['teacher']
    current=teacher.get(P+'/resources/'+rid).json()
    teacher.patch(P+'/resources/'+rid,json={'version':current['version'],'title':'Original reading resource'})
    another=resource(clients,cid)
    assert another!=rid
    assert student.post(P+f'/resources/{another}/study-events',json={'session_id':'reading-session','minutes':4}).status_code==409
    assert clients['student2'].post(url,json={'session_id':'other-session','minutes':4}).status_code==404
    assert student.get(P+'/learners/me/profile').json()['learning_behavior']['actual_minutes']==17
