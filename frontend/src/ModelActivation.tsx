import {useRef,useState} from 'react';
import {api,ApiError} from './api';

export function ModelActivation({config,onChanged}:{config:any;onChanged:()=>void}){
  const [reason,setReason]=useState('管理员试运行，质量评价结果保留');
  const [busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState('');
  const lock=useRef(false);
  const eligible=['approved','active'].includes(config.status);
  async function activate(){
    if(lock.current)return;
    if(!reason.trim()){setError('请填写激活原因');return}
    lock.current=true;setBusy(true);setMessage('正在提交激活请求…');setError('');
    try{
      await api('/admin/model-configs/'+config.id+'/activate','POST',{allow_unqualified:true,reason:reason.trim()});
      const configs=await api<any[]>('/admin/model-configs');
      if(!configs.some(c=>c.id===config.id&&c.status==='active'))throw new Error('服务未返回已激活状态，请刷新配置检查');
      setMessage(config.model+' 已激活，可在学生端选择云端规划和学习辅导。');onChanged();
    }catch(e){
      setMessage('');
      const detail=(e as Error).message;
      const legacy=detail.includes('请先完成当前teaching-v4的60场景评价并逐例复核批准');
      setError(legacy?'8000端口仍在运行旧版后端，未识别“无需60/60”参数。请在原服务窗口按Ctrl+C停止，再运行本项目“启动云端搜索版.cmd”；刷新网页不能替代重启后端。':e instanceof ApiError&&e.status===404?'后端尚无此激活接口，请重启本项目的云端搜索版服务。':detail);
    }finally{lock.current=false;setBusy(false)}
  }
  return <section aria-label={'模型激活 '+config.id}>
    <p>当前状态：{config.status==='active'?'已激活':config.status==='approved'?'连通性已通过，尚未激活':'请先完成真实能力试验'}。质量评价未通过也可由管理员启用，原分数保留。</p>
    <label>激活原因<input value={reason} onChange={e=>setReason(e.target.value)} maxLength={1000} disabled={busy}/></label>
    <button type="button" disabled={busy||!eligible} onClick={()=>void activate()}>{busy?'正在激活…':config.status==='active'?'重新激活（无需60/60）':'激活（无需60/60）'}</button>
    {!eligible&&<p>请先点击本卡片的“真实能力试验”，连通成功后即可激活。</p>}
    {message&&<p role="status">{message}</p>}{error&&<p role="alert">激活失败：{error}</p>}
  </section>
}
