from io import BytesIO
from zipfile import ZipFile
import pytest
from app.services.parse_worker import drain_once
from app.services.document_text import subtitle_text, office_text
from test_platform import classroom, P


def office_file(extension):
    output = BytesIO()
    with ZipFile(output, 'w') as archive:
        if extension == '.docx':
            archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>课程介绍</w:t></w:r></w:p><w:p><w:r><w:t>递归终止条件</w:t></w:r></w:p></w:body></w:document>')
        else:
            archive.writestr('ppt/presentation.xml', '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst></p:presentation>')
            archive.writestr('ppt/_rels/presentation.xml.rels', '<Relationships><Relationship Id="rId1" Target="slides/slide2.xml"/></Relationships>')
            archive.writestr('ppt/slides/slide2.xml', '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:t>递归终止条件</a:t></p:sld>')
    return output.getvalue()


@pytest.mark.parametrize('extension,location', [('.docx', '段落 2'), ('.pptx', '幻灯片 1')])
def test_office_upload_parse_search_and_permissions(clients, extension, location):
    cid, _ = classroom(clients)
    teacher, student = clients['teacher'], clients['student']
    response = teacher.post(P + '/resources', data={'description': '课程正文', 'tags': '递归', 'source_license': '自编', 'class_id': cid}, files=[('files', ('notes' + extension, office_file(extension), 'application/octet-stream'))])
    item = response.json()[0]
    assert item['parse_status'] == 'queued'
    resource_id = item['id']
    assert teacher.post(P + f'/resources/{resource_id}/publish').status_code == 409
    drain_once()
    detail = teacher.get(P + f'/resources/{resource_id}').json()
    assert location in detail['body'] and '递归' in detail['body']
    assert teacher.post(P + f'/resources/{resource_id}/publish').status_code == 200
    result = student.post(P + '/retrieval/search', json={'query': '递归'}).json()['results'][0]
    assert result['location'] == location
    assert '递归' in result['excerpt']
    source_url = P + f'/resources/{resource_id}/versions/{item["version_id"]}/download'
    assert student.get(source_url).status_code == 200
    assert clients['student2'].get(source_url).status_code == 404
    rebuild = P + f'/resources/{resource_id}/rebuild-index'
    current = teacher.get(P + f'/resources/{resource_id}').json()
    assert student.post(rebuild, json={'version': current['version']}).status_code in (403, 404)
    assert teacher.post(rebuild, json={'version': current['version'] - 1}).status_code == 409
    assert teacher.post(rebuild, json={'version': current['version']}).status_code == 200
    assert teacher.post(rebuild, json={'version': current['version']}).status_code == 200
    assert len(student.post(P + '/retrieval/search', json={'query': '递归'}).json()['results']) == 1
    assert clients['student2'].get(P + f'/resources/{resource_id}/download').status_code == 404
    teacher.post(P + f'/resources/{resource_id}/withdraw')
    assert not student.post(P + '/retrieval/search', json={'query': '递归'}).json()['results']


@pytest.mark.parametrize('filename,mime,data', [
    ('audio.wav', 'audio/wav', b'RIFF\x00\x00\x00\x00WAVEdata'),
    ('audio.m4a', 'audio/mp4', b'\x00\x00\x00\x18ftypM4A '),
    ('video.mov', 'video/quicktime', b'\x00\x00\x00\x18ftypqt  '),
])
def test_media_types_and_subtitle_immutable_validation(clients, filename, mime, data):
    cid, _ = classroom(clients)
    teacher = clients['teacher']
    item = teacher.post(P + '/resources', data={'description': '媒体', 'tags': '测试', 'source_license': '自编', 'class_id': cid}, files=[('files', (filename, data, mime))]).json()[0]
    assert item.get('id') and item['parse_status'] == 'not_applicable', item
    url = P + '/resources/' + item['id']
    original = teacher.get(url).json()['current_version']
    bad = teacher.post(url + '/transcripts', files={'file': ('bad.srt', b'1\n00:00:05,000 --> 00:00:01,000\nwrong', 'text/plain')})
    assert bad.status_code == 422
    assert teacher.get(url).json()['current_version'] == original
    good = '1\n00:00:01,000 --> 00:00:04,000\n递归终止条件'
    assert teacher.post(url + '/transcripts', files={'file': ('notes.srt', good.encode(), 'text/plain')}).status_code == 200
    detail = teacher.get(url).json()
    assert detail['current_version'] != original and '时间 1–4 秒' in detail['body']


@pytest.mark.parametrize('text', ['WEBVTT\n\n00:99.000 --> 00:02.000\ntext', 'WEBVTT\n\nmissing time', 'WEBVTT\n\n00:01.000 --> 00:02.000'])
def test_invalid_vtt_is_rejected(text):
    with pytest.raises(ValueError):
        subtitle_text(text.encode(), '.vtt')


def test_corrupt_office_does_not_extract():
    from zipfile import BadZipFile
    with pytest.raises(BadZipFile):
        office_text(b'not an Office file', '.docx')
