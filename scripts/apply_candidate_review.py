"""Preserve business data before recording the explicitly requested review."""
import os,sys,json
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
os.environ['ZHIXING_DATA']=str(ROOT/'backend/data');sys.path.insert(0,str(ROOT/'backend'))
from app.cli import backup
from app.services.candidate_review import review_baseline
from app.core.db import DATA
destination=DATA/'backups'/('before-candidate-review-20261116-'+uuid4().hex[:8])
backup(destination)
result=review_baseline();result['backup']=str(destination)
(ROOT/'docs/evidence/implementation/candidate-technical-review-20261116.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='items'},ensure_ascii=True))
