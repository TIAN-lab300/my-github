import {useEffect,useState} from 'react';
import {api,ApiError} from './api';

function qualityError(error:unknown){
  if(error instanceof ApiError&&error.status===404&&error.message==='Not Found')return '当前后端没有新版质量评价接口，可能仍在运行旧服务。请关闭原服务窗口，从 D:\\卓越工程 重新运行“启动云端搜索版.cmd”，然后刷新页面重试。仅刷新网页不会更新后端。';
  return (error as Error).message;
}

export function ModelQuality({configId,onChanged}:{configId:string;onChanged?:()=>void}){
  const [reports,setReports]=useState<any[]>([]);
  const [selected,setSelected]=useState<any>(null);
  const [reviewed,setReviewed]=useState<string[]>([]);
  const [comment,setComment]=useState('');
  const [message,setMessage]=useState('');
  const [busy,setBusy]=useState(false);
  const [job,setJob]=useState<any>(null);
  const base='/admin/model-configs/'+configId+'/quality-reports';
  async function load(){setReports(await api<any[]>(base))}
  useEffect(()=>{load().catch(error=>setMessage(error.message))},[configId]);

  useEffect(()=>{
    const key='zhixing-quality-job:'+configId;const saved=localStorage.getItem(key);
    if(saved)api('/admin/model-configs/'+configId+'/quality-runs/'+saved).then(setJob).catch(()=>localStorage.removeItem(key));
  },[configId]);
  useEffect(()=>{
    if(!job||!['queued','running'].includes(job.status))return;
    const timer=window.setInterval(()=>{api('/admin/model-configs/'+configId+'/quality-runs/'+job.id).then(r=>{setJob(r);if(!['queued','running'].includes(r.status))void load()}).catch(e=>setMessage(e.message))},2000);
    return()=>window.clearInterval(timer);
  },[job?.id,job?.status,configId]);
  async function review(approved:boolean){
    setBusy(true);
    try{
      await api(base+'/'+selected.quality_report_id+'/review','POST',{approved,comment,reviewed_case_ids:reviewed});
      setMessage(approved?'质量报告已批准，可激活模型配置':'已拒绝，请修正后重新评价');
      setSelected(null);await load();onChanged?.();
    }catch(error){setMessage((error as Error).message)}finally{setBusy(false)}
  }

  return <section><h3>质量评价与人工复核</h3>
    <p>当前判据 teaching-v4：覆盖9种目标/先修组合，核对具体素材、题量、快照、复习与先修门控。旧报告仅留作历史，不等同新版通过；该报告也不代替辅导专项验收。</p>
    <button disabled={busy||['queued','running'].includes(job?.status)} onClick={async()=>{if(!window.confirm('将调用已配置模型执行新版60场景评价，每例失败时最多再修复2次（最多180次评价请求，JSON格式修复还可能额外调用），会消耗API额度。完成后仍须逐例复核，不会自动激活。确认开始？'))return;setBusy(true);try{const r:any=await api('/admin/model-configs/'+configId+'/quality-runs','POST',{confirmed:true});setJob(r);localStorage.setItem('zhixing-quality-job:'+configId,r.id);setMessage('评价已开始，可保留页面查看进度')}catch(e){setMessage(qualityError(e))}finally{setBusy(false)}}}>运行新版60场景评价</button>
    {job&&<p role="status">评价进度 {job.completed_cases||0}/{job.total||60} · {job.status} · 硬判据通过{job.passed_count||0}项{job.error?' · '+job.error:''}</p>}
    {message&&<p role="status">{message}</p>}
    {!reports.length&&<p>尚无质量报告，JSON连通成功后仍需完成质量评价。</p>}
    {reports.map(report=><div className="listrow" key={report.id}>
      <p>{report.rubric_version||'旧版'} · {report.current_rubric?'当前判据':'历史判据：需新版重评'} · {report.operator} · 自动硬判据{report.passed_count}/{report.case_count} · {report.review_status}</p>
      <button disabled={busy} onClick={async()=>{
        setBusy(true);
        try{setSelected(await api(base+'/'+report.id));setReviewed([]);setComment('')}
        catch(error){setMessage((error as Error).message)}finally{setBusy(false)}
      }}>查看场景响应并复核</button>
    </div>)}
    {selected&&<details open><summary>60场景响应 · {selected.rubric_version||"旧版判据"}</summary>
      <div role="group" aria-label="批量复核选择">
        <p role="status">已选择 {reviewed.length}/{selected.results.length} 项</p>
        <button type="button" disabled={busy||selected.review_status!=='pending'||!selected.current_rubric||reviewed.length===selected.results.length} onClick={()=>setReviewed(selected.results.map((entry:any)=>entry.case.id))}>全选</button>
        <button type="button" disabled={busy||!reviewed.length} onClick={()=>setReviewed([])}>取消全选</button>
        <p>全选仅批量勾选复核项；填写复核依据并点击批准后才提交。</p>
      </div>
      {selected.results.map((entry:any)=><fieldset key={entry.case.id}>
        <legend>{entry.case.id} · {entry.case.topic} · 预算{entry.case.budget_minutes}分钟</legend>
        <pre style={{whiteSpace:"pre-wrap"}}>{JSON.stringify({先修依据:entry.case.prerequisite,资料:entry.case.sources,配套素材:entry.case.assets,目标策略:entry.case.target_action,先修范围:entry.case.prerequisite_basis,判据:entry.checks,模型输出:entry.response,逐次修复记录:entry.attempts},null,2)}</pre><p>修复次数 {entry.repair_count||0} · 预期状态 {entry.case.expected_status} · {entry.automated_pass?'硬判据通过':'硬判据未通过'}</p>
        <p>{typeof entry.response?.reason==='string'?entry.response.reason:(entry.error_code?entry.error_code+' · ':'')+(entry.error||'响应缺少有效原因说明')}</p>
        {Array.isArray(entry.response?.tasks)&&entry.response.tasks.map((task:any,index:number)=><p key={index}>{String(task?.skill_id??'无效知识点')} · {String(task?.minutes??'未知')}分钟</p>)}
        <label><input type="checkbox" disabled={selected.review_status!=='pending'||!selected.current_rubric} checked={reviewed.includes(entry.case.id)} onChange={event=>setReviewed(event.target.checked?[...reviewed,entry.case.id]:reviewed.filter(value=>value!==entry.case.id))}/>已核对本场景教学语义</label>
      </fieldset>)}
      <label>实际复核依据<textarea value={comment} onChange={event=>setComment(event.target.value)} required maxLength={3000}/></label>
      <button disabled={busy||!selected.current_rubric||!selected.hard_pass||selected.review_status!=='pending'||reviewed.length!==60||!comment.trim()} onClick={()=>review(true)}>批准质量报告</button>
      <button disabled={busy||selected.review_status!=='pending'||!comment.trim()} onClick={()=>review(false)}>拒绝质量报告</button>
    </details>}
  </section>;
}

