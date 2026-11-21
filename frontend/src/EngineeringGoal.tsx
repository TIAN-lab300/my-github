import {useEffect,useState} from 'react';
import {api} from './api';

export function EngineeringGoalDetails({goalId}:{goalId:string}){
 const [personal,setPersonal]=useState<any[]>([]);
 const [data,setData]=useState<any>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
 async function load(){try{setData(await api('/engineering-goals/'+goalId+'/readiness'));setError('')}catch(e){setError((e as Error).message)}}
 useEffect(()=>{void load();const timer=setInterval(()=>void load(),15000);return()=>clearInterval(timer)},[goalId]);
 return <section aria-label="目标课程与就绪检查"><h3>学习范围与课程推荐</h3>{error&&<p role="alert">{error}</p>}{data&&<><p>{data.analysis.summary}</p>{data.scope_stale&&<p role="alert">先修关系版本已更新，请重新解析并确认工程范围；历史方案仍可查看。</p>}
 {data.courses.map((c:any)=><p key={c.id}><a href={'#resources?course='+encodeURIComponent(c.id)}>{c.name} · 查看课程、章节与资料</a><small> · {c.recommendation_reason}</small>{c.links.map((l:any)=><span key={l.url}> · <a href={l.url} target="_blank" rel="noopener noreferrer">{l.title} ↗</a></span>)}</p>)}
 <details><summary>补充并关联我的个人学习正文</summary><p><a href="#search">先到个人资料页上传文件</a>，识别并确认正文后再关联。资料仍仅本人可见，关联不会自动允许云端发送。</p><button type="button" disabled={busy} onClick={()=>api<any[]>('/resources?scope=private').then(setPersonal).catch(e=>setError(e.message))}>读取我的个人资料列表</button><form onSubmit={async e=>{e.preventDefault();const f=new FormData(e.currentTarget);setBusy(true);try{await api('/engineering-goals/'+goalId+'/materials','POST',{skill_id:f.get('skill_id'),resource_id:f.get('resource_id'),confirmed:f.get('confirmed')==='on'});setMessage('个人正文已关联');await load()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}}><label>关联目标知识点<select name="skill_id">{data.skills.map((s:any)=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label><label>我的正文资料<select name="resource_id" required><option value="">请选择</option>{personal.map((r:any)=><option key={r.id} value={r.id}>{r.title}</option>)}</select></label><label><input name="confirmed" type="checkbox" required/>确认正文讲解了此知识点，且有权用于个人学习</label><button disabled={busy||!personal.length}>关联我的正文</button></form></details>
 <details><summary>{data.ready?'已有关联正文和三用途题库':'查看缺题、缺正文及先修检查'}</summary>{data.skills.map((s:any)=><p key={s.id}>{s.name} · 初测{s.question_counts.diagnostic}/练习{s.question_counts.practice}/重测{s.question_counts.retest} · {s.gaps.join('；')||'基础资料已关联'}</p>)}</details>
 {!!data.analysis.uncovered_capabilities.length&&<p>工程专项仍需补齐及验收：{data.analysis.uncovered_capabilities.join('、')}</p>}
 {message&&<p role="status">{message}</p>}
 </>}</section>;
}

export function EngineeringDraftReview(){
 const [data,setData]=useState<any>(null),[offset,setOffset]=useState(0),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function load(){try{setData(await api('/admin/engineering-question-drafts?offset='+offset));setError('')}catch(e){setError((e as Error).message)}}
 useEffect(()=>{void load()},[offset]);
 async function review(id:string,publish:boolean){if(!confirm(publish?'确认已核对课程知识点、完整题干、全部选项、唯一答案、解析及使用许可？发布后可用于学生诊断。':'停用此草稿并保留历史？'))return;setBusy(true);try{await api('/learning/questions/'+id+(publish?'/publish':'/disable'),'POST',publish?{confirmed:true}:undefined);await load()}catch(e){await load();setError((e as Error).message)}finally{setBusy(false)}}
 return <section className="card" aria-label="工程目标AI题目审核"><h2>工程目标AI题目审核</h2><p>模型补充题先留草稿。请逐项核对，不能把结构校验或模型自评当作教师内容审核。</p>{error&&<p role="alert">{error}</p>}<button disabled={busy} onClick={()=>void load()}>刷新工程题目草稿</button>{data&&<><p>待审核{data.total}题</p>{data.items.map((q:any)=><article className="listrow" key={q.id}><h3>{q.prompt}</h3><p>{q.course_name} · {q.skill_name} · {q.phase}</p><ol>{q.options.map((o:string,i:number)=><li key={i}>{o}</li>)}</ol><p>正确选项：{q.answer+1} · {q.options[q.answer]}</p><p>解析：{q.explanation}</p><p>来源：{q.source}</p><button disabled={busy} onClick={()=>void review(q.id,true)}>核对后发布此题</button><button disabled={busy} onClick={()=>void review(q.id,false)}>停用此草稿</button></article>)}<button disabled={busy||offset===0} onClick={()=>setOffset(Math.max(0,offset-50))}>上一页</button><button disabled={busy||offset+50>=data.total} onClick={()=>setOffset(offset+50)}>下一页</button></>}</section>;
}
