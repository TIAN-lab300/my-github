"""Start and stop our own isolated HTTP process; leave other services untouched."""
import json, subprocess, sys, time, socket, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
with (ROOT/'http-check.log').open('w',encoding='utf-8') as log:
    process=subprocess.Popen([sys.executable,str(ROOT/'scripts/run.py'),'--port',str(port)],cwd=ROOT.parent,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:
        for _ in range(60):
            if process.poll() is not None:raise RuntimeError('Service exited before startup; see http-check.log')
            try:
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(f'http://127.0.0.1:{port}/api/v1/health',timeout=1) as response:health=json.load(response)
                break
            except OSError:time.sleep(.25)
        else:raise RuntimeError('Startup timeout')
        assert Path(health['runtime']['code_root'])==ROOT
        with opener.open(f'http://127.0.0.1:{port}/') as response:assert response.status==200
        (ROOT/'http-check.json').write_text(json.dumps({'health':health,'frontend_status':200,'started_from':str(ROOT.parent)},ensure_ascii=False,indent=2),encoding='utf-8')
        print('Real HTTP startup, health, root identity and frontend: PASS')
    finally:
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait()
