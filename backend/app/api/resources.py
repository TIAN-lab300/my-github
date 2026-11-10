import hashlib,json,re,mimetypes
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import APIRouter,Depends,UploadFile,File,Form
from fastapi.responses import FileResponse
from app.core.db import *
from app.core.security import *
from app.schemas import StudyInput

router=APIRouter()
TEXT={'.md','.txt','.srt','.vtt','.pdf','.docx','.pptx'}
DOCUMENTS={'.pdf','.docx','.pptx'}
MEDIA={'.mp4','.webm','.mov','.m4a','.mp3','.wav','.ogg','.png','.jpg','.jpeg','.gif','.webp'}

@router.get('/resources/{id}/versions/{version_id}/content')
def historical_content(id:str,version_id:str,user=Depends(current_user)):
    with transaction() as db:
        r=one(db,'SELECT * FROM resources WHERE id=:id',id=id)
        if not r: fail(404,'资料不存在')
        if r['owner_id']!=user['id']:
            referenced=False
            if r['current_version']==version_id and r['status']=='published':
                resource_access(db,user,id)
                referenced=True
            for path in rows(db,"SELECT sources FROM paths WHERE student_id=:u AND status IN ('active','superseded')",u=user['id']):
                if any(s['resource_id']==id and s['version_id']==version_id for s in json.loads(path['sources'])):
                    referenced=True;break
            if not referenced:
                referenced=bool(one(db,"SELECT 1 FROM assignments a JOIN tasks t ON t.id=a.task_id WHERE a.student_id=:u AND t.resource_id=:r AND t.resource_version_id=:v AND a.status!='cancelled'",u=user['id'],r=id,v=version_id))
            if not referenced: fail(404,'历史来源不可访问')
            if r['scope']=='class': class_access(db,user,r['class_id'])
            elif r['scope']=='private': fail(404,'历史来源不可访问')
        version=one(db,'SELECT id,body,parse_status,index_status,created_at FROM resource_versions WHERE resource_id=:r AND id=:v',r=id,v=version_id)
        if not version: fail(404,'历史版本不存在')
        return version

@router.get('/resources/{id}/versions')
def versions(id:str,user=Depends(current_user)):
    with transaction() as db:
        resource_access(db,user,id,True)
        return rows(db,'SELECT id,filename,bytes,hash,parse_status,index_status,error,created_at FROM resource_versions WHERE resource_id=:r ORDER BY created_at DESC',r=id)

@router.get('/resources/{id}/versions/{version_id}/download')
def historical_download(id:str,version_id:str,user=Depends(current_user)):
    historical_content(id,version_id,user)
    with transaction() as db:
        version=one(db,'SELECT * FROM resource_versions WHERE resource_id=:r AND id=:v',r=id,v=version_id)
    if not version['storage_key']: fail(404,'该版本仅登记外部网址')
    return FileResponse(DATA/'files'/version['storage_key'],media_type=version['mime'],filename=version['filename'],headers={'X-Content-Type-Options':'nosniff'})


def extract_text(data,extension):
    from app.services.document_text import office_text,subtitle_text
    if extension in ('.docx','.pptx'):
        return office_text(data,extension)
    if extension in ('.srt','.vtt'):
        return subtitle_text(data,extension)
    if extension=='.pdf':
        from io import BytesIO
        from pypdf import PdfReader
        if not data.startswith(b'%PDF'): raise ValueError('不是有效PDF')
        pages=[p.extract_text() or '' for p in PdfReader(BytesIO(data)).pages]
        if not any(page.strip() for page in pages): raise ValueError('扫描PDF需要OCR，未提取到正文')
        body='\n\n'.join(f'【页码 {number}】\n{text}' for number,text in enumerate(pages,1) if text.strip())
    else: body=data.decode('utf-8-sig')
    if not body.strip() or '\x00' in body: raise ValueError('无可读正文，扫描PDF暂不支持')
    return body

