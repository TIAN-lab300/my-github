"""Offline Chinese embeddings with renewable, persistent indexing jobs."""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import json
import os
from pathlib import Path
from threading import Lock
from app.core.db import transaction, one, rows, run, insert, now, uid, dump

MODEL = 'BAAI/bge-small-zh-v1.5'
MODEL_DIR = Path(os.getenv('ZHIXING_MODEL_DIR', str(Path(__file__).resolve().parents[2] / 'data' / 'models')))
model_lock = Lock()


@lru_cache(maxsize=1)
def model():
    from fastembed import TextEmbedding
    return TextEmbedding(MODEL, cache_dir=str(MODEL_DIR / 'embeddings'),
                         threads=2, local_files_only=True)


def embed(texts):
    with model_lock:
        return [vector.tolist() for vector in model().embed(texts)]


def enqueue(db, version_id):
    run(db,"INSERT INTO embedding_jobs(version_id,status,updated_at) VALUES(:v,'queued',:t) ON CONFLICT(version_id) DO NOTHING",v=version_id,t=now())


def drain_once():
    with transaction() as db:
        run(db,"UPDATE embedding_jobs SET status='queued' WHERE status='running' AND lease_until<:t AND attempts<3",t=now())
        run(db,"UPDATE embedding_jobs SET status='failed',error='索引恢复次数耗尽' WHERE status='running' AND lease_until<:t AND attempts>=3",t=now())
        job=one(db,"SELECT * FROM embedding_jobs WHERE status='queued' ORDER BY updated_at LIMIT 1")
        if not job: return
        version=one(db,'SELECT * FROM resource_versions WHERE id=:v',v=job['version_id'])
        token=uid()
        run(db,"UPDATE embedding_jobs SET status='running',attempts=attempts+1,lease_token=:token,lease_until=:until WHERE version_id=:v",token=token,until=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(),v=version['id'])
    try:
        if version['parse_status']!='ready' or version['index_status']!='indexed':
            raise ValueError('仅就绪并通过复核的正文可建立向量索引')
        chunks=[version['body'][offset:offset+800] for offset in range(0,len(version['body']),700)]
        if len(chunks)>2000: raise ValueError('正文分片过多，请拆分资料')
        vectors=embed(chunks)
        error=None
    except Exception:
        chunks=[];vectors=[];error='本地向量索引失败，请检查模型文件后重试'
    with transaction() as db:
        current=one(db,'SELECT * FROM embedding_jobs WHERE version_id=:v',v=version['id'])
        if current['lease_token']!=token or current['status']!='running': return
        run(db,'DELETE FROM vector_chunks WHERE version_id=:v',v=version['id'])
        if not error:
            from app.services.document_text import excerpt_at
            for ordinal,(chunk,vector) in enumerate(zip(chunks,vectors)):
                offset=ordinal*700
                # Locate the chunk against the immutable original body.
                import re
                locations=list(re.finditer(r'【([^】]+)】',version['body'][:offset+1]))
                location=locations[-1].group(1) if locations else f'正文字符 {offset}–{offset+len(chunk)}'
                insert(db,'vector_chunks',id=uid(),version_id=version['id'],ordinal=ordinal,body=chunk,location=location,embedding=dump(vector),model=MODEL)
        run(db,'UPDATE embedding_jobs SET status=:status,error=:error,updated_at=:t WHERE version_id=:v',status='failed' if error else 'ready',error=error,t=now(),v=version['id'])


def cosine(left,right):
    import math
    denominator=math.sqrt(sum(x*x for x in left)*sum(x*x for x in right))
    return sum(x*y for x,y in zip(left,right))/denominator if denominator else 0
