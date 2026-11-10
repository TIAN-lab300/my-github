import {useEffect,useState} from 'react';
import {api} from './api';

export function ModelQuality({configId}:{configId:string}){
  const [reports,setReports]=useState<any[]>([]);
  const [selected,setSelected]=useState<any>(null);
  const [reviewed,setReviewed]=useState<string[]>([]);
  const [comment,setComment]=useState('');
  const [message,setMessage]=useState('');
  const [busy,setBusy]=useState(false);
  const base='/admin/model-configs/'+configId+'/quality-reports';
  async function load(){setReports(await api<any[]>(base))}
  useEffect(()=>{load().catch(error=>setMessage(error.message))},[configId]);

  async function review(approved:boolean){
    setBusy(true);
    try{
      await api(base+'/'+selected.quality_report_id+'/review','POST',{approved,comment,reviewed_case_ids:reviewed});
      setMessage(approved?'质量报告已批准，可激活模型配置':'已拒绝，请修正后重新评价');
      setSelected(null);await load();
    }catch(error){setMessage((error as Error).message)}finally{setBusy(false)}
  }

  return <section><h3>质量评价与人工复核</h3>
    <p>请先执行60场景评价命令，再在这里逐例核对教学语义。</p>
    {message&&<p role="status">{message}</p>}
    {!reports.length&&<p>尚无质量报告，JSON连通成功后仍需完成质量评价。</p>}
    {reports.map(report=><div className="listrow" key={report.id}>
      <p>{report.operator} · 自动硬判据{report.passed_count}/{report.case_count} · {report.review_status}</p>
      <button disabled={busy} onClick={async()=>{
        setBusy(true);
        try{setSelected(await api(base+'/'+report.id));setReviewed([]);setComment('')}
        catch(error){setMessage((error as Error).message)}finally{setBusy(false)}
      }}>查看场景响应并复核</button>
    </div>)}
    {selected&&<details open><summary>60场景响应</summary>
      {selected.results.map((entry:any)=><fieldset key={entry.case.id}>
        <legend>{entry.case.id} · {entry.case.topic} · 预算{entry.case.budget_minutes}分钟</legend>
        <p>预期状态 {entry.case.expected_status} · {entry.automated_pass?'硬判据通过':'硬判据未通过'}</p>
        <p>{typeof entry.response?.reason==='string'?entry.response.reason:entry.error||'响应缺少有效原因说明'}</p>
        {Array.isArray(entry.response?.tasks)&&entry.response.tasks.map((task:any,index:number)=><p key={index}>{String(task?.skill_id??'无效知识点')} · {String(task?.minutes??'未知')}分钟</p>)}
        <label><input type="checkbox" disabled={selected.review_status!=='pending'} checked={reviewed.includes(entry.case.id)} onChange={event=>setReviewed(event.target.checked?[...reviewed,entry.case.id]:reviewed.filter(value=>value!==entry.case.id))}/>已核对本场景教学语义</label>
      </fieldset>)}
      <label>实际复核依据<textarea value={comment} onChange={event=>setComment(event.target.value)} required maxLength={3000}/></label>
      <button disabled={busy||selected.review_status!=='pending'||reviewed.length!==60||!comment.trim()} onClick={()=>review(true)}>批准质量报告</button>
      <button disabled={busy||selected.review_status!=='pending'||!comment.trim()} onClick={()=>review(false)}>拒绝质量报告</button>
    </details>}
  </section>;
}
