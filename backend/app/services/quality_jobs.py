"""Local durable progress for explicitly requested model quality runs; no secrets persisted."""
import json,re,time
from pathlib import Path
from uuid import uuid4
from app.core.db import DATA,transaction,one,now,dump,audit
from app.core.security import fail
from app.services.quality_evaluation import evaluate,save_report
TOKEN=uuid4().hex

def folder():
    p=DATA/'quality-runs';p.mkdir(exist_ok=True);return p

def path_for(ident):
    if not re.fullmatch('[a-f0-9]{32}',ident):fail(404,'评价任务不存在')
    return folder()/(ident+'.job.json')

def read_job(config,ident):
    path=path_for(ident)
    if not path.exists():fail(404,'评价任务不存在')
    job=json.loads(path.read_text(encoding='utf-8'))
    if job['model_config_id']!=config:fail(404,'评价任务不属于该模型')
    if job['status'] in ('queued','running') and job.get('worker_token')!=TOKEN:
        job.update(status='interrupted',error='服务已重启，原评价中断；可重新执行，未完成结果不会自动批准',finished_at=now());save_report(path,job)
    report=folder()/(ident+'.report.json')
    if report.exists():
        try:
            current=json.loads(report.read_text(encoding='utf-8'));job['completed_cases']=len(current.get('results',[]));job['passed_count']=sum(bool(e.get('automated_pass')) for e in current.get('results',[]))
        except (OSError,ValueError):pass
    return {k:v for k,v in job.items() if k!='worker_token'}

def prepare_job(config,actor):
    import os
    with transaction() as db:
        c=one(db,'SELECT * FROM model_configs WHERE id=:c',c=config)
        if not c:fail(404,'模型配置不存在')
        if not os.getenv(c['secret_env']):fail(409,'当前服务进程缺少模型密钥，请通过云端启动脚本启动','MODEL_KEY_MISSING')
        for file in folder().glob('*.job.json'):
            job=json.loads(file.read_text(encoding='utf-8'))
            if job['status'] in ('queued','running') and job.get('worker_token')==TOKEN:fail(409,'已有质量评价运行，请等待完成')
        ident=uuid4().hex
        job={'id':ident,'model_config_id':config,'actor_id':actor,'operator':'管理员页面发起真实评价','status':'queued','worker_token':TOKEN,'completed_cases':0,'total':60,'created_at':now()}
        save_report(path_for(ident),job);audit(db,actor,'quality_evaluation_requested',config,ident)
    return job

def execute_job(config,ident):
    path=path_for(ident);job=json.loads(path.read_text(encoding='utf-8'));job.update(status='running',started_at=now());save_report(path,job)
    try:
        report=evaluate(config,folder()/(ident+'.report.json'),job['operator'])
        job.update(status='completed',completed_cases=60,passed_count=report['automated_passed'],report_id=report['quality_report_id'],finished_at=now())
    except Exception:
        job.update(status='failed',error='评价执行失败，请查看已完成的场景进度并核对模型与网络后重试；不会批准报告',finished_at=now())
    save_report(path,job)
