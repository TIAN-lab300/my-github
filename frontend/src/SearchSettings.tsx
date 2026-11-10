import {useEffect,useState} from 'react';
import {api} from './api';

export function SearchSettings(){
  const [status,setStatus]=useState<any>(null);
  const [message,setMessage]=useState('');
  const [busy,setBusy]=useState(false);
  useEffect(()=>{api('/admin/search/status').then(setStatus).catch(error=>setMessage(error.message))},[]);
  return <section className="card"><h2>联网搜索服务</h2>
    {status&&<p>{status.provider} · {status.configured?'服务端已配置':'尚未配置'}</p>}
    <p>服务端支持 Tavily 或百炼原生搜索。能力试验会发起一次真实请求，搜索摘要仍需教师核实。</p>
    <button disabled={busy||!status?.configured} onClick={async()=>{
      setBusy(true);
      try{
        const result:any=await api('/admin/search/evaluate','POST');
        setMessage(result.provider_search_verified?'已取得真实搜索来源 '+result.result_count+' 条，正文尚未验证':'服务未返回可用来源');
      }catch(error){setMessage((error as Error).message)}finally{setBusy(false)}
    }}>执行真实搜索能力试验</button>
    {message&&<p role="status">{message}</p>}
  </section>;
}
