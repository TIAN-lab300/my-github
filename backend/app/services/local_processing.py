"""Run media extraction with durable cancellation and a renewable ownership lease."""
from datetime import datetime, timedelta, timezone
import json
import os
import subprocess
import sys
import time
from app.core.db import DATA, transaction, one, run, now, uid


def process(version, job, token):
    output = DATA / (uid() + '.extraction.json')
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    child = subprocess.Popen(
        [sys.executable, '-m', 'app.services.media_extract',
         str(DATA / 'files' / version['storage_key']), job['operation'], str(output)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **options)
    deadline = time.monotonic() + 900
    try:
        while child.poll() is None:
            if time.monotonic() > deadline:
                raise ValueError('本地处理超过15分钟，请缩短资料后重试')
            with transaction() as db:
                current = one(db, 'SELECT status,lease_token FROM parse_jobs WHERE id=:id', id=job['id'])
                if current['status'] != 'running' or current['lease_token'] != token:
                    raise ValueError('处理已取消或执行权已转移')
                run(db, 'UPDATE parse_jobs SET lease_until=:until WHERE id=:id',
                    until=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(), id=job['id'])
            time.sleep(.5)
        if child.returncode != 0 or not output.exists():
            raise ValueError('本地处理进程失败，请检查依赖与模型文件')
        result = json.loads(output.read_text(encoding='utf-8'))
        if result.get('error'):
            raise ValueError(result['error'])
        if not isinstance(result.get('body'), str) or not result['body'].strip():
            raise ValueError('处理结果没有有效正文')
        return result
    finally:
        if child.poll() is None:
            child.kill()
        child.wait()
        output.unlink(missing_ok=True)