@router.post('/resources/{id}/versions',status_code=201)
async def replace_content(id:str,file:UploadFile=File(...),expected_version:int=Form(...),background:bool=Form(False),user=Depends(current_user)):
    with transaction() as db:
        r=resource_access(db,user,id,True)
        if r['version']!=expected_version: fail(409,'资料已更新，请刷新后重试')
        if r['kind']!='text': fail(422,'此入口仅用于正文资料，音视频请使用字幕关联')
    data=await file.read(20*1024*1024+1);ext=Path(file.filename or '').suffix.lower()
    if not data or len(data)>20*1024*1024 or ext not in TEXT: fail(422,'请选择20MiB内支持的正文文件')
    if background:
        from app.services.parse_worker import enqueue
        key=uid()+ext;vid=uid();(DATA/'files'/key).write_bytes(data)
        try:
            with transaction() as db:
                r=resource_access(db,user,id,True)
                if r['version']!=expected_version: fail(409,'资源已变更，请刷新后再试')
                insert(db,'resource_versions',id=vid,resource_id=id,filename=Path(file.filename).name,storage_key=key,mime=mimetypes.guess_type(file.filename)[0] or 'application/octet-stream',bytes=len(data),hash=hashlib.sha256(data).hexdigest(),body='',parse_status='queued',index_status='queued',created_at=now())
                jid=enqueue(db,vid)
                run(db,'UPDATE parse_jobs SET expected_version=:e WHERE id=:j',e=expected_version,j=jid)
                audit(db,user['id'],'resource_candidate_uploaded',id)
        except Exception:
            (DATA/'files'/key).unlink(missing_ok=True);raise
        return {'id':vid,'job_id':jid,'status':'queued'}
    try: body=extract_text(data,ext)
    except Exception: fail(422,'解析失败，请检查UTF-8文本、文本PDF或DOCX/PPTX文件；当前已发布版本未改变')
    key=uid()+ext;vid=uid();(DATA/'files'/key).write_bytes(data)
    try:
        with transaction() as db:
            r=resource_access(db,user,id,True)
            if r['version']!=expected_version: fail(409,'上传期间资料已更新，请刷新后重试')
            insert(db,'resource_versions',id=vid,resource_id=id,filename=Path(file.filename or 'file').name,storage_key=key,mime=mimetypes.guess_type(file.filename or '')[0] or 'application/octet-stream',bytes=len(data),hash=hashlib.sha256(data).hexdigest(),body=body,parse_status='ready',index_status='indexed',error=None,created_at=now())
            run(db,'INSERT INTO chunks VALUES(:r,:v,:b)',r=id,v=vid,b=tokenize(body))
            run(db,"UPDATE resources SET current_version=:v,status='draft',version=version+1 WHERE id=:id",v=vid,id=id)
            audit(db,user['id'],'resource_version_created',id)
    except Exception:
        (DATA/'files'/key).unlink(missing_ok=True);raise
    return {'id':vid,'status':'draft','message':'新正文已保存为草稿，审核后重新发布；旧版本保留'}

@router.post('/resources/{id}/retry-parse')
def retry_parse(id:str,user=Depends(current_user)):
    with transaction() as db:
        r=resource_access(db,user,id,True)
        v=one(db,'SELECT * FROM resource_versions WHERE id=:id',id=r['current_version'])
        if r['kind']!='text' or not v['storage_key']: fail(422,'该资料不适用正文重解析')
        if v['parse_status']=='ready': return {'ok':True,'already_ready':True}
        from app.services.parse_worker import enqueue
        jid=enqueue(db,v['id'])
        audit(db,user['id'],'resource_parse_retried',id)
    return {'ok':True,'job_id':jid,'status':'queued'}

@router.get('/resources/{id}/parse-jobs/{job_id}')
def parse_job(id:str,job_id:str,user=Depends(current_user)):
    with transaction() as db:
        resource_access(db,user,id,True)
        job=one(db,'SELECT j.id,j.status,j.attempts,j.error,j.updated_at FROM parse_jobs j JOIN resource_versions v ON v.id=j.resource_version_id WHERE j.id=:j AND v.resource_id=:r',j=job_id,r=id)
        if not job: fail(404,'解析任务不存在')
        return job


@router.get('/resources/{id}/parse-jobs')
def processing_jobs(id:str,user=Depends(current_user)):
    with transaction() as db:
        resource_access(db,user,id,True)
        return rows(db,'SELECT j.id,j.status,j.operation,j.attempts,j.error,j.updated_at FROM parse_jobs j JOIN resource_versions v ON v.id=j.resource_version_id WHERE v.resource_id=:r ORDER BY j.created_at DESC LIMIT 20',r=id)


