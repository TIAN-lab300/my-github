import {CourseLearning} from './CourseLearning';
import {useEffect,useState} from 'react';
import {api} from './api';
export function CurriculumCatalog({onOpen,role}:{role:string;onOpen:(id:string)=>void}){
 const [courses,setCourses]=useState<any[]>([]),[selected,setSelected]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function load(){setBusy(true);setError('');try{const r=await api('/curriculum/catalog');setCourses(r.courses);setSelected(old=>r.courses.some((c:any)=>c.id===old)?old:r.courses[0]?.id||'')}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 useEffect(()=>{void load()},[]);
 const current=courses.find(c=>c.id===selected);
 return <section className="card"><h2>专业课程与中文资料导读</h2><p>按课程查看中文知识点目录和阅读说明。外部原文保留原语言；候选知识点待核对教学大纲，当前未导入正式题库。</p>{error&&<p className="error" role="alert">{error}</p>}<button disabled={busy} onClick={()=>void load()}>刷新课程资料</button>{!busy&&!error&&!courses.length&&<p>尚未导入课程资料。</p>}{!!courses.length&&<><label className="field">选择专业课程<select aria-label="选择专业课程" value={selected} onChange={e=>setSelected(e.target.value)}>{courses.map(c=><option key={c.id} value={c.id}>{c.year?`大${c.year}`:'选修'} · {c.name}</option>)}</select></label>{current&&<><p>{current.skills.length}个候选知识／能力点 · {current.sources.length}份中文导读 · 题库待补充</p>{current.assessment_mode==='project_rubric'&&<p>本课程以项目成果和教师评价为主，目录不能替代正式评分量规。</p>}<details><summary>查看知识点目录</summary><ul>{current.skills.map((s:any)=><li key={s.id}>{s.name}</li>)}</ul></details><CourseLearning key={current.id} courseId={current.id} role={role} onOpen={onOpen}/><h3>对应公开资料</h3>{current.sources.map((s:any)=><div key={s.id} className="listrow"><b>{s.title}</b><p>{s.description}</p><button onClick={()=>onOpen(s.resource_id)}>阅读中文导读</button></div>)}</>}</>}</section>;
}
