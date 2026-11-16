"""Back up and migrate an existing installation, then add original lesson versions."""
import argparse,json,os,sqlite3,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--data-root',type=Path,default=ROOT/'backend/data');args=parser.parse_args()
os.environ['ZHIXING_DATA']=str(args.data_root.resolve());sys.path.insert(0,str(ROOT/'backend'))
from app.core.db import DATA
from app.cli import backup,migrate
from app.services.engineering_materials import import_materials
with sqlite3.connect(DATA/'zhixing.db') as db:
    protected=['users','classes','learning_question_versions','learning_assessments','learning_responses','question_review_candidates','goals','diagnoses','attempts','observations','paths','reservations']
    before={t:db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in protected}
destination=DATA/'backups'/('before-engineering-goals-20261116-'+uuid4().hex[:8]);backup(destination);migrate();result=import_materials()
with sqlite3.connect(DATA/'zhixing.db') as db:
    assert all(db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0]==n for t,n in before.items())
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    result.update(schema=db.execute('SELECT version_num FROM alembic_version').fetchone()[0],
        total_material_links=db.execute('SELECT COUNT(*) FROM learning_material_links').fetchone()[0],existing_records_preserved=True,backup=str(destination))
(DATA/'engineering-goals-install-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=True))
