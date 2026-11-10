import {useState} from 'react';
import {api} from './api';

export function GoalInspector({goal}:{goal:any}){
 const [check,setCheck]=useState<any>(null);
 const [history,setHistory]=useState<any[]>([]);
 const [message,setMessage]=useState('');
 const [busy,setBusy]=useState(false);
 async function inspect(kind:'feasibility'|'history'){
  setBusy(true);setMessage('');
  try{
   const result=await api<any>('/goals/'+goal.id+'/'+kind);
   if(kind==='history')setHistory(result);else setCheck(result);
  }catch(e){setMessage((e as Error).message)}finally{setBusy(false)}
 }
 return <section><p>目标版本 {goal.version} · {goal.class_id?'已显式关联班级':'本人私有目标'}</p>
  {goal.requires_replan&&<p role="status">目标或预算已变化，请重新评估活动路径</p>}
  <button disabled={busy} onClick={()=>inspect('feasibility')}>检查时间可行性</button>
  <button disabled={busy} onClick={()=>inspect('history')}>查看目标版本历史</button>
  {message&&<p role="alert">{message}</p>}
  {check&&<div role="status"><p>{check.status==='feasible'?'当前预算可排期':check.status==='missing_structure'?'目标结构待补齐':check.status==='evidence_gap'?'授权学习资料存在缺口':'当前预算存在冲突'}</p>
   <p>需求分钟 {check.required_minutes??'待确定'}</p>{check.reasons.map((r:string)=><p key={r}>{r}</p>)}
   {check.schedule?.map((s:any)=><p key={s.date}>{s.date} · {s.minutes}分钟</p>)}
  </div>}
  {!!history.length&&<details open><summary>目标版本历史（{history.length}版）</summary>
   {history.map(h=>{const p=JSON.parse(h.payload);return <p key={h.version}>版本{h.version} · {p.title} · {p.weekly_minutes}分钟/周 · 截止{p.due_date} · {p.status}</p>})}
  </details>}
 </section>
}
