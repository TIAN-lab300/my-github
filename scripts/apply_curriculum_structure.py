"""Back up production before adding the explicit curriculum structure."""
import json,os,sqlite3,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
os.environ['ZHIXING_DATA']=str(ROOT/'backend/data');sys.path.insert(0,str(ROOT/'backend'))
from app.cli import backup,migrate
from app.core.db import DATA
from app.services.curriculum_structure import import_structure,SOURCE,validate
validate(json.loads(SOURCE.read_text(encoding='utf-8')))
with sqlite3.connect(DATA/'zhixing.db') as db:
    revision=db.execute('SELECT version_num FROM alembic_version').fetchone()[0]
    if revision!='0024':raise SystemExit('Expected production revision 0024; inspect current state before reapplying.')
    tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'chunks%' AND name!='alembic_version'")]
    before={t:db.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0] for t in tables}
destination=DATA/'backups'/('before-curriculum-structure-20261115-'+uuid4().hex[:8])
backup(destination);migrate();result=import_structure()
with sqlite3.connect(DATA/'zhixing.db') as db:
    protected={t:n for t,n in before.items() if t not in ('learning_chapters','learning_skill_chapters','audit_logs')}
    if any(db.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0]!=n for t,n in protected.items()):raise SystemExit('Protected data counts changed')
    if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():raise SystemExit('Database integrity check failed')
    result.update(schema='0025',backup=str(destination),existing_business_counts_preserved=True,database_integrity='ok')
(ROOT/'docs/evidence/implementation/curriculum-structure-20261115.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True))