@router.post('/resources/{id}/rebuild-index')
def rebuild_resource_index(id:str,body:dict,user=Depends(current_user)):
    with transaction() as db:
        resource=resource_access(db,user,id,True)
        if type(body.get('version')) is not int or body['version']!=resource['version']:
            fail(409,'资料已变化，请刷新后重建索引')
        version=one(db,'SELECT * FROM resource_versions WHERE id=:v',v=resource['current_version'])
        if version['parse_status']!='ready' or not version['body'].strip():
            fail(409,'正文尚未就绪，不能重建索引')
        run(db,'DELETE FROM chunks WHERE version_id=:v',v=version['id'])
        run(db,'INSERT INTO chunks VALUES(:r,:v,:b)',r=id,v=version['id'],b=tokenize(version['body']))
        run(db,"UPDATE resource_versions SET index_status='indexed' WHERE id=:v",v=version['id'])
        from app.services.vector_index import enqueue as enqueue_vector
        enqueue_vector(db,version['id'])
        run(db,"UPDATE embedding_jobs SET status='queued',attempts=0,error=NULL,updated_at=:t WHERE version_id=:v",t=now(),v=version['id'])
        audit(db,user['id'],'resource_index_rebuilt',id)
    return {'ok':True,'resource_version_id':version['id'],'index_status':'indexed'}


@router.post('/resources/{id}/process',status_code=202)
def process_resource(id:str,body:dict,user=Depends(current_user)):
    operation=body.get('operation')
    with transaction() as db:
        resource=resource_access(db,user,id,True)
        if type(body.get('version')) is not int or body['version']!=resource['version']:
            fail(409,'资料已变化，请刷新后处理')
        source=one(db,'SELECT * FROM resource_versions WHERE id=:id',id=resource['current_version'])
        if operation=='ocr':
            if resource['kind']!='image' and Path(source['filename']).suffix.lower()!='.pdf':
                fail(422,'OCR仅支持图片和PDF')
        elif operation=='transcribe':
            if resource['kind'] not in ('video','audio'): fail(422,'转写仅支持音视频')
        else: fail(422,'请选择OCR或语音转写')
        existing=one(db,"SELECT j.id FROM parse_jobs j JOIN resource_versions v ON v.id=j.resource_version_id WHERE v.resource_id=:r AND j.operation=:op AND j.expected_version=:version AND j.status IN ('queued','running')",r=id,op=operation,version=resource['version'])
        if existing: return {'job_id':existing['id'],'status':'queued'}
        version_id=uid()
        source.update(id=version_id,body='',parse_status='queued',index_status='queued',review_status='not_required',extraction_json='{}',error=None,created_at=now())
        insert(db,'resource_versions',**source)
        from app.services.parse_worker import enqueue
        job_id=enqueue(db,version_id)
        run(db,'UPDATE parse_jobs SET operation=:op,expected_version=:version WHERE id=:id',op=operation,version=resource['version'],id=job_id)
        audit(db,user['id'],'resource_processing_started',id,operation)
    return {'job_id':job_id,'status':'queued'}


@router.post('/resources/{id}/parse-jobs/{job_id}/cancel')
def cancel_parse(id:str,job_id:str,user=Depends(current_user)):
    with transaction() as db:
        resource_access(db,user,id,True)
        job=one(db,'SELECT j.* FROM parse_jobs j JOIN resource_versions v ON v.id=j.resource_version_id WHERE j.id=:id AND v.resource_id=:r',id=job_id,r=id)
        if not job: fail(404,'处理任务不存在')
        if job['status'] in ('queued','running'):
            run(db,"UPDATE parse_jobs SET status='cancelled',updated_at=:t WHERE id=:id",t=now(),id=job_id)
            run(db,"UPDATE resource_versions SET parse_status='cancelled',index_status='failed',error='用户取消处理' WHERE id=:v",v=job['resource_version_id'])
            audit(db,user['id'],'resource_processing_cancelled',id)
    return {'ok':True}


