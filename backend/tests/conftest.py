import os,tempfile
from pathlib import Path
test_root=Path(__file__).resolve().parents[1]/'data'/'tests'
test_root.mkdir(parents=True,exist_ok=True)
os.environ['ZHIXING_DATA']=tempfile.mkdtemp(prefix='run-',dir=test_root)
import pytest
from fastapi.testclient import TestClient
from app.cli import migrate
from app.main import app
from app.core.db import transaction,insert,run,uid,now
from app.core.security import password

@pytest.fixture(autouse=True)
def clean():
    migrate()
    from app.core.db import engine
    with engine.begin() as db:
        db.exec_driver_sql('PRAGMA foreign_keys=OFF')
        tables=db.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='alembic_version' AND name NOT LIKE 'chunks%' ").fetchall()
        for (name,) in tables: db.exec_driver_sql('DELETE FROM '+name)
        db.exec_driver_sql('DELETE FROM chunks')
        db.exec_driver_sql('PRAGMA foreign_keys=ON')
    with transaction() as db:
        for name,role in [('admin','admin'),('teacher','teacher'),('teacher2','teacher'),('student','student'),('student2','student')]:
            insert(db,'users',id=name,username=name,name=name,role=role,password_hash=password('TestPassword123!'),must_change=0,created_at=now())
            if role=='student': insert(db,'budgets',user_id=name)
    yield

@pytest.fixture
def clients():
    clients={}
    for name in ('admin','teacher','teacher2','student','student2'):
        client=TestClient(app)
        r=client.post('/api/v1/auth/login',json={'username':name,'password':'TestPassword123!'})
        assert r.status_code==200,r.text
        clients[name]=client
    yield clients
    for c in clients.values(): c.close()
