"""Extract bounded Office XML and validated subtitle text without external calls."""
from io import BytesIO
from pathlib import PurePosixPath
import posixpath
import re
from xml.etree import ElementTree
from zipfile import ZipFile


def read_xml(archive, name):
    data = archive.read(name)
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('文档包含不支持的XML声明')
    return ElementTree.fromstring(data)


def office_text(data, extension):
    with ZipFile(BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > 10000 or sum(entry.file_size for entry in entries) > 80 * 1024 * 1024:
            raise ValueError('文档解压后超过处理限制')
        if any(entry.file_size > 20 * 1024 * 1024 for entry in entries):
            raise ValueError('文档内部单文件超过处理限制')
        parts = []
        if extension == '.docx':
            document = read_xml(archive, 'word/document.xml')
            namespace = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
            for number, paragraph in enumerate(document.iter(namespace + 'p'), 1):
                text = ''.join(node.text or '' for node in paragraph.iter(namespace + 't'))
                if text.strip():
                    parts.append(f'【段落 {number}】\n{text}')
        else:
            presentation = read_xml(archive, 'ppt/presentation.xml')
            relations = read_xml(archive, 'ppt/_rels/presentation.xml.rels')
            targets = {node.get('Id'): node.get('Target') for node in relations
                       if node.get('TargetMode') != 'External'}
            relationship = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
            namespace = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
            for number, slide in enumerate(presentation.iter(namespace + 'sldId'), 1):
                target = targets[slide.get(relationship)]
                name = target.lstrip('/') if target.startswith('/') else posixpath.normpath('ppt/' + target)
                if not name.startswith('ppt/slides/'):
                    raise ValueError('课件幻灯片引用不合法')
                content = read_xml(archive, name)
                text = '\n'.join(node.text or '' for node in content.iter()
                                 if node.tag.endswith('}t'))
                parts.append(f'【幻灯片 {number}】\n{text}')
                slide_path = PurePosixPath(name)
                rels = str(slide_path.parent / '_rels' / (slide_path.name + '.rels'))
                if rels in archive.namelist():
                    for relation in read_xml(archive, rels):
                        if relation.get('Type', '').endswith('/notesSlide') and relation.get('TargetMode') != 'External':
                            note_name = posixpath.normpath(str(slide_path.parent / relation.get('Target', '')))
                            if note_name.startswith('ppt/notesSlides/'):
                                notes = read_xml(archive, note_name)
                                # Only body placeholders contain speaker notes. Exclude page numbers.
                                for shape in notes.iter(namespace + 'sp'):
                                    if any(node.get('type') == 'body' for node in shape.iter(namespace + 'ph')):
                                        note_text = '\n'.join(node.text or '' for node in shape.iter() if node.tag.endswith('}t'))
                                        if note_text.strip():
                                            parts.append(f'【幻灯片 {number} 备注】\n{note_text}')
        body = '\n\n'.join(parts)
        if not re.sub(r'【[^】]+】', '', body).strip():
            raise ValueError('未提取到正文，图片型页面需要OCR')
        return body


def subtitle_text(data, extension):
    text = data.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n').strip()
    if not text or '\x00' in text:
        raise ValueError('字幕必须包含有效正文')
    if extension == '.txt':
        return text
    if extension == '.vtt':
        header=text.split('\n',1)[0]
        if header!='WEBVTT' and not header.startswith(('WEBVTT ','WEBVTT\t')):
            raise ValueError('VTT缺少WEBVTT文件头')
        text = text.split('\n', 1)[1] if '\n' in text else ''
    cue_time = re.compile(r'(?:(\d{2,}):)?([0-5]\d):([0-5]\d)[,.](\d{3})')
    parts = []
    previous_start = -1
    for block in re.split(r'\n\s*\n', text):
        lines = block.strip().splitlines()
        if not lines or (extension == '.vtt' and lines[0].split(maxsplit=1)[0] in ('NOTE', 'STYLE', 'REGION')):
            continue
        index = next((i for i, line in enumerate(lines) if '-->' in line), None)
        if index is None or index > 1:
            raise ValueError('字幕缺少有效时间段')
        start, end = lines[index].split('-->', 1)
        start_match = cue_time.fullmatch(start.strip())
        end_match = cue_time.fullmatch(end.strip().split()[0]) if end.strip() else None
        if not start_match or not end_match:
            raise ValueError('字幕时间格式不合法')
        def seconds(match):
            hours, minutes, secs, milliseconds = match.groups()
            return int(hours or 0) * 3600 + int(minutes) * 60 + int(secs) + int(milliseconds) / 1000
        begin, finish = seconds(start_match), seconds(end_match)
        content = '\n'.join(lines[index + 1:]).strip()
        if begin < previous_start or finish <= begin or not content:
            raise ValueError('字幕时间逆序、时长无效或正文为空')
        previous_start = begin
        parts.append(f'【时间 {begin:g}–{finish:g} 秒】\n{content}')
    if not parts:
        raise ValueError('字幕没有有效片段')
    return '\n\n'.join(parts)


def excerpt_at(body, query):
    """Return original text and its nearest structural locator, including legacy text."""
    terms = re.findall(r'[a-zA-Z0-9_]+|[\u4e00-\u9fff]+', query)
    lower = body.lower()
    matches = [lower.find(term.lower()) for term in terms if term.lower() in lower]
    position = min(matches) if matches else 0
    markers = list(re.finditer(r'【(段落 \d+|幻灯片 \d+(?: 备注)?|页码 \d+|时间 [^】]+)】', body[:position + 1]))
    location = markers[-1].group(1) if markers else '正文/关联字幕'
    return body[max(0, position - 80):position + 720], location
