"""Record real provider outputs for a synthetic 60-case learning-plan evaluation."""
import json
from pathlib import Path
from app.core.db import transaction,one,now,dump,uid,insert
from app.core.security import fail
from app.services.quality_rubric import checks as grade,INSTRUCTION_V4 as INSTRUCTION,RUBRIC_VERSION


def save_report(destination,report):
    from app.core.db import uid
    temporary=destination.with_name(destination.name+'.tmp-'+uid())
    try:
        temporary.write_text(dump(report),encoding='utf-8')
        import time
        for attempt in range(5):
            try:temporary.replace(destination);break
            except PermissionError:
                if attempt==4:raise
                time.sleep(.1*(attempt+1))
    finally:
        temporary.unlink(missing_ok=True)


def cases():
    from app.services.quality_assets import enrich_v4
    from app.services.planning_rules import graph_snapshot
    with transaction() as db:graph,version=graph_snapshot(db)
    nodes={n['id']:n for n in graph};result=[]
    topics=[('函数','functions'),('递归','recursion'),('调用栈','stack')]
    for topic_index,(topic,skill) in enumerate(topics):
        if skill not in nodes:raise ValueError('当前图谱不包含基础评价主题，需建立适配该图谱的质量集')
        prerequisites=nodes[skill]['prerequisites'];prerequisite=prerequisites[0] if prerequisites else 'expressions'
        if prerequisite not in ('expressions','functions','recursion','stack'):raise ValueError('基础质量集缺少该先修的执行素材')
        for level_index,level in enumerate(['未知','薄弱','已掌握']):
            for prior_index,prior in enumerate(['unknown','weak','mastered']):
                for available in [False,True]:
                    index=len([c for c in result if c['skill_id']==skill])+1
                    case={'id':f'{skill}-{index:02d}','topic':topic,'skill_id':skill,'budget_minutes':[30,45,60,75,90][(index-1)%5],
                        'prior_level':level,'prerequisite_state':prior,'evidence_available':available,'review_mastered':level=='已掌握' and prior!='unknown',
                        'preference':'文本' if (level_index+prior_index+int(available)+topic_index)%2 else '视频',
                        'graph_version':version,'prerequisite_basis':'当前图谱先修' if prerequisites else '显式声明的表达式基础能力，不冒充图谱节点'}
                    result.append(enrich_v4(case,prerequisite))
        for index,incomplete in [(19,True),(20,False)]:
            result.append(enrich_v4({'id':f'{skill}-{index:02d}','topic':topic,'skill_id':skill,'budget_minutes':30,
                'prior_level':'薄弱' if incomplete else '已掌握','prerequisite_state':'weak' if incomplete else 'mastered',
                'evidence_available':incomplete,'asset_incomplete':incomplete,'review_mastered':False,
                'preference':'文本' if incomplete else '视频','graph_version':version,'prerequisite_basis':'当前图谱或明确外部能力'},prerequisite))
    return result


def evaluate_case(config,case,call_model):
    """Keep every provider attempt; repairs are model-generated, never patched by graders."""
    from fastapi import HTTPException
    model_case={key:value for key,value in case.items() if key!='expected_status'}
    attempts=[];feedback=None
    for attempt in range(3):
        request={'case':model_case,'instruction':INSTRUCTION}
        if feedback:request['repair']=feedback
        try:
            response=call_model(config,dump(request))
            checks=grade(case,response)
            failed=[key for key,value in checks.items() if not value]
            attempts.append({'attempt':attempt+1,'response':response,'checks':checks,'automated_pass':not failed})
            if not failed:break
            feedback={'failed_checks':failed,'previous_response':response,
                      'instruction':'按原始case和规则重新返回完整JSON。修正失败字段及相关任务，不修改素材、预算、证据和题量；禁止只声称检查通过。'}
        except HTTPException as exc:
            detail=exc.detail if isinstance(exc.detail,dict) else {}
            code=detail.get('code','MODEL_CALL_FAILED')
            attempts.append({'attempt':attempt+1,'error':'模型调用失败','error_code':code,'automated_pass':False})
            # Auth, quota, configuration and connectivity are not teaching repairs.
            if code not in ('MODEL_JSON_INVALID','MODEL_OUTPUT_TRUNCATED'):break
            feedback={'failed_checks':['response_format'],'error_code':code,
                      'instruction':'上次响应无有效完整JSON，请简洁返回全部必需字段，缩短reason，不省略任务及trace字段。'}
        except Exception:
            attempts.append({'attempt':attempt+1,'error':'评价处理失败','error_code':'QUALITY_PROCESSING_ERROR','automated_pass':False})
            break
    final=attempts[-1]
    return {'case':case,**{k:v for k,v in final.items() if k!='attempt'},'attempts':attempts,
            'repair_count':len(attempts)-1,'human_review':'pending'}


def evaluate(config_id,output,operator,previous=None):
    from app.api.models import call_model
    if not operator.strip():raise ValueError('请填写实际执行人')
    with transaction() as db:
        config=one(db,'SELECT * FROM model_configs WHERE id=:id',id=config_id)
        if not config:raise ValueError('模型配置不存在')
    import os
    if not os.getenv(config['secret_env']):raise ValueError('服务端模型密钥尚未配置，未执行评价')
    destination=Path(output).resolve()
    if destination.exists():raise ValueError('评价输出目标已存在，请使用新文件名')
    import hashlib
    prompt_hash=hashlib.sha256(INSTRUCTION.encode()).hexdigest()
    cached={}
    if previous:
        prior=json.loads(Path(previous).read_text(encoding='utf-8-sig'))
        if prior.get('model_config_id')!=config_id or prior.get('model')!=config['model'] or prior.get('prompt_version')!=config['prompt_version']:
            raise ValueError('旧报告的模型配置不匹配，不能复用')
        if prior.get('rubric_version')==RUBRIC_VERSION and prior.get('instruction_hash')==prompt_hash:
            cached={entry['case']['id']:entry for entry in prior['results']}
    results=[]
    report={'schema_version':4,'max_repair_attempts':2,'rubric_version':RUBRIC_VERSION,'instruction_hash':prompt_hash,'previous_report':str(previous) if previous else None,'operator':operator,'model_config_id':config_id,'model':config['model'],
            'prompt_version':config['prompt_version'],'started_at':now(),'case_source':'项目生成的60个合成场景，非真实学生样本',
            'human_review':'pending','results':results}
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('x',encoding='utf-8') as stream:stream.write(dump(report))
    for case in cases():
        old=cached.get(case['id'])
        if old and old.get('case')==case and isinstance(old.get('response'),dict) and all(grade(case,old['response']).values()):
            results.append({**old,'checks':grade(case,old['response']),'human_review':'pending','reused_from':str(previous)})
            save_report(destination,report)
            print(f'复用已通过场景 {case["id"]}',flush=True)
            continue
        results.append(evaluate_case(config,case,call_model))
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

