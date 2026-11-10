"""Docker-only grading. Student code never executes in the application process."""
from datetime import datetime,timedelta,timezone
import json
import os
import shutil
import subprocess
from threading import Thread
import time
from app.core.db import transaction,one,run,insert,uid,now,dump,touch
from app.core.security import class_access,fail

HARNESS="import sys,json,io; p=json.loads(sys.stdin.read()); sys.stdin=io.StringIO(p['stdin']); exec(compile(p['code'],'<submission>','exec'),{'__name__':'__main__'})"


def execute_case(code,case):
    docker=shutil.which('docker')
    if not docker:fail(503,'尚未安装或配置Docker代码隔离运行环境','CODE_SANDBOX_UNAVAILABLE')
    name='zhixing-judge-'+uid()
    image=os.getenv('ZHIXING_CODE_IMAGE','python:3.12-slim')
    options={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
    command=[docker,'run','--rm','--pull=never','--name',name,'--network','none',
             '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
             '--user','65534:65534','--memory','128m','--memory-swap','128m',
             '--cpus','0.5','--pids-limit','32','--ulimit','nofile=64:64',
             '--tmpfs','/tmp:rw,noexec,nosuid,size=16m','-i',image,'python','-I','-S','-c',HARNESS]
    child=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,**options)
    parts=[];size=[0];overflow=[False]
    def read_output():
        while True:
            part=child.stdout.read1(4096)
            if not part:return
            size[0]+=len(part)
            if size[0]>65536:
                overflow[0]=True;return
            parts.append(part)
    reader=Thread(target=read_output,daemon=True);reader.start()
    try:
        child.stdin.write(json.dumps({'code':code,'stdin':case['stdin']}).encode())
        child.stdin.close()
        deadline=time.monotonic()+5
        while child.poll() is None and not overflow[0] and time.monotonic()<deadline:
            time.sleep(.05)
        timed_out=child.poll() is None
        if timed_out or overflow[0]:
            subprocess.run([docker,'rm','-f',name],timeout=5,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**options)
            if child.poll() is None:child.kill()
        child.wait(timeout=5);reader.join(timeout=2)
        output=b''.join(parts).decode('utf-8',errors='replace')
        if child.returncode in (125,126,127):fail(503,'Docker服务或预置Python镜像不可用','CODE_SANDBOX_UNAVAILABLE')
        return {'passed':not timed_out and not overflow[0] and child.returncode==0 and output.rstrip()==case['stdout'].rstrip(),
                'status':'output_limit' if overflow[0] else 'timeout' if timed_out else 'ok' if child.returncode==0 else 'runtime_error'}
    except (OSError,subprocess.SubprocessError):
        fail(503,'隔离运行环境暂时不可用','CODE_SANDBOX_UNAVAILABLE')
    finally:
        if child.poll() is None:child.kill()
        child.wait()
        subprocess.run([docker,'rm','-f',name],timeout=5,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**options)


def submit_code(task_id,body,user):
    if not body.text.strip():fail(422,'请填写Python程序')
    token=uid()
    with transaction() as db:
        task=one(db,'SELECT t.*,a.id AS assignment_id,a.status AS assignment_status FROM tasks t JOIN assignments a ON a.task_id=t.id WHERE t.id=:id AND a.student_id=:u',id=task_id,u=user['id'])
        if not task:fail(404,'任务未分配给你')
        classroom=class_access(db,user,task['class_id'])
        previous=one(db,'SELECT * FROM attempts WHERE assignment_id=:a',a=task['assignment_id'])
        if previous:return previous
        if classroom['status']!='active' or task['status']!='published' or task['assignment_status']=='cancelled':fail(409,'任务不接受新提交')
        lease=one(db,'SELECT * FROM code_runs WHERE assignment_id=:a',a=task['assignment_id'])
        if lease and lease['status']=='running' and lease['lease_until']>now():fail(409,'判题正在进行，请稍后查看结果')
        cases=json.loads(task['code_cases'])
        if not cases:fail(409,'代码任务缺少测试用例')
        run(db,"INSERT INTO code_runs(assignment_id,token,status,lease_until,updated_at) VALUES(:a,:token,'running',:lease,:t) ON CONFLICT(assignment_id) DO UPDATE SET token=:token,status='running',lease_until=:lease,error=NULL,updated_at=:t",a=task['assignment_id'],token=token,lease=(datetime.now(timezone.utc)+timedelta(seconds=300)).isoformat(),t=now())
    try:
        results=[execute_case(body.text,case) for case in cases]
        with transaction() as db:
            current=one(db,'SELECT * FROM code_runs WHERE assignment_id=:a',a=task['assignment_id'])
            latest=one(db,'SELECT t.version,t.status,a.status AS assignment_status FROM tasks t JOIN assignments a ON a.task_id=t.id WHERE a.id=:a',a=task['assignment_id'])
            class_access(db,user,task['class_id'])
            if current['token']!=token or latest['version']!=task['version'] or latest['status']!='published' or latest['assignment_status']=='cancelled':fail(409,'判题期间任务或成员状态已变化')
            score=sum(result['passed'] for result in results)/len(results)
            attempt_id=uid()
            insert(db,'attempts',id=attempt_id,assignment_id=task['assignment_id'],student_id=user['id'],class_id=task['class_id'],answers=dump({'text':body.text}),feedback=dump([{'message':f'测试 {index+1} '+result['status'],'correct':result['passed']} for index,result in enumerate(results)]),status='scored',score=score,minutes=body.minutes,late=int(now()>task['due_at']),created_at=now())
            run(db,"UPDATE assignments SET status='completed',first_completed_at=:t,draft='{}' WHERE id=:a",t=now(),a=task['assignment_id'])
            run(db,"UPDATE reservations SET status='completed' WHERE source_type='teacher' AND source_id=:a",a=task['assignment_id'])
            run(db,"UPDATE code_runs SET status='ready',updated_at=:t WHERE assignment_id=:a",t=now(),a=task['assignment_id'])
            touch(db,user['id'])
            return one(db,'SELECT * FROM attempts WHERE id=:id',id=attempt_id)
    except Exception:
        with transaction() as db:
            run(db,"UPDATE code_runs SET status='failed',error='判题失败，可重试',updated_at=:t WHERE assignment_id=:a AND token=:token",t=now(),a=task['assignment_id'],token=token)
        raise
