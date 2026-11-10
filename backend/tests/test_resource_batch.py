from test_platform import P,classroom,resource

def test_resource_private_and_metadata_guards(clients):
    student=clients['student']
    data={'description':'private','tags':'tag','source_license':'own'}
    uploaded=student.post(P+'/resources',data=data,files=[('files',('mine.txt',b'private notes','text/plain'))])
    rid=uploaded.json()[0]['id']
    url=P+'/resources/'+rid
    assert student.post(url+'/publish').status_code==403
    assert clients['teacher'].get(url).status_code==404
    current=student.get(url).json()
    assert current['scope']=='private' and current['cloud_allowed'] is False
    assert student.patch(url,json={'version':current['version'],'cloud_allowed':'false'}).status_code==422
    assert student.patch(url,json={'version':current['version'],'description':''}).status_code==422
    assert student.patch(url,json={'version':current['version'],'cloud_allowed':True}).status_code==200
    assert student.get(url).json()['cloud_allowed'] is True

def test_subtitles_create_reviewable_version(clients):
    cid,_=classroom(clients)
    teacher=clients['teacher']
    upload=teacher.post(P+'/resources',data={'description':'video','tags':'media','source_license':'own','class_id':cid},files=[('files',('clip.mp4',b'0000ftypisom00000000','video/mp4'))])
    rid=upload.json()[0]['id'];url=P+'/resources/'+rid
    assert teacher.post(url+'/publish').status_code==200
    before=teacher.get(url).json()
    assert before['parse_status']=='not_applicable'
    assert teacher.post(url+'/transcripts',files={'file':('caption.txt',b'functions recursion stack','text/plain')}).status_code==200
    after=teacher.get(url).json()
    assert after['status']=='draft' and after['current_version']!=before['current_version']
    assert clients['student'].get(url).status_code==404
    assert teacher.post(url+'/publish').status_code==200
    assert clients['student'].get(url).json()['body']=='functions recursion stack'
    text=resource(clients,cid)
    assert teacher.post(P+'/resources/'+text+'/transcripts',files={'file':('caption.txt',b'caption','text/plain')}).status_code==422

def test_private_resource_can_support_own_accepted_path(clients):
    from test_platform import goal,planning
    cid,_=classroom(clients)
    student=clients['student']
    response=student.post(P+'/resources',data={'description':'private notes','tags':'Python','source_license':'own'},files=[('files',('private.txt','函数 function def return 递归 recursion 调用栈 stack'.encode(),'text/plain'))])
    rid=response.json()[0]['id']
    gid=goal(clients,cid)
    pid=planning(student,gid)
    assert student.post(P+f'/paths/{pid}/accept').status_code==200
    path=student.get(P+'/paths/'+pid).json()
    assert any(source['resource_id']==rid and source['cloud_allowed'] is False for source in path['sources'])
    assert clients['teacher'].get(P+'/resources/'+rid).status_code==404

def test_sf_resource_02_upload_metadata(clients):
    cid,_=classroom(clients)
    teacher=clients['teacher']
    data={'class_id':cid,'title':'Explicit title','description':'Description','tags':'tag1,tag2','source_license':'Author permission','cloud_allowed':'true'}
    response=teacher.post(P+'/resources',data=data,files=[('files',('source.txt',b'body','text/plain'))])
    assert response.status_code==201
    rid=response.json()[0]['id']
    detail=teacher.get(P+'/resources/'+rid).json()
    for field in ['class_id','title','description','tags','source_license']:
        assert detail[field]==data[field]
    assert detail['cloud_allowed'] is True
    for field in ['description','tags','source_license']:
        invalid=teacher.post(P+'/resources',data={**data,field:' '},files=[('files',('invalid.txt',b'body','text/plain'))])
        assert invalid.status_code==422
    assert clients['teacher2'].post(P+'/resources',data=data,files=[('files',('foreign.txt',b'body','text/plain'))]).status_code==403