@router.post('/resources/{id}/parse-jobs/{job_id}/retry')
def retry_processing_job(id:str,job_id:str,user=Depends(current_user)):
    with transaction() as db:
        resource=resource_access(db,user,id,True)
        job=one(db,'SELECT j.* FROM parse_jobs j JOIN resource_versions v ON v.id=j.resource_version_id WHERE j.id=:id AND v.resource_id=:r',id=job_id,r=id)
        if not job or job['status'] not in ('failed','cancelled'): fail(409,'该处理任务不可重试')
        if job['expected_version'] is not None and job['expected_version']!=resource['version']:
            fail(409,'资料已变化，请重新创建处理任务')
        from app.services.parse_worker import enqueue
        enqueue(db,job['resource_version_id'])
        audit(db,user['id'],'resource_processing_retried',id)
    return {'job_id':job_id,'status':'queued'}


@router.post('/resources/{id}/review-extraction')
def review_extraction(id:str,body:dict,user=Depends(current_user)):
    content=body.get('body')
    if not isinstance(content,str) or not content.strip() or len(content)>2_000_000 or '\x00' in content:
        fail(422,'请提供有效的复核正文')
    with transaction() as db:
        resource=resource_access(db,user,id,True)
        if body.get('version')!=resource['version']: fail(409,'资料已变化，请刷新后复核')
        source=one(db,'SELECT * FROM resource_versions WHERE id=:id',id=resource['current_version'])
        if source['review_status']!='pending': fail(409,'该版本不需要复核')
        version_id=uid()
        source.update(id=version_id,body=content,parse_status='ready',index_status='indexed',review_status='approved',error=None,created_at=now())
        insert(db,'resource_versions',**source)
        run(db,'INSERT INTO chunks VALUES(:r,:v,:b)',r=id,v=version_id,b=tokenize(content))
        run(db,"UPDATE resources SET current_version=:v,status='draft',version=version+1 WHERE id=:r",v=version_id,r=id)
        audit(db,user['id'],'resource_extraction_reviewed',id)
    return {'ok':True,'version_id':version_id}


def tokenize(text):
    # Character spacing makes Chinese searchable in FTS5 without external dictionaries.
    return re.sub(r'([\u4e00-\u9fff])',r' \1 ',text)

def visible(db,user):
    result=[]
    for r in rows(db,'SELECT * FROM resources ORDER BY created_at DESC'):
        if r['owner_id']==user['id']: result.append(r); continue
        if r['status']!='published': continue
        if r['scope']=='school' or (r['scope']=='class' and user['role']=='student' and one(db,"SELECT 1 FROM memberships WHERE class_id=:c AND user_id=:u AND status='active'",c=r['class_id'],u=user['id'])):
            result.append(r)
    return result

def dto(db,r,body=False):
    v=one(db,'SELECT * FROM resource_versions WHERE id=:id',id=r['current_version'])
    result=dict(r)
    result['cloud_allowed']=bool(result['cloud_allowed'])
    if v:
        result.update({k:v[k] for k in ('filename','mime','bytes','parse_status','index_status','error','review_status','extraction_json')})
        if body: result['body']=v['body']
    return result

@router.get('/resources')
def listing(q:str='',kind:str='',page:int=1,class_id:str='',status:str='',parse_status:str='',tag:str='',user=Depends(current_user)):
    if page<1: fail(422,'页码必须为正数')
    if status and status not in ('draft','published','withdrawn'): fail(422,'发布状态不合法')
    if parse_status and parse_status not in ('queued','running','ready','failed','not_applicable','review_required','cancelled'): fail(422,'解析状态不合法')
    with transaction() as db:
        result=[r for r in visible(db,user) if q.lower() in (r['title']+' '+r['tags']).lower() and (not kind or r['kind']==kind)]
        result=[dto(db,r) for r in result if (not class_id or r['class_id']==class_id) and (not status or r['status']==status) and (not tag or tag.lower() in r['tags'].lower())]
        result=[r for r in result if not parse_status or r['parse_status']==parse_status]
        return result[(page-1)*50:page*50]

