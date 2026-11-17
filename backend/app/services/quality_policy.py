"""Versioned quality approval: legacy passing reports are retained, not silently upgraded."""
import hashlib,json
from app.core.db import one
from app.services.quality_rubric import RUBRIC_VERSION,INSTRUCTION_V4,checks

def describe(report):
    if not report:return {'rubric_version':None,'required_rubric':RUBRIC_VERSION,'current_rubric':False,'hard_pass':False,'approved':False}
    try:
        payload=json.loads(report['payload']);results=payload.get('results',[])
        current=payload.get('rubric_version')==RUBRIC_VERSION and payload.get('instruction_hash')==hashlib.sha256(INSTRUCTION_V4.encode()).hexdigest() and len(results)==60 and len({e['case']['id'] for e in results})==60 and all(e['case'].get('contract')==RUBRIC_VERSION for e in results)
        integrity=hashlib.sha256(report['payload'].encode()).hexdigest()==report['report_hash']
        passed=current and integrity and report['case_count']==60 and report['passed_count']==60 and all(all(checks(e['case'],e.get('response',{})).values()) for e in results)
        return {'rubric_version':payload.get('rubric_version'),'required_rubric':RUBRIC_VERSION,'current_rubric':current,'hard_pass':passed,'approved':passed and report['review_status']=='approved'}
    except (ValueError,TypeError,KeyError,AttributeError):
        return {'rubric_version':None,'required_rubric':RUBRIC_VERSION,'current_rubric':False,'hard_pass':False,'approved':False}

def quality_state(db,config_id):
    report=one(db,'SELECT * FROM model_quality_reports WHERE model_config_id=:c ORDER BY created_at DESC,rowid DESC LIMIT 1',c=config_id)
    return describe(report)


def config_fingerprint(config):
    fields=('id','model','endpoint','secret_env','timeout_seconds','max_tokens','temperature','prompt_version')
    return hashlib.sha256(json.dumps({k:config.get(k) for k in fields},sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def activation_state(db,config):
    quality=quality_state(db,config['id']) if config else describe(None)
    override=False
    if config:
        try:
            evaluation=json.loads(config['evaluation']);record=evaluation.get('quality_override',{})
            override=(evaluation.get('json_ok') is True and record.get('enabled') is True
                      and bool(record.get('reason','').strip()) and bool(record.get('actor_id'))
                      and record.get('config_fingerprint')==config_fingerprint(config))
        except (ValueError,TypeError,AttributeError):pass
    return {**quality,'override':override,'allowed':bool(quality['approved'] or override)}
