from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
import os
import asyncio
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import JSONResponse,FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.core.db import transaction,run,uid
from app.api import phone,auth,classes,resources,tasks,goals,profiles,models,management,evidence

@asynccontextmanager
async def lifespan(app):
    with transaction() as db:
        run(db,"UPDATE agent_runs SET status='interrupted',error='服务重启导致中断，可重试' WHERE status IN ('queued','running')")
    stop=asyncio.Event()
    async def consume(drain):
        while not stop.is_set():
            try:
                await asyncio.to_thread(drain)
            except Exception:
                import logging
                logging.getLogger(__name__).exception('Background consumer failed')
            try: await asyncio.wait_for(stop.wait(),timeout=5)
            except asyncio.TimeoutError: pass
    from app.services.profile_worker import drain_once as profile_once
    from app.services.parse_worker import drain_once as parse_once
    from app.services.vector_index import drain_once as vector_once
    workers=[asyncio.create_task(consume(profile_once)),asyncio.create_task(consume(parse_once)),asyncio.create_task(consume(vector_once))]
    try: yield
    finally:
        stop.set()
        await asyncio.gather(*workers)

app=FastAPI(title='知行智能学习平台',version='0.1.0',lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','testserver'])

@app.middleware('http')
async def safety(request:Request,call_next):
    request.state.request_id=uid()
    if request.method not in ('GET','HEAD','OPTIONS'):
        # All browser mutations must originate from the same host, including login.
        origin=request.headers.get('origin')
        site=request.headers.get('sec-fetch-site')
        allowed={'http://127.0.0.1:8000','http://localhost:8000','http://127.0.0.1:5173','http://localhost:5173','http://testserver'}
        allowed.add(str(request.base_url).rstrip('/'))
        if (origin and origin not in allowed) or site=='cross-site':
            return JSONResponse({'code':'CSRF_REJECTED','message':'请求来源不受信任'},403)
    response=await call_next(request)
    if response.status_code>=400 and request.url.path.startswith('/api/') and request.method not in ('GET','HEAD','OPTIONS'):
        from app.core.db import audit
        with transaction() as db:
            audit(db,getattr(request.state,'actor_id',None),'request_failed',request.url.path,detail=str(response.status_code),result='failed')
    response.headers['X-Request-ID']=request.state.request_id
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    if request.url.path.startswith('/api'): response.headers['Cache-Control']='no-store'
    return response

@app.exception_handler(HTTPException)
async def errors(request,exc):
    detail=exc.detail if isinstance(exc.detail,dict) else {'message':str(exc.detail),'code':'REQUEST_FAILED'}
    return JSONResponse({**detail,'request_id':getattr(request.state,'request_id','')},status_code=exc.status_code,headers=exc.headers)

for router in (auth.router,classes.router,resources.router,tasks.router,goals.router,profiles.router,models.router,management.router,evidence.router):
    app.include_router(router,prefix='/api/v1')

@app.get('/api/v1/health')
def health():
    from tempfile import TemporaryFile
    from sqlalchemy.exc import SQLAlchemyError
    from app.core.db import DATA, engine, one

    checks = {'database': 'unavailable', 'files': 'unavailable', 'model': 'unknown'}
    try:
        with engine.connect() as db:
            config = one(db, "SELECT secret_env FROM model_configs WHERE status='active' LIMIT 1")
            checks['database'] = 'ok'
            if config:
                checks['model'] = 'configured' if os.getenv(config['secret_env']) else 'missing_key'
            else:
                checks['model'] = 'not_configured'
    except SQLAlchemyError:
        pass
    try:
        with TemporaryFile(dir=DATA / 'files') as probe:
            probe.write(b'ok')
            probe.seek(0)
            if probe.read() == b'ok':
                checks['files'] = 'ok'
    except OSError:
        pass
    from importlib.util import find_spec
    from app.services.vector_index import MODEL_DIR
    checks['ocr']='available' if find_spec('rapidocr') else 'missing_dependency'
    checks['asr']='available' if find_spec('faster_whisper') and (MODEL_DIR/'whisper-tiny'/'model.bin').exists() else 'missing_dependency_or_model'
    checks['embedding']='available' if find_spec('fastembed') and (MODEL_DIR/'embeddings').exists() else 'missing_dependency_or_model'
    from app.services.web_evidence import search_status
    checks['search']='configured' if search_status()['configured'] else 'not_configured'
    ready = checks['database'] == checks['files'] == 'ok'
    return JSONResponse({'status': 'ok' if ready else 'degraded', 'version': '0.1.0',
                         'checks': checks}, status_code=200 if ready else 503)

dist=Path(__file__).resolve().parents[2]/'frontend'/'dist'
if not dist.exists(): dist=Path(__file__).resolve().parents[2].parent/'frontend'/'dist'
if dist.exists():
    app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')
    @app.get('/')
    def index(): return FileResponse(dist/'index.html')

app.include_router(phone.router,prefix="/api/v1")
