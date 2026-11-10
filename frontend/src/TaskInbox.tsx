import {useRef,useState} from 'react';
import {api,parse} from './api';

export function TaskInbox({tasks,onChanged}:{tasks:any[];onChanged:()=>void}){
 const [status,setStatus]=useState('');
 const [message,setMessage]=useState('');
 const [busy,setBusy]=useState(false);
 const [source,setSource]=useState<{title:string;body:string}|null>(null);
 const lock=useRef(false);
 async function save(form:HTMLFormElement,task:any,draft:boolean){
  if(lock.current)return;
  lock.current=true;setBusy(true);setMessage('');
  const values=new FormData(form);
  const answers=Object.fromEntries(task.questions.map((q:any)=>[q.id,values.getAll(q.id).map(String).join(',')]));
  const payload={answers,text:String(values.get('text')||''),minutes:Number(values.get('minutes'))};
  try{
   await api('/tasks/'+task.id+(draft?'/draft':'/attempts'),draft?'PUT':'POST',payload);
   setMessage(draft?'暂存成功，可稍后继续':'提交成功，结果已保存');onChanged();
  }catch(e){setMessage((e as Error).message)}
  finally{lock.current=false;setBusy(false)}
 }
 return <><section className="card"><label>筛选任务状态<select value={status} onChange={e=>setStatus(e.target.value)}>
  <option value="">全部任务</option>{[['not_started','未开始'],['in_progress','进行中'],['completed','已完成'],['overdue','逾期'],['cancelled','已取消']].map(([v,n])=><option key={v} value={v}>{n}</option>)}</select></label>
  {message&&<p role="status">{message}</p>}</section>
  {source&&<section className="card"><h3>{source.title} · 任务资料</h3><article className="reading">{source.body}</article><button onClick={()=>setSource(null)}>关闭任务资料</button></section>}
  {tasks.filter(t=>!status||t.assignment_status===status).map(task=>{
   const attempt=task.attempt;
   const feedback=attempt?parse<any[]>(attempt.feedback):[];
   return <section className="card" key={task.id}><h2>{task.title}</h2><p>{task.description}</p>
    <p>{task.assignment_status} · 截止{new Date(task.due_at).toLocaleString()} · {task.minutes}分钟</p>
    {task.resource_id&&<button disabled={busy} onClick={async()=>{
      setBusy(true);
      try{
        const path=task.resource_version_id
          ?'/resources/'+task.resource_id+'/versions/'+task.resource_version_id+'/content'
          :'/resources/'+task.resource_id;
        const result=await api<{body:string}>(path);
        setSource({title:task.title,body:result.body||'该资料为附件，请到课程知识库查看'});
      }catch(e){setMessage((e as Error).message)}finally{setBusy(false)}
    }}>查看关联资料</button>}
    {attempt?<div><h3>{attempt.status==='pending_review'?'待教师复核':attempt.score==null?'提交已保存':'得分 '+Math.round(attempt.score*100)+'%'}</h3>
     <p>{attempt.late?'逾期补交':'按时提交'} · 评分规则 {attempt.scoring_version}</p>
     {feedback.map((f:any,i:number)=><p key={i}>{f.prompt} {f.correct===true?'✓':f.correct===false?'✕':''} {f.answer!=null?'正确答案 '+f.answer:''} {f.explanation||f.comment||f.message} {f.skill&&'知识点 '+f.skill} {f.recommendation} {f.review_version&&'评分版本 '+f.review_version}</p>)}
    </div>:task.status==='published'&&task.assignment_status!=='cancelled'?<form onSubmit={e=>{e.preventDefault();if(confirm('确认提交？提交后作答将冻结。'))save(e.currentTarget,task,false)}}>
     {task.mode==='quiz'?task.questions.map((q:any)=><fieldset key={q.id}><legend>{q.prompt}</legend>{['single','boolean','multi'].includes(q.kind||'single')&&q.options?.length?q.options.map((option:string,index:number)=><label className="choice" key={index}>
      <input name={q.id} type={q.kind==='multi'?'checkbox':'radio'} value={index} defaultChecked={String(task.draft?.answers?.[q.id]||'').split(',').includes(String(index))}/>{option}
     </label>):<textarea name={q.id} maxLength={2000} defaultValue={task.draft?.answers?.[q.id]||''}/>}</fieldset>)
     :task.mode!=='checkin'&&<label>{task.mode==='code'?'Python程序':'提交内容'}<textarea name="text" maxLength={20000} defaultValue={task.draft?.text||''}/></label>}
     <label>本次实际分钟<input type="number" name="minutes" min={1} max={1440} required defaultValue={task.draft?.minutes||task.minutes}/></label>
     <button disabled={busy} type="button" onClick={e=>save(e.currentTarget.form!,task,true)}>暂存作答</button>
     <button disabled={busy} type="submit">提交并查看反馈</button>
    </form>:<p>当前任务已停止接收提交</p>}
   </section>
  })}
  {!tasks.filter(t=>!status||t.assignment_status===status).length&&<p>暂无符合条件的任务</p>}
 </>;
}