@router.post('/resources',status_code=201)
async def upload(files:list[UploadFile]=File(...),title:str=Form(''),description:str=Form(...),tags:str=Form(...),source_license:str=Form(...),class_id:str=Form(''),cloud_allowed:bool=Form(False),user=Depends(current_user)):
    role(user,'teacher','student','admin')
    if not description.strip() or not tags.strip() or not source_license.strip(): fail(422,'请填写说明、标签和来源权限')
    if len(files)>10: fail(422,'每批最多10份文件')
    with transaction() as db:
        if user['role']=='teacher': class_access(db,user,class_id,True)
        elif class_id: fail(422,'私有或共享资料不能指定班级')
    results=[]; total=0; document_total=0
    for f in files:
        ext=Path(f.filename or '').suffix.lower()
        is_media=ext in {'.mp4','.webm','.mov','.mp3','.wav','.ogg','.m4a'}
        limit=(200 if is_media else 20)*1024*1024
        data=await f.read(limit+1); total+=len(data)
        if not is_media: document_total+=len(data)
        if len(data)>limit or total>500*1024*1024 or document_total>100*1024*1024 or not data or ext not in TEXT|MEDIA:
            results.append({'filename':f.filename,'error':'空文件、格式不支持或超过上传限制'}); continue
        mime=(f.content_type or '').split(';')[0].lower()
        expected=mimetypes.guess_type(f.filename or '')[0]
        text_mimes={'text/plain','text/markdown','text/x-markdown','text/vtt','application/x-subrip'}
        media_mimes={'.wav':{'audio/wav','audio/x-wav','audio/wave'},'.mp3':{'audio/mpeg','audio/mp3'},'.m4a':{'audio/mp4','audio/x-m4a'},'.mov':{'video/quicktime'}}
        if mime and mime!='application/octet-stream' and mime!=expected and mime not in media_mimes.get(ext,set()) and not (ext in TEXT-DOCUMENTS and mime in text_mimes):
            results.append({'filename':f.filename,'error':'MIME与文件格式不符'});continue
        rid=uid();vid=uid();storage=uid()+ext;job_id=None
        body=''; error=None; state='ready' if ext in TEXT else 'not_applicable'
        try:
            if ext in DOCUMENTS:
                if ext=='.pdf' and not data.startswith(b'%PDF'): raise ValueError('不是有效PDF')
                state='queued'
            elif ext in TEXT: body=extract_text(data,ext)
            if ext in TEXT and state!='queued' and not body.strip(): raise ValueError('未提取到正文，扫描PDF当前不支持')
            if '\x00' in body: raise ValueError('文本包含二进制内容')
        except Exception as exc:
            state='failed';error=str(exc)[:200]
        if ext in MEDIA:
            matches={
                '.png':data.startswith(bytes.fromhex('89504e470d0a1a0a')),
                '.jpg':data.startswith(bytes.fromhex('ffd8ff')),
                '.jpeg':data.startswith(bytes.fromhex('ffd8ff')),
                '.gif':data.startswith((b'GIF87a',b'GIF89a')),
                '.webp':data.startswith(b'RIFF') and data[8:12]==b'WEBP',
                '.wav':data.startswith(b'RIFF') and data[8:12]==b'WAVE',
                '.mp4':data[4:8]==b'ftyp',
                '.mov':data[4:8] in (b'ftyp',b'moov',b'mdat',b'wide'),
                '.m4a':data[4:8]==b'ftyp',
                '.webm':data.startswith(bytes.fromhex('1a45dfa3')),
                '.ogg':data.startswith(b'OggS'),
                '.mp3':data.startswith(b'ID3') or (len(data)>1 and data[0]==255 and data[1]&224==224),
            }
            if not matches[ext]:
                results.append({'filename':f.filename,'error':'文件内容与类型不符'});continue
        (DATA/'files'/storage).write_bytes(data)
        try:
            with transaction() as db:
                if user['role']=='teacher': class_access(db,user,class_id,True)
                existing=one(db,'''SELECT r.id,r.current_version,v.parse_status,v.error FROM resources r JOIN resource_versions v ON v.id=r.current_version WHERE r.owner_id=:owner AND r.class_id IS :class_id AND v.hash=:hash AND r.title=:title AND r.description=:description AND r.tags=:tags AND r.source_license=:license AND r.cloud_allowed=:cloud LIMIT 1''',owner=user['id'],class_id=class_id or None,hash=hashlib.sha256(data).hexdigest(),title=(title.strip() or f.filename or '资料')[:200],description=description[:3000],tags=tags[:500],license=source_license[:1000],cloud=int(cloud_allowed))
                if existing:
                    (DATA/'files'/storage).unlink(missing_ok=True)
                    results.append({'id':existing['id'],'version_id':existing['current_version'],'filename':f.filename,'parse_status':existing['parse_status'],'error':existing['error'],'deduplicated':True})
                    continue
                insert(db,'resources',id=rid,owner_id=user['id'],class_id=class_id or None,scope='class' if user['role']=='teacher' else 'private' if user['role']=='student' else 'school',title=(title.strip() or f.filename or '资料')[:200],description=description[:3000],tags=tags[:500],source_license=source_license[:1000],cloud_allowed=int(cloud_allowed),kind='text' if ext in TEXT else 'video' if ext in ('.mp4','.webm','.mov') else 'audio' if ext in ('.mp3','.wav','.ogg','.m4a') else 'image',current_version=vid,created_at=now())
                insert(db,'resource_versions',id=vid,resource_id=rid,filename=Path(f.filename or 'file').name,storage_key=storage,mime=mimetypes.guess_type(f.filename or '')[0] or 'application/octet-stream',bytes=len(data),hash=hashlib.sha256(data).hexdigest(),body=body,parse_status=state,index_status='indexed' if body and state=='ready' else 'not_applicable' if state=='not_applicable' else 'failed',error=error,created_at=now())
                if body and state=='ready': run(db,'INSERT INTO chunks(resource_id,version_id,body) VALUES(:r,:v,:b)',r=rid,v=vid,b=tokenize(body))
                if state=='queued':
                    from app.services.parse_worker import enqueue
                    job_id=enqueue(db,vid)
                audit(db,user['id'],'resource_uploaded',rid)
        except Exception:
            (DATA/'files'/storage).unlink(missing_ok=True); raise
        results.append({'id':rid,'version_id':vid,'job_id':job_id,'filename':f.filename,'parse_status':state,'error':error})
    return results

