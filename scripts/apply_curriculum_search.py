"""Back up business data, persist course links, and build metadata-only FTS."""
import json,os,sqlite3,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
os.environ['ZHIXING_DATA']=str(ROOT/'backend/data');sys.path.insert(0,str(ROOT/'backend'))
from app.cli import backup,migrate
from app.core.db import DATA,transaction
from app.services.curriculum_search import rebuild
with sqlite3.connect(DATA/'zhixing.db') as db:
    version=db.execute('SELECT version_num FROM alembic_version').fetchone()[0]
    if version!='0025':raise SystemExit('Expected revision 0025; inspect existing migration state.')
    tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='alembic_version'")]
    before={t:db.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0] for t in tables}
destination=DATA/'backups'/('before-curriculum-search-20261116-'+uuid4().hex[:8])
backup(destination);migrate()
with transaction() as db:result=rebuild(db)
with sqlite3.connect(DATA/'zhixing.db') as db:
    assert all(db.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0]==n for t,n in before.items())
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    result.update(knowledge_points=db.execute('SELECT COUNT(*) FROM curriculum_catalog_skills').fetchone()[0],schema='0026',existing_counts_preserved=True,backup=str(destination))
(ROOT/'docs/evidence/implementation/curriculum-search-import.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True))
