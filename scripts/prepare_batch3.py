import os
from pathlib import Path
os.environ['ZHIXING_DATA']=str(Path(__file__).resolve().parents[1]/'backend/data/batch3')
from app.cli import migrate
from app.core.db import transaction,one,insert,now
from app.core.security import password
migrate()
with transaction() as db:
    for name,role in [('teacher','teacher'),('teacher2','teacher'),('student','student'),('student2','student')]:
        if not one(db,'SELECT id FROM users WHERE id=:id',id=name):
            insert(db,'users',id=name,username=name,name=name,role=role,password_hash=password('AcceptanceOnly!123'),must_change=0,created_at=now())
            if role=='student':insert(db,'budgets',user_id=name)
print('Isolated batch3 database ready')
