"""SQLAlchemy connection and a small explicit SQL persistence boundary."""
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, event, text

DATA = Path(os.getenv('ZHIXING_DATA', str(Path(__file__).resolve().parents[2] / 'data')))
DATA.mkdir(parents=True, exist_ok=True)
(DATA / 'files').mkdir(exist_ok=True)
engine = create_engine('sqlite:///' + (DATA / 'zhixing.db').as_posix(), connect_args={'check_same_thread': False, 'timeout': 15})

@event.listens_for(engine, 'connect')
def configure(dbapi, _):
    dbapi.execute('PRAGMA foreign_keys=ON')
    dbapi.execute('PRAGMA journal_mode=WAL')

def now():
    return datetime.now(timezone.utc).isoformat()

def uid():
    return uuid4().hex

def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)

def rows(db, sql, **params):
    return [dict(r) for r in db.execute(text(sql), params).mappings()]

def one(db, sql, **params):
    found = rows(db, sql, **params)
    return found[0] if found else None

def run(db, sql, **params):
    return db.execute(text(sql), params)

@contextmanager
def transaction():
    with engine.begin() as db:
        # Serialize short business writes, including version checks and reservations.
        db.exec_driver_sql('BEGIN IMMEDIATE')
        yield db

def insert(db, table, **values):
    keys = ','.join(values)
    placeholders = ','.join(':'+k for k in values)
    run(db, f'INSERT INTO {table} ({keys}) VALUES ({placeholders})', **values)

def audit(db, actor, action, target, detail='',result='success'):
    insert(db, 'audit_logs', id=uid(), actor_id=actor, action=action, target_id=target, detail=detail, result=result, created_at=now())

def touch(db, student):
    run(db, 'UPDATE users SET watermark=watermark+1 WHERE id=:id', id=student)
    source=one(db,'SELECT watermark FROM users WHERE id=:id',id=student)
    if source:
        insert(db,'profile_refresh_events',id=uid(),student_id=student,source_watermark=source['watermark'],created_at=now())
