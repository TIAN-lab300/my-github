"""Isolated acceptance data, never connected to the running user's database."""
import os
from pathlib import Path
os.environ['ZHIXING_DATA']=str(Path(__file__).resolve().parents[1]/'backend/data/batch20')
from app.cli import migrate
from app.core.db import *
from app.core.security import password
migrate()
with transaction() as db:
    for name,role in [('admin','admin'),('teacher','teacher'),('student','student'),('first','student')]:
        if not one(db,'SELECT id FROM users WHERE id=:id',id=name):
            insert(db,'users',id=name,username=name,name=name,role=role,password_hash=password('AcceptanceOnly!123'),must_change=int(name=='first'),created_at=now())
            if role=='student': insert(db,'budgets',user_id=name)
print('Isolated batch20 database ready')
