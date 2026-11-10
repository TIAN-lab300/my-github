import {useState} from 'react';
import {api} from './api';

export function PublishTask({task,onChanged}:{task:any;onChanged:(message:string)=>void}){
 const [preview,setPreview]=useState<any[]|null>(null);
 const [busy,setBusy]=useState(false);
 const [message,setMessage]=useState('');
 async function inspect(){
  setBusy(true);setMessage('');
  try{
   const classroom=await api<any>('/classes/'+task.class_id);
   setPreview(classroom.members.filter((m:any)=>m.status==='active'&&(!task.recipients.length||task.recipients.includes(m.id))));
  }catch(e){setMessage((e as Error).message)}finally{setBusy(false)}
 }
 async function publish(){
  setBusy(true);
  try{
   const result=await api<any>('/teacher/tasks/'+task.id+'/publish','POST');
   const notice=result.budget_conflicts?.length?'已发布，预算冲突学生 '+result.budget_conflicts.join('、')+'，请评估重规划':'发布成功';
   setMessage(notice);setPreview(null);onChanged(notice);
  }catch(e){setMessage((e as Error).message)}finally{setBusy(false)}
 }
 return <div><button disabled={busy} onClick={inspect}>预览接收人并发布</button>
  {preview&&<section><h3>发布前核对</h3><p>接收{preview.length}人，发布时冻结内容及成员快照</p>
   {preview.map(m=><p key={m.id}>{m.name} · {m.username}</p>)}
   <button disabled={busy||!preview.length} onClick={publish}>确认发布任务</button>
   <button disabled={busy} onClick={()=>setPreview(null)}>取消发布</button></section>}
  {message&&<p role="status">{message}</p>}
 </div>
}
