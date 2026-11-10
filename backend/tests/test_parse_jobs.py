from test_platform import classroom,P
from app.core.db import transaction,one,run,DATA
from app.services.parse_worker import drain_once

def test_parse_retry_is_durable_and_authorized(clients):
    cid,_=classroom(clients);t=clients['teacher']
    response=t.post(P+'/resources',data={'description':'notes','tags':'test','source_license':'own','class_id':cid},files=[('files',('bad.txt',b'\x00','text/plain'))])
    rid=response.json()[0]['id']
    url=P+f'/resources/{rid}/retry-parse'
    first=t.post(url);assert first.status_code==200
    jid=first.json()['job_id']
    assert t.post(url).json()['job_id']==jid
    assert clients['teacher2'].get(P+f'/resources/{rid}/parse-jobs/{jid}').status_code==403
    assert t.post(P+f'/resources/{rid}/publish').status_code==409
    drain_once()
    assert t.get(P+f'/resources/{rid}/parse-jobs/{jid}').json()['status']=='failed'
    with transaction() as db:
        v=one(db,'SELECT v.* FROM resource_versions v JOIN resources r ON r.current_version=v.id WHERE r.id=:id',id=rid)
    (DATA/'files'/v['storage_key']).write_text('Recovered readable text',encoding='utf-8')
    assert t.post(url).json()['job_id']==jid
    with transaction() as db:
        run(db,"UPDATE parse_jobs SET status='running',lease_until='2000-01-01T00:00:00+00:00' WHERE id=:id",id=jid)
    drain_once()
    assert t.get(P+f'/resources/{rid}/parse-jobs/{jid}').json()['status']=='ready'
    assert t.post(P+f'/resources/{rid}/publish').status_code==200
    assert t.get(P+f'/resources/{rid}').json()['body']=='Recovered readable text'

def test_pdf_queue_and_retry_limit(clients):
    cid,_=classroom(clients);t=clients['teacher']
    r=t.post(P+'/resources',data={'description':'notes','tags':'test','source_license':'own','class_id':cid},files=[('files',('broken.pdf',b'%PDF broken','application/pdf'))])
    assert r.status_code==201
    rid=r.json()[0]['id'];assert r.json()[0]['parse_status']=='queued'
    for attempt in range(3):
        drain_once()
        response=t.post(P+f'/resources/{rid}/retry-parse')
        assert response.status_code==(409 if attempt==2 else 200)
    assert t.post(P+f'/resources/{rid}/publish').status_code==409

def test_candidate_switch_is_atomic(clients):
    from test_platform import resource
    cid,_=classroom(clients);rid=resource(clients,cid);t=clients['teacher']
    url=P+'/resources/'+rid
    old=t.get(url).json()
    def candidate(data):
        response=t.post(url+'/versions',data={'expected_version':old['version'],'background':'true'},files={'file':('new.txt',data,'text/plain')})
        assert response.status_code==201,response.text
        return response.json()
    bad=candidate(b'\xff')
    drain_once()
    assert t.get(url+'/parse-jobs/'+bad['job_id']).json()['status']=='failed'
    assert t.get(url).json()['current_version']==old['current_version']
    first=candidate(b'first');second=candidate(b'second')
    assert clients['student'].get(url).json()['body']==old['body']
    drain_once();drain_once()
    assert t.get(url).json()['current_version']==first['id']
    assert t.get(url+'/parse-jobs/'+second['job_id']).json()['status']=='failed'
    assert clients['student'].get(url).status_code==404

def test_upload_rejects_disguised_media_but_keeps_other_files(clients):
    cid,_=classroom(clients);t=clients['teacher']
    r=t.post(P+'/resources',data={'description':'notes','tags':'test','source_license':'own','class_id':cid},files=[('files',('fake.mp4',b'not a video','video/mp4')),('files',('notes.txt',b'notes','text/plain'))])
    assert r.status_code==201
    failed,ok=r.json()
    assert failed['error'] and 'id' not in failed
    assert ok['parse_status']=='ready' and ok['id']
