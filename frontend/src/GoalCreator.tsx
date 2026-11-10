import {useState,useEffect} from 'react';
import {api,ApiError} from './api';
export function GoalCreator({classes,onCreated}:{classes:any[];onCreated:()=>void}){
 const [catalog,setCatalog]=useState<{id:string;name:string;diagnostic_available?:boolean}[]>([]);
 const [catalogError,setCatalogError]=useState(''),[loadingCatalog,setLoadingCatalog]=useState(false);
 async function loadCatalog(){setLoadingCatalog(true);setCatalogError('');try{const result=await api<any>('/curriculum/skills');if(!Array.isArray(result.skills)||!result.skills.length)throw new Error('当前没有可用的知识范围，请联系管理员维护知识图谱和题库');setCatalog(result.skills);}catch(e){setCatalogError(e instanceof ApiError&&e.status===404?'当前后端缺少题库目录接口，请更新并重启服务':e instanceof TypeError?'无法连接后端，请确认8000服务正在运行':(e as Error).message);}finally{setLoadingCatalog(false)}}
 useEffect(()=>{void loadCatalog()},[]);
 const [title,setTitle]=useState(''),[skills,setSkills]=useState<string[]>([]),[date,setDate]=useState('');
 const [minutes,setMinutes]=useState(300),[preference,setPreference]=useState('unspecified');
 const [busy,setBusy]=useState(false),[message,setMessage]=useState('');
 const [confirmed,setConfirmed]=useState(false);
 async function interpret(){
  setBusy(true);setMessage('');setConfirmed(false);
  try{
   const value=await api<any>('/goals/interpret','POST',{text:title});
   setSkills(value.target_skill_ids);if(value.due_date)setDate(value.due_date);
   if(value.weekly_minutes)setMinutes(value.weekly_minutes);setPreference(value.preference);
   setMessage(value.needs_clarification.length?value.needs_clarification.join('；'):'已提取目标，请核对技能、截止、时间与偏好后确认');
  }catch(e){setMessage((e as Error).message)}finally{setBusy(false)}
 }
 return <section className="card"><h2>从一个明确的目标开始</h2>{message&&<p role="status">{message}</p>}
  <form onSubmit={async e=>{
   e.preventDefault();const values=new FormData(e.currentTarget);setBusy(true);
   try{
    await api('/goals','POST',{title,target_skill_ids:skills,due_date:date,weekly_minutes:minutes,class_id:values.get('class_id')||null,preference});
    setMessage('目标已保存');onCreated();
   }catch(e){setMessage((e as Error).message)}finally{setBusy(false)}
  }}>
   <label>学习目标<textarea aria-label="学习目标" value={title} maxLength={200} required onChange={e=>{setTitle(e.target.value);setConfirmed(false)}} placeholder="例如：每周3小时，在2026-12-01前学习Python，偏好阅读文本"/></label>
   <button type="button" disabled={busy||!title.trim()} onClick={interpret}>解析目标描述</button>
   <fieldset><legend>确认目标知识范围</legend>{loadingCatalog&&<p role="status">正在读取知识范围与题库覆盖…</p>}{catalogError&&<p role="alert" className="error">{catalogError}</p>}<button type="button" disabled={loadingCatalog||busy} onClick={()=>void loadCatalog()}>重新获取题库</button>{catalog.map(({id,name,diagnostic_available})=><label key={id}><input type="checkbox" disabled={diagnostic_available===false} checked={skills.includes(id)} onChange={e=>{setSkills(e.target.checked?[...skills,id]:skills.filter(s=>s!==id));setConfirmed(false)}}/>{name}{diagnostic_available===false?'（诊断题库待管理员补充）':''}</label>)}</fieldset>
   <label>每周目标分钟<input type="number" min={1} max={10080} required value={minutes} onChange={e=>{setMinutes(Number(e.target.value));setConfirmed(false)}}/></label>
   <label>截止日期<input type="date" value={date} required onChange={e=>{setDate(e.target.value);setConfirmed(false)}}/></label>
   <label>学习偏好<select aria-label="学习偏好" value={preference} onChange={e=>{setPreference(e.target.value);setConfirmed(false)}}><option value="unspecified">未指定</option><option value="text">文本阅读</option><option value="video">视频</option></select></label>
   <label>关联班级（默认私有）<select name="class_id"><option value="">私有目标</option>{classes.filter(c=>c.status==='active').map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
   <label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} required/>已核对目标范围、时间与偏好</label>
   <button disabled={busy||!confirmed||loadingCatalog||!!catalogError||!skills.length}>保存目标</button>
  </form>
 </section>
}