@router.post('/resources/links',status_code=201)
def link(body:dict,user=Depends(current_user)):
    role(user,'teacher')
    for field,limit in [('url',2048),('title',200),('description',3000),('class_id',100)]:
        if not isinstance(body.get(field),str) or not body[field].strip() or len(body[field])>limit:fail(422,'请填写有效的网址、标题、说明和班级')
    if 'tags' in body and (not isinstance(body['tags'],str) or len(body['tags'])>500):fail(422,'标签不合法')
    url=body['url']; parsed=urlsplit(url)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password: fail(422,'请输入有效HTTP/HTTPS网址')
    if not str(body.get('title','')).strip() or not str(body.get('description','')).strip(): fail(422,'请填写标题与推荐理由')
    with transaction() as db:
        class_access(db,user,body.get('class_id'),True)
        rid=uid();vid=uid()
        insert(db,'resources',id=rid,owner_id=user['id'],class_id=body['class_id'],scope='class',title=body['title'][:200],description=body['description'][:3000],tags=str(body.get('tags',''))[:500],source_license='教师登记，内容待审核',cloud_allowed=0,kind='link',current_version=vid,created_at=now())
        insert(db,'resource_versions',id=vid,resource_id=rid,filename=url,bytes=0,hash=hashlib.sha256(url.encode()).hexdigest(),body='',parse_status='not_applicable',index_status='not_applicable',created_at=now())
    return {'id':rid}

@router.get('/resources/{id}')
def detail(id:str,user=Depends(current_user)):
    with transaction() as db: return dto(db,resource_access(db,user,id),True)

@router.post('/resources/{id}/publish')
def publish(id:str,user=Depends(current_user)):
    with transaction() as db:
        r=resource_access(db,user,id,True);v=one(db,'SELECT * FROM resource_versions WHERE id=:id',id=r['current_version'])
        role(user,'teacher','admin')
        if v['parse_status'] not in ('ready','not_applicable'): fail(409,'正文解析失败，不能发布')
        if v['parse_status']=='ready' and v['index_status']!='indexed': fail(409,'正文索引未就绪')
        run(db,"UPDATE resources SET status='published',version=version+1 WHERE id=:id",id=id)
        from app.services.vector_index import enqueue as enqueue_vector
        if v['parse_status']=='ready': enqueue_vector(db,v['id'])
        audit(db,user['id'],'resource_published',id)
    return {'ok':True}

