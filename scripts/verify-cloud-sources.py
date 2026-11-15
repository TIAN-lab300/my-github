"""Three real synthetic probes; no student or course records are changed."""
import json,os,sys,sqlite3
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
os.environ.setdefault('ZHIXING_DATA',str(ROOT/'backend'/'data'))
DATA_ROOT=Path(os.environ['ZHIXING_DATA'])
from app.api.models import call_model
from app.services.cloud_contracts import validate_output

def main():
    with sqlite3.connect('file:'+str(DATA_ROOT/'zhixing.db').replace(chr(92),'/')+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        row=db.execute("SELECT * FROM model_configs WHERE status='active' ORDER BY created_at DESC LIMIT 1").fetchone()
    if not row:raise SystemExit('No active model configuration')
    config=dict(row)
    if not os.getenv(config['secret_env']):raise SystemExit('Model key is missing in this process')
    source={'version_id':'synthetic-functions-v1','supported_skills':['functions'],'excerpt':'函数通过参数接收输入，通过return返回结果。double(x)返回x*2，因此double(3)返回6。练习计算double(0)和double(-1)的返回值。'}
    report={'type':'isolated_real_provider_probe','student_data_modified':False,'model':config['model'],'results':[]}
    destination=DATA_ROOT/('source-probe-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
    def probe(name,agent,payload,predicate):
        try:
            response=call_model(config,json.dumps({'agent':agent,'output_contract_version':'planning-v2','task':payload},ensure_ascii=False))
            validate_output(agent,response)
            passed=bool(predicate(response))
            entry={'name':name,'passed':passed,'response':response}
        except Exception as exc:
            entry={'name':name,'passed':False,'error_code':getattr(exc,'detail',{}).get('code','PROBE_FAILED') if isinstance(getattr(exc,'detail',{}),dict) else 'PROBE_FAILED'}
        report['results'].append(entry)
        destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(name,entry['passed'],flush=True)
    def valid_plan(r):
        ts=r.get('tasks',[])
        return len(ts)==1 and ts[0]['skill_id']=='functions' and ts[0]['minutes']<=30 and ts[0]['citation_version_ids']==[source['version_id']]
    probe('nonempty_plan','PathBuildingAgent',{'sources':[source],'tasks':[{'skill_id':'functions','minutes':30,'prerequisites':[]}],'required_task_count':1,'allowed_skill_ids':['functions'],'instruction':'返回reason和tasks。只生成一个functions任务，总时长不超过30分钟，含skill_id、正整数minutes、具体instructions、citation_version_ids。只依据给定片段安排阅读、练习与测评，不添加外部资源。'},valid_plan)
    instruction='对照sources检查任务内容是否有依据。输出approved布尔值和issues字符串数组。未覆盖的额外结论、外部资源必须拒绝并说明；内容有完整支持时批准且issues为空。'
    for name,activity,expected in [('supported_activity','计算double(0)和double(-1)，说明参数和返回值的关系。',True),('unsupported_activity','依据该资料证明所有Python递归函数都被自动优化为常量栈空间，并观看资料指定的量子计算视频。',False)]:
        probe(name,'PlanReviewAgent',{'sources':[source],'tasks':[{'skill_id':'functions','instructions':activity,'citations':[{'version_id':source['version_id']}]}],'rules':[],'instruction':instruction},lambda r,e=expected:r['approved'] is e and (not r['issues'] if e else bool(r['issues'])))
    report['passed']=all(x['passed'] for x in report['results'])
    report['scope']='Synthetic direct-agent probes, not full end-to-end planning or a guarantee of semantic correctness.'
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('REPORT',destination,flush=True)
    return 0 if report['passed'] else 1
if __name__=='__main__':sys.exit(main())
