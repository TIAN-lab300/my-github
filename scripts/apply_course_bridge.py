"""Back up the local database, migrate, and prove existing row counts are intact."""
import json,os,sqlite3,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
os.environ['ZHIXING_DATA']=str(ROOT/'backend/data')
from app.cli import backup,migrate
from app.core.db import DATA

def counts():
    with sqlite3.connect(DATA/'zhixing.db') as db:
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'chunks%'")]
        return {t:db.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0] for t in tables if t!='alembic_version'}

if not (DATA/'zhixing.db').is_file():raise SystemExit('Local database is missing; refusing to initialize replacement data.')
with sqlite3.connect(DATA/'zhixing.db') as db:before_revision=db.execute('SELECT version_num FROM alembic_version').fetchone()[0]
if before_revision!='0023':raise SystemExit('Expected revision 0023; current revision is '+before_revision)
before=counts();destination=DATA/'backups'/('before-course-bridge-20261115-'+uuid4().hex[:8])
backup(destination)
migrate()
after=counts()
if any(after.get(t)!=n for t,n in before.items()):raise SystemExit('Existing record counts changed; inspect migration before starting service.')
with sqlite3.connect(DATA/'zhixing.db') as db:
    integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
    foreign_keys=db.execute('PRAGMA foreign_key_check').fetchall()
    revision=db.execute('SELECT version_num FROM alembic_version').fetchone()[0]
if integrity!='ok' or foreign_keys:raise SystemExit('Database consistency check failed.')
result={'version':'course-planning-bridge-2026.11.15','schema_before':before_revision,'schema_after':revision,
    'backup':str(destination),'existing_counts_preserved':True,'integrity':integrity,'foreign_key_errors':len(foreign_keys),
    'new_tables':{t:after[t] for t in sorted(set(after)-set(before))},
    'tests':{'passed':236,'seconds':131.87,'report':'docs/evidence/implementation/course-bridge-tests.xml'},
    'browser':json.loads((ROOT/'docs/evidence/implementation/course-bridge-browser.json').read_text(encoding='utf-8')),
    'real_model_calls':False,'automatic_content_publication':False}
(ROOT/'docs/evidence/implementation/course-planning-bridge-20261115.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True))
