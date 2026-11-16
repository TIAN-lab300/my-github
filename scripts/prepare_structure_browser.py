"""Create an isolated, read-only UI acceptance sample, never production records."""
import os,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sample=ROOT/'backend/data'/('browser-structure-'+uuid4().hex[:8])
os.environ['ZHIXING_DATA']=str(sample);sys.path.insert(0,str(ROOT/'backend'))
from app.cli import migrate
from app.core.db import transaction,insert,now
from app.core.security import password
from app.services.public_catalog import import_catalog
from app.services.curriculum_structure import import_structure
migrate()
with transaction() as db:
    for name,role in [('admin','admin'),('student','student')]:
        insert(db,'users',id=name,username=name,name='验收'+name,role=role,password_hash=password('TestPassword123!'),must_change=0,created_at=now())
        if role=='student':insert(db,'budgets',user_id=name)
import_catalog();print(import_structure())
(ROOT/'backend/data/structure-browser-path.txt').write_text(str(sample),encoding='utf-8')
print(sample)
