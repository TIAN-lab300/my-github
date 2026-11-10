"""Durable parsing; file extraction runs outside the SQLite transaction."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from app.core.db import DATA,transaction,one,run,insert,uid,now

def enqueue(db,version_id):
    job=one(db,'SELECT * FROM parse_jobs WHERE resource_version_id=:v',v=version_id)
    if job and job['status'] in ('queued','running'): return job['id']
    if job and job['attempts']>=3:
        from app.core.security import fail
        fail(409,'解析已尝试3次，请上传修正后的新版本')
    if job:
        run(db,"UPDATE parse_jobs SET status='queued',error=NULL,updated_at=:t WHERE id=:id",t=now(),id=job['id'])
        jid=job['id']
    else:
        jid=uid();insert(db,'parse_jobs',id=jid,resource_version_id=version_id,status='queued',attempts=0,created_at=now(),updated_at=now())
    run(db,"UPDATE resource_versions SET parse_status='queued',index_status='queued',error=NULL WHERE id=:v",v=version_id)
    return jid

def drain_once():
    from app.api.resources import extract_text,tokenize
    with transaction() as db:
        run(db,"UPDATE parse_jobs SET status='queued' WHERE status='running' AND lease_until<:t AND attempts<3",t=now())
        expired=one(db,"SELECT * FROM parse_jobs WHERE status='running' AND lease_until<:t AND attempts>=3",t=now())
        if expired:
            run(db,"UPDATE parse_jobs SET status='failed',error='解析恢复次数耗尽',updated_at=:t WHERE id=:id",id=expired['id'],t=now())
            run(db,"UPDATE resource_versions SET parse_status='failed',index_status='failed',error='解析恢复次数耗尽' WHERE id=:id",id=expired['resource_version_id'])
        j=one(db,"SELECT * FROM parse_jobs WHERE status='queued' ORDER BY created_at LIMIT 1")
        if not j:return
        token=uid()
        run(db,"UPDATE parse_jobs SET status='running',attempts=attempts+1,lease_token=:token,lease_until=:until,updated_at=:t WHERE id=:id",token=token,until=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(),t=now(),id=j['id'])
        v=one(db,'SELECT * FROM resource_versions WHERE id=:v',v=j['resource_version_id'])
        run(db,"UPDATE resource_versions SET parse_status='running' WHERE id=:v",v=v['id'])
    extraction={}
    try:
        if j['operation']!='text':
            from app.services.local_processing import process
            extraction=process(v,j,token)
            body=extraction['body']
        else:
            body=extract_text((DATA/'files'/v['storage_key']).read_bytes(),Path(v['filename']).suffix.lower())
        error=None
    except Exception as exc:
        body='';error=str(exc)[:300] if j['operation']!='text' else '无法解析正文，请检查UTF-8文本、文本PDF或DOCX/PPTX，图片型资料需要OCR'
    with transaction() as db:
        current=one(db,'SELECT * FROM parse_jobs WHERE id=:id',id=j['id'])
        if current['lease_token']!=token or current['status']!='running':return
        if not error and current['expected_version'] is not None:
            switched=run(db,"""UPDATE resources SET current_version=:v,status='draft',version=version+1 WHERE id=:r AND version=:e AND (class_id IS NULL OR EXISTS(SELECT 1 FROM classes WHERE id=resources.class_id AND status='active'))""",v=v['id'],r=v['resource_id'],e=current['expected_version'])
            if switched.rowcount!=1:
                error='资源已变更或班级已归档，请刷新后重新提交';body=''
        review=not error and bool(extraction) and extraction.get('confidence',0)<.85
        state='failed' if error else 'review_required' if review else 'ready'
        run(db,'UPDATE resource_versions SET body=:b,parse_status=:s,index_status=:i,error=:e WHERE id=:v',b=body,s=state,i='failed' if error else 'pending_review' if review else 'indexed',e=error,v=v['id'])
        run(db,'DELETE FROM chunks WHERE version_id=:v',v=v['id'])
        from app.core.db import dump
        run(db,'UPDATE resource_versions SET extraction_json=:data,review_status=:review WHERE id=:v',data=dump(extraction),review='pending' if review else 'not_required',v=v['id'])
        if not error and not review:run(db,'INSERT INTO chunks VALUES(:r,:v,:b)',r=v['resource_id'],v=v['id'],b=tokenize(body))
        run(db,'UPDATE parse_jobs SET status=:s,error=:e,updated_at=:t WHERE id=:id',s='failed' if error else 'ready',e=error,t=now(),id=j['id'])
