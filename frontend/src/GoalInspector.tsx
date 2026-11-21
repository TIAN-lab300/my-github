import {useState} from 'react';
import {api} from './api';

export function GoalInspector({goal}:{goal:any}){
 const [history,setHistory]=useState<any[]>([]);
 const [message,setMessage]=useState('');
 const [busy,setBusy]=useState(false);
 async function inspect(){
  setBusy(true);setMessage('');
  try{
   const result=await api<any>('/goals/'+goal.id+'/history');
   setHistory(result);
  }catch(e){setMessage((e as Error).message)}finally{setBusy(false)}
 }
 return <section><p>目标版本 {goal.version} · {goal.class_id?'已显式关联班级':'本人私有目标'}</p>
  {goal.requires_diagnosis&&<p role="status">当前目标版本尚无已提交诊断，请先点击“开始/查看诊断”完成检测。</p>}
  <button disabled={busy} onClick={()=>inspect()}>查看目标版本历史</button>
  {message&&<p role="alert">{message}</p>}
  {!!history.length&&<details open><summary>目标版本历史（{history.length}版）</summary>
   {history.map(h=>{const p=JSON.parse(h.payload);return <p key={h.version}>版本{h.version} · {p.title} · {p.weekly_minutes}分钟/周 · 截止{p.due_date} · {p.status}</p>})}
  </details>}
 </section>
}
