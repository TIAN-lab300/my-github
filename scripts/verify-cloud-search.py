import os,sys,json,time
import httpx
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
os.environ['ZHIXING_SEARCH_PROVIDER']='dashscope'
from app.services.web_evidence import search_web
report={'provider':'dashscope','query':'Python 官方文档 函数 定义 return','scope':'来源列表连通验证，不代表网页正文已核实','passed':False}
started=time.monotonic()
try:
    results=search_web(report['query'])
    report.update(results=results,passed=bool(results))
except Exception as exc:
    report['error_type']=type(exc).__name__
    report['message']=('搜索服务60秒内未完成响应，请稍后再试或检查网络代理。' if isinstance(exc,httpx.ReadTimeout) else '无法连接搜索服务，请检查网络或代理。' if isinstance(exc,(httpx.ConnectTimeout,httpx.ConnectError)) else '搜索未返回可用来源，请检查服务配置和报告。')
report['elapsed_seconds']=round(time.monotonic()-started,2)
if not report['passed'] and 'message' not in report:report['message']='服务未返回可用的公开来源，不能判定联网搜索成功。'
destination=Path(os.getenv('ZHIXING_DATA',str(ROOT/'backend'/'data')))
destination.mkdir(parents=True,exist_ok=True)
path=destination/('search-probe-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASSED',report['passed']);print(report.get('message','已返回来源列表，正文仍需核实。'));print('REPORT',path)
sys.exit(0 if report['passed'] else 1)
