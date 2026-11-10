import {useState} from 'react';
import {api} from './api';

export function TaskSupplement({task,onChanged}:{task:any,onChanged:()=>void}) {
  const [members,setMembers]=useState<any[]|null>(null);
  const [selected,setSelected]=useState<string[]>([]);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState('');
  async function open(){
    setBusy(true);setMessage('');
    try {const c=await api('/classes/'+task.class_id);setMembers(c.members.filter((m:any)=>m.status==='active'));}
    catch(e){setMessage((e as Error).message);}finally{setBusy(false);}
  }
  async function submit(){
    setBusy(true);setMessage('');
    try {await api(`/teacher/tasks/${task.id}/supplement`,'POST',{student_ids:selected,expected_version:task.version});setMembers(null);setSelected([]);setMessage('关联补发草稿已建立，请核对截止时间后发布。');onChanged();}
    catch(e){setMessage((e as Error).message);}finally{setBusy(false);}
  }
  return <div><button disabled={busy} onClick={open}>创建指定学生补发草稿</button>{members&&<fieldset><legend>选择补发接收人</legend><p>原任务及历史作答保留，新任务需核对后发布。</p>{members.map(m=><label className="choice" key={m.id}><input type="checkbox" checked={selected.includes(m.id)} onChange={e=>setSelected(e.target.checked?[...selected,m.id]:selected.filter(id=>id!==m.id))}/>{m.name} · {m.username}</label>)}<button disabled={busy||!selected.length} onClick={submit}>建立补发草稿</button><button disabled={busy} onClick={()=>setMembers(null)}>取消</button></fieldset>}{message&&<p role="status">{message}</p>}</div>;
}
