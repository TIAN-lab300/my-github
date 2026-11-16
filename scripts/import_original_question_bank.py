"""Back up the selected local installation and import its original foundation bank."""
import argparse,json,os,sqlite3,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--data-root',type=Path,default=ROOT/'backend/data')
args=parser.parse_args()
os.environ['ZHIXING_DATA']=str(args.data_root.resolve());sys.path.insert(0,str(ROOT/'backend'))
from app.core.db import DATA
from app.cli import backup,migrate
from app.services.original_question_bank import import_bank,load_bank
bank,digest=load_bank()
if not (DATA/'zhixing.db').is_file():raise SystemExit('先初始化系统账号和课程目录，再导入题库。')
with sqlite3.connect(DATA/'zhixing.db') as db:
    protected=['users','classes','resources','resource_versions','learning_assessments','learning_responses','question_review_candidates']
    before={t:db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in protected}
destination=DATA/'backups'/('before-original-bank-20261116-'+uuid4().hex[:8])
backup(destination);migrate();result=import_bank()
with sqlite3.connect(DATA/'zhixing.db') as db:
    assert all(db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0]==n for t,n in before.items())
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    result.update(published_questions=db.execute("SELECT COUNT(*) FROM learning_question_versions WHERE status='published'").fetchone()[0],
        covered_courses=db.execute("SELECT COUNT(DISTINCT course_id) FROM learning_question_versions WHERE status='published'").fetchone()[0],
        covered_skills=db.execute("SELECT COUNT(DISTINCT skill_id) FROM learning_question_versions WHERE status='published'").fetchone()[0],
        project_rubrics=db.execute('SELECT COUNT(*) FROM learning_project_rubrics').fetchone()[0],
        phase_counts=dict(db.execute("SELECT phase,COUNT(*) FROM learning_question_versions WHERE status='published' GROUP BY phase").fetchall()),
        existing_data_preserved=True,backup=str(destination),content_hash=digest)
output=DATA/'original-bank-import-result.json';output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=True))
