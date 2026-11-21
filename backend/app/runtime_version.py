import json,hashlib,os
from datetime import datetime,timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
LOADED_AT=datetime.now(timezone.utc).isoformat()
LOADED_RELEASE=json.loads((ROOT/'release.json').read_text(encoding='utf-8'))
_sources=('backend/app/main.py','backend/app/api/learning_catalog.py','backend/app/api/question_bank.py')
LOADED_BUILD=hashlib.sha256(b''.join((ROOT/p).read_bytes() for p in _sources)).hexdigest()[:16]

def runtime_info():
    disk=json.loads((ROOT/'release.json').read_text(encoding='utf-8'))
    return {**LOADED_RELEASE,'disk_release_version':disk.get('version'),'loaded_at':LOADED_AT,'loaded_build_id':LOADED_BUILD,
        'process_id':os.getpid(),'capabilities':[],
        'code_root':str(ROOT),'app_file':str(ROOT/'backend/app/main.py')}
