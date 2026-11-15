import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
def runtime_info():
    release = json.loads((ROOT / 'release.json').read_text(encoding='utf-8'))
    return {**release, 'code_root': str(ROOT), 'app_file': str(ROOT / 'backend/app/main.py')}
