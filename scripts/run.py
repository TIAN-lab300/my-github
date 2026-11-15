"""Fixed-root launcher, with a separate database and explicit source identity."""
import argparse, json, os, socket, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--check', action='store_true')
parser.add_argument('--port', type=int, default=8000)
args = parser.parse_args()
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / 'backend'))
os.environ['PYTHONPATH'] = str(ROOT / 'backend')
os.environ.setdefault('ZHIXING_DATA', str(ROOT / 'backend' / 'data'))
os.environ['ZHIXING_MODEL_DIR'] = str(ROOT / 'backend/data/models')
from app.runtime_version import runtime_info
from app.core.db import DATA
from app.cli import migrate
from alembic.config import Config
from alembic.script import ScriptDirectory
scripts = ScriptDirectory.from_config(Config(str(ROOT / 'backend/alembic.ini')))
if len(scripts.get_heads()) != 1: raise SystemExit('Expected one migration head')
if not args.check:
    with socket.socket() as probe:
        try: probe.bind(('127.0.0.1', args.port))
        except OSError: raise SystemExit(f'Port {args.port} is occupied. Stop old service or choose --port.')
migrate()
from app.main import app
import importlib
app_module = importlib.import_module('app.main')
if Path(app_module.__file__).resolve() != ROOT / 'backend/app/main.py': raise SystemExit('Unexpected source path')
print(json.dumps({**runtime_info(), 'data_root':str(DATA), 'migration_head':scripts.get_current_head()}, ensure_ascii=False), flush=True)
if not (ROOT / 'frontend/dist/index.html').is_file(): raise SystemExit('Frontend build missing')
if args.check:
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        response = client.get('/api/v1/health')
        if response.status_code != 200: raise SystemExit(response.text)
        if client.get('/').status_code != 200: raise SystemExit('Frontend unavailable')
        print(response.text)
else:
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=args.port)
