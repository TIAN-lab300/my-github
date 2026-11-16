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
    <details><summary>如何启用联网搜索</summary><p>在启动后端的电脑上配置环境变量，然后重启服务。普通 DeepSeek 或 GPT 对话配置不会自动启用搜索。</p><p>Tavily：ZHIXING_SEARCH_PROVIDER=tavily，并设置 TAVILY_API_KEY。百炼：ZHIXING_SEARCH_PROVIDER=dashscope，并设置 DASHSCOPE_API_KEY，模型默认 qwen-plus。</p><p>密钥只在服务器本地设置，不要发到聊天或提交到 GitHub。具体步骤见 docs/search-service-setup.md。</p></details>
    <button disabled={busy} onClick={()=>api('/admin/search/status').then(setStatus).catch(error=>setMessage(error.message))}>刷新配置状态</button>
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