@router.post('/resources/{id}/withdraw')
def withdraw(id:str,user=Depends(current_user)):
    with transaction() as db:
        resource_access(db,user,id,True)
        run(db,"UPDATE resources SET status='withdrawn',version=version+1 WHERE id=:id",id=id)
        audit(db,user['id'],'resource_withdrawn',id)
    return {'ok':True}

@router.get('/resources/{id}/download')
def download(id:str,inline:bool=False,user=Depends(current_user)):
    with transaction() as db:
        r=resource_access(db,user,id);v=one(db,'SELECT * FROM resource_versions WHERE id=:id',id=r['current_version'])
    if not v['storage_key']: fail(404,'该资料仅登记外部网址')
    return FileResponse(DATA/'files'/v['storage_key'],media_type=v['mime'],filename=v['filename'],content_disposition_type='inline' if inline and (r['kind'] in ('video','audio','image') or v['mime']=='application/pdf') else 'attachment',headers={'X-Content-Type-Options':'nosniff'})

@router.post('/resources/{id}/transcripts')
async def transcript(id:str,file:UploadFile=File(...),user=Depends(current_user)):
    data=await file.read(1024*1024+1)
    if len(data)>1024*1024 or Path(file.filename or '').suffix.lower() not in ('.txt','.srt','.vtt'): fail(422,'字幕须为1MiB内TXT/SRT/VTT')
    from app.services.document_text import subtitle_text
    try: body=subtitle_text(data,Path(file.filename or '').suffix.lower())
    except (UnicodeDecodeError,ValueError) as exc: fail(422,'字幕校验失败，请检查UTF-8编码、时间格式和正文')
    if not body.strip(): fail(422,'字幕不能为空')
    with transaction() as db:
        r=resource_access(db,user,id,True)
        if r['kind'] not in ('video','audio'): fail(422,'仅音视频支持关联字幕')
        # New immutable resource version, retaining attachment and old transcript history.
        old=one(db,'SELECT * FROM resource_versions WHERE id=:id',id=r['current_version']);vid=uid()
        metadata=json.loads(old['extraction_json'])
        duration=metadata.get('duration_seconds')
        if duration is None:
            try:
                from app.services.media_extract import media_duration
                duration=media_duration(DATA/'files'/old['storage_key'])
            except (ValueError,ImportError,OSError):
                duration=None
        times=[float(value) for value in re.findall(r'【时间 [\d.]+–([\d.]+) 秒】',body)]
        if duration is not None and times and max(times)>duration+.1:fail(422,'字幕时间超过媒体长度，请校正后重新提交')
        metadata.update(duration_seconds=duration,subtitle_duration_verified=duration is not None)
        old['extraction_json']=dump(metadata)
        old.update(id=vid,body=body,parse_status='ready',index_status='indexed',created_at=now(),error=None)
        insert(db,'resource_versions',**old)
        insert(db,'transcripts',id=uid(),version_id=vid,body=body,filename=(file.filename or '')[:200],created_at=now())
        run(db,'INSERT INTO chunks VALUES(:r,:v,:b)',r=id,v=vid,b=tokenize(body))
        run(db,"UPDATE resources SET current_version=:v,status='draft',version=version+1 WHERE id=:id",v=vid,id=id)
    return {'ok':True}

@router.post('/resources/{id}/study-events')
def study(id:str,body:StudyInput,user=Depends(current_user)):
    role(user,'student')
    with transaction() as db:
        r=resource_access(db,user,id)
        if r['class_id'] and class_access(db,user,r['class_id'])['status']!='active': fail(409,'归档班级不能新增学习记录')
        existing=one(db,'SELECT * FROM study_sessions WHERE id=:id',id=body.session_id)
        if existing and (existing['student_id']!=user['id'] or existing['resource_id']!=id): fail(409,'学习会话标识冲突')
        if existing and existing['minutes']==body.minutes and existing['completed']==int(body.completed):
            return {'ok':True,'session_id':body.session_id}
        run(db,'INSERT INTO study_sessions VALUES(:s,:u,:r,:c,:m,:done,:time) ON CONFLICT(id) DO UPDATE SET minutes=:m,completed=:done',s=body.session_id,u=user['id'],r=id,c=r['class_id'],m=body.minutes,done=int(body.completed),time=now())
        touch(db,user['id'])
    return {'ok':True,'session_id':body.session_id}

