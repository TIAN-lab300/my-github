"""Record real provider outputs for a synthetic 60-case learning-plan evaluation."""
import json
from pathlib import Path
from app.core.db import transaction,one,now,dump,uid,insert
from app.core.security import fail


def save_report(destination,report):
    from app.core.db import uid
    temporary=destination.with_name(destination.name+'.tmp-'+uid())
    try:
        temporary.write_text(dump(report),encoding='utf-8')
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def cases():
    topics=[('函数','functions'),('递归','recursion'),('调用栈','stack')]
    rows=[]
    for topic,skill in topics:
        for index in range(20):
            budget=30+(index%5)*15
            missing=index%4==0
            rows.append({'id':f'{skill}-{index+1:02d}','topic':topic,'skill_id':skill,
                         'budget_minutes':budget,'evidence_available':not missing,
                         'prior_level':['未知','薄弱','已掌握'][index%3],
                         'preference':'文本' if index%2 else '视频',
                         'expected_status':'draft' if missing else 'candidate'})
    return rows


def evaluate(config_id,output,operator):
    from app.api.models import call_model
    if not operator.strip():raise ValueError('请填写实际执行人')
    with transaction() as db:
        config=one(db,'SELECT * FROM model_configs WHERE id=:id',id=config_id)
        if not config:raise ValueError('模型配置不存在')
    import os
    if not os.getenv(config['secret_env']):raise ValueError('服务端模型密钥尚未配置，未执行评价')
    destination=Path(output).resolve()
    if destination.exists():raise ValueError('评价输出目标已存在，请使用新文件名')
    results=[]
    report={'schema_version':1,'operator':operator,'model_config_id':config_id,'model':config['model'],
            'prompt_version':config['prompt_version'],'started_at':now(),'case_source':'项目生成的60个合成场景，非真实学生样本',
            'human_review':'pending','results':results}
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('x',encoding='utf-8') as stream:stream.write(dump(report))
    for case in cases():
        try:
            response=call_model(config,dump({'case':case,'instruction':'根据证据是否可用、预算和学习水平生成计划。返回status为draft或candidate，tasks为数组，每项含skill_id和正整数minutes，reason为原因说明。没有证据时保留draft，不能虚构引用。'}))
            tasks=response.get('tasks')
            valid=isinstance(tasks,list) and all(isinstance(task,dict) and task.get('skill_id')==case['skill_id'] and type(task.get('minutes')) is int and task['minutes']>0 for task in tasks)
            checks={'status':response.get('status')==case['expected_status'],
                    'budget':valid and sum(task['minutes'] for task in tasks)<=case['budget_minutes'],
                    'explanation':isinstance(response.get('reason'),str) and bool(response['reason'].strip()),
                    'nonempty_candidate':case['expected_status']=='draft' or bool(tasks)}
            results.append({'case':case,'response':response,'checks':checks,'automated_pass':all(checks.values()),'human_review':'pending'})
        except Exception:
            results.append({'case':case,'automated_pass':False,'error':'供应商调用失败或响应无效','human_review':'pending'})
        save_report(destination,report)
        print(f'评价进度 {len(results)}/60',flush=True)
    report.update(finished_at=now(),automated_passed=sum(result['automated_pass'] for result in results),total=len(results))
    import hashlib
    report['quality_report_id']=uid()
    payload=dump(report)
    with transaction() as db:
        insert(db,'model_quality_reports',id=report['quality_report_id'],model_config_id=config_id,operator=operator,
               case_count=len(results),passed_count=report['automated_passed'],payload=payload,
               report_hash=hashlib.sha256(payload.encode()).hexdigest(),created_at=now())
    save_report(destination,report)
    return report
