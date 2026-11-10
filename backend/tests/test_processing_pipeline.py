from pathlib import Path
import json
import pytest
from app.core.db import transaction,one,rows
from app.services.parse_worker import drain_once
from test_platform import classroom,P


def image_resource(clients):
    from io import BytesIO
    from PIL import Image
    output=BytesIO()
    Image.new('RGB',(30,30),'white').save(output,format='PNG')
    cid,_=classroom(clients)
    response=clients['teacher'].post(P+'/resources',data={'description':'图片','tags':'课程','source_license':'自编','class_id':cid},files=[('files',('scan.png',output.getvalue(),'image/png'))])
    return response.json()[0]['id']


def test_processing_review_cancel_and_version_gate(clients,monkeypatch):
    teacher=clients['teacher'];student=clients['student'];rid=image_resource(clients)
    url=P+'/resources/'+rid
    original=teacher.get(url).json()
    payload={'operation':'ocr','version':original['version']}
    assert student.post(url+'/process',json=payload).status_code==403
    first=teacher.post(url+'/process',json=payload).json()
    assert teacher.post(url+'/process',json=payload).json()['job_id']==first['job_id']
    assert teacher.post(url+'/parse-jobs/'+first['job_id']+'/cancel').status_code==200
    drain_once()
    assert teacher.get(url).json()['current_version']==original['current_version']
    assert teacher.post(url+'/parse-jobs/'+first['job_id']+'/retry').status_code==200
    monkeypatch.setattr('app.services.local_processing.process',lambda *args:{'body':'递归终止条件','confidence':.5,'method':'test_fixture'})
    drain_once()
    pending=teacher.get(url).json()
    assert pending['review_status']=='pending' and pending['parse_status']=='review_required'
    assert teacher.post(url+'/publish').status_code==409
    assert not student.post(P+'/retrieval/search',json={'query':'递归'}).json()['results']
    assert teacher.post(url+'/review-extraction',json={'version':pending['version']-1,'body':'递归结束条件'}).status_code==409
    assert teacher.post(url+'/review-extraction',json={'version':pending['version'],'body':'递归结束条件'}).status_code==200
    assert teacher.post(url+'/publish').status_code==200
    assert student.post(P+'/retrieval/search',json={'query':'递归'}).json()['results']
    assert len(teacher.get(url+'/versions').json())==3


def test_processing_conflict_preserves_existing_body(clients,monkeypatch):
    teacher=clients['teacher'];rid=image_resource(clients);url=P+'/resources/'+rid
    original=teacher.get(url).json()
    teacher.post(url+'/process',json={'operation':'ocr','version':original['version']})
    teacher.patch(url,json={'version':original['version'],'title':'新标题'})
    monkeypatch.setattr('app.services.local_processing.process',lambda *args:{'body':'测试','confidence':.99})
    drain_once()
    assert teacher.get(url).json()['current_version']==original['current_version']
    assert teacher.get(url+'/parse-jobs').json()[0]['status']=='failed'


def test_metadata_match_is_not_body_evidence(clients):
    teacher=clients['teacher'];rid=image_resource(clients);url=P+'/resources/'+rid
    current=teacher.get(url).json()
    teacher.patch(url,json={'version':current['version'],'title':'递归图片'})
    teacher.post(url+'/publish')
    result=clients['student'].post(P+'/retrieval/search',json={'query':'递归'}).json()
    assert result['results']==[] and result['coverage_status']=='metadata_only'
    assert result['metadata_results'][0]['resource_id']==rid
    assert clients['student2'].post(P+'/retrieval/search',json={'query':'递归'}).json()['metadata_results']==[]


@pytest.mark.parametrize('extension',['png','pdf'])
def test_real_local_ocr_child_process(clients,extension):
    from io import BytesIO
    from PIL import Image,ImageDraw,ImageFont
    image=Image.new('RGB',(1200,180),'white')
    ImageDraw.Draw(image).text((20,40),'Python functions return values',fill='black',font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',40))
    output=BytesIO()
    if extension=='pdf':
        image.save(output,format='PDF',save_all=True,append_images=[Image.new('RGB',(1200,180),'white')])
    else:image.save(output,format='PNG')
    cid,_=classroom(clients);teacher=clients['teacher']
    item=teacher.post(P+'/resources',data={'description':'实测','tags':'Python','source_license':'生成测试','class_id':cid},files=[('files',('ocr.'+extension,output.getvalue(),'application/pdf' if extension=='pdf' else 'image/png'))]).json()[0]
    if extension=='pdf':drain_once()
    url=P+'/resources/'+item['id'];resource=teacher.get(url).json()
    teacher.post(url+'/process',json={'operation':'ocr','version':resource['version']})
    drain_once()
    processed=teacher.get(url).json()
    assert 'Python' in processed['body'] and 'return' in processed['body'],processed
    if extension=='pdf':
        assert processed['review_status']=='pending'
        assert json.loads(processed['extraction_json'])['unreadable_pages']==[2]


def test_subtitle_duration_and_upload_deduplication(clients):
    from io import BytesIO
    import wave
    output=BytesIO()
    with wave.open(output,'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(16000)
        audio.writeframes(b'\0'*32000)
    cid,_=classroom(clients);teacher=clients['teacher']
    def upload():
        return teacher.post(P+'/resources',data={'description':'一秒音频','tags':'字幕','source_license':'生成测试','class_id':cid},files=[('files',('one.wav',output.getvalue(),'audio/wav'))]).json()[0]
    first=upload();second=upload()
    assert first['id']==second['id'] and second['deduplicated'] is True
    url=P+'/resources/'+first['id']
    original=teacher.get(url).json()['current_version']
    response=teacher.post(url+'/transcripts',files={'file':('long.srt',b'1\n00:00:00,000 --> 00:00:02,000\nhello','text/plain')})
    assert response.status_code==422
    assert teacher.get(url).json()['current_version']==original


def test_real_vector_index_is_authorized(clients):
    from test_platform import resource
    from app.services.vector_index import drain_once as index_once
    cid,_=classroom(clients);rid=resource(clients,cid)
    index_once()
    result=clients['student'].post(P+'/retrieval/search',json={'query':'函数的返回值'}).json()
    assert result['vector_available'] is True,result
    assert result['results'][0]['resource_id']==rid
    assert not clients['student2'].post(P+'/retrieval/search',json={'query':'函数的返回值'}).json()['results']