@router.post('/retrieval/search')
def search(body:dict,user=Depends(current_user)):
    query=str(body.get('query','')).strip()[:200]
    if not query: fail(422,'请输入检索词')
    tokens=re.findall(r'[a-zA-Z0-9_]+|[\u4e00-\u9fff]',query)
    expression=' OR '.join('"'+t+'"' for t in tokens)
    with transaction() as db:
        allowed={r['id']:r for r in visible(db,user)}
        # Restrict FTS candidates to authorized IDs before ranking (not after top-k).
        hits=[]; dense=[]; metadata=[]
        for rid,r in allowed.items():
            if r['status']!='published' and r['scope']!='private': continue
            version=one(db,'SELECT body,parse_status,index_status FROM resource_versions WHERE id=:v',v=r['current_version'])
            if query.lower() in (r['title']+' '+r['tags']+' '+r['description']).lower():
                metadata.append({'resource_id':rid,'resource_version_id':r['current_version'],'title':r['title'],'kind':r['kind'],'parse_status':version['parse_status'] if version else 'unavailable'})
            if not version or version['parse_status']!='ready' or version['index_status']!='indexed': continue
            from app.services.vector_index import enqueue as enqueue_vector
            enqueue_vector(db,r['current_version'])
            dense.extend({**entry,'resource_id':rid,'title':r['title']} for entry in rows(db,'SELECT * FROM vector_chunks WHERE version_id=:v',v=r['current_version']))
            found=rows(db,'SELECT version_id,body,bm25(chunks) AS rank FROM chunks WHERE chunks MATCH :q AND resource_id=:r AND version_id=:v',q=expression or '""',r=rid,v=r['current_version'])
            from app.services.document_text import excerpt_at
            excerpt,location=excerpt_at(version['body'],query)
            for f in found: hits.append({'resource_id':rid,'resource_version_id':f['version_id'],'title':r['title'],'excerpt':excerpt,'score':-f['rank'],'location':location,'method':'FTS5关键词检索'})
        hits.sort(key=lambda h:h['score'],reverse=True)
    vector_available=False
    if dense:
        from app.services.vector_index import embed,cosine
        try:
            query_vector=embed([query])[0]
            ranked=sorted(((cosine(query_vector,json.loads(chunk['embedding'])),chunk) for chunk in dense),key=lambda pair:pair[0],reverse=True)
            fused={(hit['resource_id'],hit['resource_version_id']):{**hit,'score':1/(60+index)} for index,hit in enumerate(hits,1)}
            seen=set()
            for rank,(similarity,chunk) in enumerate(ranked,1):
                key=(chunk['resource_id'],chunk['version_id'])
                if similarity<.25 or key in seen: continue
                seen.add(key)
                if key in fused:
                    fused[key]['score']+=1/(60+rank)
                    fused[key]['method']='FTS5与本地中文向量混合检索'
                else:
                    fused[key]={'resource_id':key[0],'resource_version_id':key[1],'title':chunk['title'],'excerpt':chunk['body'],'location':chunk['location'],'score':1/(60+rank),'method':'本地中文向量检索'}
            hits=sorted(fused.values(),key=lambda hit:hit['score'],reverse=True)
            vector_available=True
        except Exception:
            vector_available=False
    with transaction() as db:
        current_allowed={resource['id']:resource for resource in visible(db,user)}
        hits=[hit for hit in hits if (resource:=current_allowed.get(hit['resource_id'])) and resource['current_version']==hit['resource_version_id'] and (resource['status']=='published' or resource['scope']=='private')]
    metadata=[hit for hit in metadata if (resource:=current_allowed.get(hit['resource_id'])) and resource['current_version']==hit['resource_version_id'] and (resource['status']=='published' or resource['scope']=='private')]
    return {'results':hits[:20],'metadata_results':metadata[:20],'coverage_status':'body_hits' if hits else 'metadata_only' if metadata else 'empty','coverage':'有正文命中，覆盖仍需校验' if hits else '仅资料信息命中，正文证据不足' if metadata else '未找到授权正文，请补充材料','vector_available':vector_available,'web_search_executed':False}
