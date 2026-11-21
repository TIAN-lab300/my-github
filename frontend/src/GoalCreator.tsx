import {useEffect,useRef,useState} from 'react';
import {api,ApiError} from './api';
export function GoalCreator({classes,onCreated}:{classes:any[];onCreated:(goalId:string)=>void}){
 const [title,setTitle]=useState(''),[date,setDate]=useState(''),[minutes,setMinutes]=useState(300),[preference,setPreference]=useState('unspecified');
 const [proposal,setProposal]=useState<any>(null),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
 const lock=useRef(false);
 const [draftId,setDraftId]=useState(''),[drafts,setDrafts]=useState<any[]>([]);
 async function loadDrafts(){setDrafts(await api('/engineering-goals/drafts'))}
 useEffect(()=>{void loadDrafts().catch(()=>{})},[]);

 const labels:Record<string,string>={course:'课程目标',knowledge:'知识点目标',project:'工程目标',unclear:'需要补充说明'};
 async function interpret(){
  if(lock.current)return;lock.current=true;setBusy(true);setMessage('正在调用模型识别目标类型和知识范围…');setProposal(null);
  try{
   const value=await api('/goals/interpret','POST',{text:title,cloud_consent:true});setProposal(value);
   if(value.due_date)setDate(value.due_date);if(value.weekly_minutes)setMinutes(value.weekly_minutes);
   setPreference(value.preference||'unspecified');setMessage(value.can_save?'模型解析完成，填写时间后即可保存目标。':'请补充下面的问题或调整目标后重新解析。');
  }catch(e){setMessage(e instanceof ApiError&&e.status===404?'当前后端未加载模型解析接口，请重启云端服务。':(e as Error).message)}finally{lock.current=false;setBusy(false)}
 }
 const issues=[...(!title.trim()?['填写学习目标']:[]),...(!proposal?.can_save?['完成大模型解析并解决范围缺口']:[]),...(!date?['填写截止日期']:[]),...(!Number.isInteger(minutes)||minutes<1||minutes>10080?['每周分钟须为1至10080的整数']:[])];
 return <section className="card" aria-label="目标设定"><h2>目标设定</h2><p>可以先保存工程草稿，再由模型匹配基础知识。未覆盖能力保持未知，不阻止已有课程基础诊断。</p><button type="button" disabled={busy||!title.trim()} onClick={async()=>{setBusy(true);try{const d=await api('/engineering-goals/drafts','POST',{draft_id:draftId||undefined,description:title,due_date:date,weekly_minutes:minutes});setDraftId(d.id);await loadDrafts();setMessage('工程草稿已保存，下一步调用模型匹配基础知识。')}catch(e){setMessage((e as Error).message)}finally{setBusy(false)}}}>先保存工程草稿</button>{drafts.length>0&&<details><summary>恢复已保存工程草稿</summary>{drafts.map(d=><button type="button" key={d.id} onClick={()=>{setTitle(d.description);setDraftId(d.id);setDate(d.settings?.due_date||'');setMinutes(d.settings?.weekly_minutes||300);setProposal(d.proposal?{...d.proposal,proposal_id:d.id}:null);setMessage('草稿已恢复，可继续解析或生成补充草稿。')}}>{d.description}</button>)}</details>}<p>描述你想学什么或做出什么，模型自动判断课程、知识点或工程目标，并匹配现有知识范围。</p>
 {message&&<p role="status">{message}</p>}
 <form noValidate onSubmit={async e=>{
  e.preventDefault();if(lock.current)return;if(issues.length){setMessage('保存前请完成：'+issues.join('；'));return;}
  const form=new FormData(e.currentTarget);lock.current=true;setBusy(true);
  try{const saved=await api('/goals/from-interpretation','POST',{proposal_id:proposal.proposal_id,due_date:date,weekly_minutes:minutes,class_id:form.get('class_id')||null,preference});setMessage('目标已保存，正在准备诊断');onCreated(saved.id)}catch(e){setMessage((e as Error).message)}finally{lock.current=false;setBusy(false)}
 }}>
 <label className="field">学习目标<textarea aria-label="学习目标" disabled={busy} value={title} maxLength={2000} required onChange={e=>{setTitle(e.target.value);setProposal(null);setMessage('')}} placeholder="例如：两周学完数据结构；掌握Python递归；用OpenGL实现一个简单渲染器"/></label>
 <p>解析会将目标描述和公开课程目录发送给已激活模型，不发送个人资料正文。</p>
 <button type="button" disabled={busy||!title.trim()} onClick={()=>void interpret()}>{busy?'正在处理…':'大模型解析目标'}</button>
 {proposal&&<section aria-label="目标解析结果"><button type="button" disabled={busy} onClick={async()=>{setBusy(true);try{const r=await api('/goals/interpretations/'+proposal.proposal_id+'/supplement','POST',{cloud_consent:true});setProposal({...proposal,supplement:r});setMessage(r.message)}catch(e){setMessage((e as Error).message)}finally{setBusy(false)}}}>让模型补充缺失知识与资料草稿</button>{proposal.supplement?.units?.map((u:any,i:number)=><details key={i}><summary>{u.course}／{u.chapter}／{u.knowledge} · 待审核 · {u.question_count}题</summary><p style={{whiteSpace:'pre-wrap'}}>{u.body}</p></details>)}<h3>{labels[proposal.goal_type]||'解析结果'}</h3><p>{proposal.model_called?'已调用 '+proposal.model:'未调用模型'}</p><p>{proposal.summary}</p><p>自动匹配范围：{proposal.skills.map((s:any)=>s.name).join('、')||'尚未匹配'}</p>{proposal.scope_warnings?.map((s:string,i:number)=><p key={'scope'+i}>范围检查：{s}</p>)}{proposal.clarifications.map((s:string,i:number)=><p key={'clarify'+i}>请补充：{s}</p>)}{proposal.uncovered_capabilities.map((s:string,i:number)=><p key={'gap'+i}>未知／未诊断／待补齐：{s}</p>)}</section>}
 <label className="field">每周目标分钟<input aria-label="每周目标分钟" type="number" disabled={busy} min={1} max={10080} required value={minutes} onChange={e=>setMinutes(Number(e.target.value))}/></label>
 <label className="field">截止日期<input aria-label="目标截止日期" type="date" disabled={busy} value={date} required onChange={e=>setDate(e.target.value)}/></label>
 <label className="field">学习偏好<select aria-label="学习偏好" disabled={busy} value={preference} onChange={e=>setPreference(e.target.value)}><option value="unspecified">未指定</option><option value="text">文本阅读</option><option value="video">视频</option></select></label>
 <label className="field">关联班级（默认私有）<select name="class_id" disabled={busy}><option value="">私有目标</option>{classes.filter(c=>c.status==='active').map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
 <p role="status">{issues.length?'保存前请完成：'+issues.join('；'):'可以保存基础范围并开始诊断；未覆盖工程能力仍为未知。'}</p>
 <button className="primary goal-save-button" disabled={busy}>{busy?'正在处理…':'保存目标'}</button>
 </form></section>
}
