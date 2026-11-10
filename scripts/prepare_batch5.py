import os
from pathlib import Path
acceptance_root=(Path(__file__).resolve().parents[1]/'backend/data').resolve()
target=Path(os.environ.get('ZHIXING_ACCEPTANCE_DIR',str(acceptance_root/'batch5'))).resolve()
if not target.is_relative_to(acceptance_root):
    raise RuntimeError('Acceptance data must stay inside backend/data')
os.environ['ZHIXING_DATA']=str(target)
from app.cli import migrate
from app.core.db import transaction,one,insert,now
from app.core.security import password
migrate()
with transaction() as db:
    for name,role in [('admin','admin'),('teacher','teacher'),('teacher2','teacher'),('student','student'),('student2','student')]:
        if not one(db,'SELECT id FROM users WHERE id=:id',id=name):
            insert(db,'users',id=name,username=name,name=name,role=role,password_hash=password('AcceptanceOnly!123'),must_change=0,created_at=now())
            if role=='student':insert(db,'budgets',user_id=name)
print('Isolated batch5 database ready')
