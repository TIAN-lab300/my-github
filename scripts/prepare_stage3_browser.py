"""Prepare isolated acceptance accounts and a real active learning path."""
import os, sys, json, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
sys.path.insert(0, str(ROOT/'backend/tests'))
folder=Path(tempfile.mkdtemp(prefix='stage3-browser-',dir=ROOT/'backend/data'))
os.environ['ZHIXING_DATA']=str(folder)
os.environ['ZHIXING_MODEL_DIR']=str(ROOT/'backend/data/models')
from app.cli import migrate
migrate()
from app.core.db import transaction,insert,now
from app.core.security import password
from app.main import app
from fastapi.testclient import TestClient
from test_batch5 import active_path
from test_stage3 import publish
with transaction() as db:
    for name,role in [('admin','admin'),('teacher','teacher'),('student','student')]:
        insert(db,'users',id=name,username=name,name=name,role=role,password_hash=password('Acceptance123!'),must_change=0,created_at=now())
        if role=='student':insert(db,'budgets',user_id=name)
clients={}
for name in ('admin','teacher','student'):
    client=TestClient(app)
    assert client.post('/api/v1/auth/login',json={'username':name,'password':'Acceptance123!'}).status_code==200
    clients[name]=client
cid,rid,gid,pid=active_path(clients)
for index in (0,1):publish(clients,index)
(ROOT/'stage3-browser-config.json').write_text(json.dumps({'data':str(folder),'path':pid,'class':cid},ensure_ascii=False),encoding='utf-8')
print('Isolated browser data prepared')
