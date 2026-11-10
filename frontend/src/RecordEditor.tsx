import {CodeCasesEditor} from './CodeCasesEditor';
import {api} from './api';
import {QuestionEditor} from './QuestionEditor';
import {useState,useEffect,FormEvent} from 'react';
type Props={kind:string;record:any;members:any[];classes:any[];onClose:()=>void;onSave:(path:string,body:any)=>Promise<void>};
export function RecordEditor({kind,record:r,members,classes,onClose,onSave}:Props){
 const [catalog,setCatalog]=useState<{id:string;name:string}[]>([]);
 useEffect(()=>{if(kind==='goal')api<any>('/curriculum/skills').then(result=>setCatalog(result.skills)).catch(error=>setError(error.message))},[kind]);
 const [questions,setQuestions]=useState<any[]>(r.questions||[]);
 const [error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function submit(e:FormEvent<HTMLFormElement>){
  e.preventDefault();const f=new FormData(e.currentTarget);const body:any={...Object.fromEntries(f),version:r.version};
  if(kind==='goal'){body.weekly_minutes=Number(body.weekly_minutes);body.target_skill_ids=f.getAll('skills').map(String);delete body.skills;body.class_id=body.class_id||null;}
  if(kind==='task'){if(r.mode==='code')body.code_cases=JSON.parse(String(f.get('code_cases')||'[]'));body.questions=questions;body.minutes=Number(body.minutes);body.due_at=new Date(body.due_at).toISOString();body.recipients=f.getAll('recipients');}
  if(kind==='resource')body.cloud_allowed=f.has('cloud_allowed');
  const base:any={class:'/classes/',resource:'/resources/',goal:'/goals/',task:'/teacher/tasks/'};
  setBusy(true);setError('');try{await onSave(base[kind]+r.id,body)}catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 return <section className="card" role="region" aria-label="编辑信息"><div className="row"><h2>编辑信息 · 版本 {r.version}</h2><button disabled={busy} onClick={onClose}>取消编辑</button></div>{error&&<p className="error" role="alert">{error}</p>}<form onSubmit={submit}><fieldset disabled={busy} style={{border:0,padding:0}}><label className="field">{kind==='class'?'班级名称':'标题'}<input name={kind==='class'?'name':'title'} defaultValue={r.name||r.title} required maxLength={kind==='class'?100:200}/></label>{kind!=='goal'&&<label className="field">说明<textarea name="description" defaultValue={r.description} maxLength={3000}/></label>}
 {kind==='resource'&&<><label className="field">标签<input name="tags" defaultValue={r.tags}/></label><label className="field">来源与使用权限<input name="source_license" defaultValue={r.source_license} required/></label><label><input type="checkbox" name="cloud_allowed" defaultChecked={!!r.cloud_allowed}/>允许必要正文发送云端</label></>}
 {kind==='goal'&&<><fieldset><legend>确认目标知识范围</legend>{catalog.map(({id,name})=><label key={id}><input type="checkbox" name="skills" value={id} defaultChecked={r.target_skill_ids.includes(id)}/>{name}</label>)}</fieldset><label>学习偏好<select name="preference" defaultValue={r.preference||'unspecified'}><option value="unspecified">未指定</option><option value="text">文本阅读</option><option value="video">视频</option></select></label><label className="field">每周目标分钟<input name="weekly_minutes" type="number" min={1} max={10080} defaultValue={r.weekly_minutes} required/></label><label className="field">截止日期<input name="due_date" type="date" defaultValue={r.due_date} required/></label><label className="field">关联班级<select name="class_id" defaultValue={r.class_id||''}><option value="">私有目标</option>{classes.filter(c=>c.status==='active').map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label><p className="footnote">修改将建立新目标版本，旧路径及证据保留。取消班级关联后教师不再看到该目标。</p></>}
 {kind==='task'&&<><label className="field">预计分钟<input name="minutes" type="number" min={1} max={1440} defaultValue={r.minutes} required/></label><label className="field">截止时间<input name="due_at" type="datetime-local" defaultValue={new Date(new Date(r.due_at).getTime()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,16)} required/></label>{r.mode==='code'&&<CodeCasesEditor initialCases={r.code_cases}/>} {r.mode==='quiz'&&<QuestionEditor questions={questions} onChange={setQuestions}/>}<p>指定接收人，不选表示全班</p>{members.map(m=><label className="choice" key={m.id}><input type="checkbox" name="recipients" value={m.id} defaultChecked={r.recipients.includes(m.id)}/>{m.name}</label>)}</>}
 <button className="primary" disabled={busy}>{busy?'保存中…':'保存修改'}</button></fieldset></form></section>
}