def test_sf_resource_14_attachment_is_not_evidence(clients):
    from test_platform import goal
    from app.core.db import transaction,one,run
    cid,_=classroom(clients);teacher=clients['teacher'];student=clients['student']
    response=teacher.post(P+'/resources',data={'class_id':cid,'description':'attachment','tags':'test','source_license':'own'},files=[('files',('audio.wav',b'RIFF0000WAVE00000000','audio/wav'))])
    rid=response.json()[0]['id'];url=P+'/resources/'+rid
    assert teacher.post(url+'/publish').status_code==200
    detail=student.get(url).json()
    assert detail['parse_status']==detail['index_status']=='not_applicable'
    assert detail['body']==''
    # Stale derived text must never elevate an attachment to verified evidence.
    with transaction() as db:
        run(db,"INSERT INTO chunks VALUES(:r,:v,:b)",r=rid,v=detail['current_version'],b='functions recursion stack')
        run(db,"UPDATE resource_versions SET body='functions recursion stack' WHERE id=:v",v=detail['current_version'])
    assert student.post(P+'/retrieval/search',json={'query':'recursion'}).json()['results']==[]
    gid=goal(clients,cid)
    generated=student.post(P+f'/goals/{gid}/planning-runs',headers={'Idempotency-Key':'attachment-only'})
    assert generated.status_code==202
    result=student.get(P+'/runs/'+generated.json()['run_id']).json()
    assert result['status']=='failed' and result['result_id'] is None

def test_historical_reference_survives_replacement_and_withdrawal(clients):
    from test_platform import goal,planning
    from app.core.db import transaction,one
    cid,_=classroom(clients);rid=resource(clients,cid);student=clients['student'];teacher=clients['teacher']
    gid=goal(clients,cid);pid=planning(student,gid)
    assert student.post(P+f'/paths/{pid}/accept').status_code==200
    original=teacher.get(P+f'/resources/{rid}').json()
    teacher.post(P+f'/resources/{rid}/versions',data={'expected_version':original['version']},files={'file':('new.txt',b'replacement text','text/plain')})
    historical=P+f"/resources/{rid}/versions/{original['current_version']}/content"
    assert student.get(historical).json()['body']==original['body']
    assert clients['student2'].get(historical).status_code==404
    assert teacher.post(P+f'/resources/{rid}/withdraw').status_code==200
    assert student.get(P+f'/resources/{rid}').status_code==404
    assert student.get(historical).json()['body']==original['body']
    teacher.delete(P+f'/classes/{cid}/members/student')
    assert student.get(historical).status_code==404

def test_upload_count_size_mime_and_attachment_metadata(clients):
    cid,_=classroom(clients);teacher=clients['teacher']
    data={'class_id':cid,'description':'notes','tags':'test','source_license':'own'}
    def upload(files):
        return teacher.post(P+'/resources',data=data,files=[('files',file) for file in files])
    assert upload([('a.txt',b'content','text/plain')]*11).status_code==422
    response=upload([('large.txt',b'a'*(20*1024*1024+1),'text/plain'),('good.txt',b'content','text/plain')])
    assert 'error' in response.json()[0] and response.json()[1]['id']
    assert 'error' in upload([('notes.txt',b'content','image/png')]).json()[0]
    assert 'error' in upload([('empty.txt',b'','text/plain')]).json()[0]
    image=upload([('image.png',bytes.fromhex('89504e470d0a1a0a')+b'test','image/png')]).json()[0]
    detail=teacher.get(P+'/resources/'+image['id']).json()
    assert detail['kind']=='image' and detail['parse_status']=='not_applicable'
    assert teacher.post(P+'/resources/'+image['id']+'/publish').status_code==200
    assert clients['student'].get(P+'/resources/'+image['id']+'/download').status_code==200
    assert clients['student2'].get(P+'/resources/'+image['id']+'/download').status_code==404

def test_batch_total_limit_and_pdf_modes(clients):
    from io import BytesIO
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
    from app.services.parse_worker import drain_once
    cid,_=classroom(clients);teacher=clients['teacher']
    data={'class_id':cid,'description':'limits','tags':'test','source_license':'own'}
    content=b'a'*(20*1024*1024)
    response=teacher.post(P+'/resources',data=data,files=[('files',(f'{n}.txt',content,'text/plain')) for n in range(6)])
    assert response.status_code==201
    assert all(row.get('id') for row in response.json()[:5])
    assert 'error' in response.json()[5]
    for with_text in [False,True]:
        writer=PdfWriter();page=writer.add_blank_page(width=300,height=300)
        if with_text:
            font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
            page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
            stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 20 200 Td (Readable PDF text) Tj ET')
            page[NameObject('/Contents')]=writer._add_object(stream)
        buffer=BytesIO();writer.write(buffer)
        created=teacher.post(P+'/resources',data=data,files=[('files',('sample.pdf',buffer.getvalue(),'application/pdf'))])
        rid=created.json()[0]['id']
        drain_once()
        detail=teacher.get(P+'/resources/'+rid).json()
        assert detail['parse_status']==('ready' if with_text else 'failed')
        if with_text:assert 'Readable PDF text' in detail['body']
        else:assert detail['error']
