import {useEffect,useState} from 'react';
import {api} from './api';
export function CourseStructure({courseId}:{courseId:string}){
 const [data,setData]=useState<any>(null),[error,setError]=useState('');
 useEffect(()=>{let active=true;setData(null);setError('');api('/learning/courses/'+courseId+'/structure').then(d=>{if(active)setData(d)}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[courseId]);
 return <section><h3>课程、章节与先修关系</h3>{error&&<p role="alert">{error}</p>}{data&&<>
 <p>{data.version?'项目教学设定 · '+data.version.id+'；官方培养方案尚未核准。':'尚未导入课程关系设定。'}</p>
 <p>课程基础表示应具备的相关能力，可通过等效学习补齐；不要求完成整门课才允许学习。章节次序用于展示，具体先修以知识点依赖为准。</p>
 <ul>{data.course_prerequisites.map((p:any)=><li key={p.before_id}>{p.kind==='required'?'建议先具备':'建议补充'}：{p.name}。{p.reason}</li>)}</ul>
 {!!data.external_requirements.length&&<p>目录外基础：{data.external_requirements.map((r:any)=>r.name).join('；')}</p>}
 {data.chapters.map((ch:any)=><details key={ch.id}><summary>第{ch.position}章 · {ch.title}（{ch.skills.length}个知识点）</summary><ul>{ch.skills.map((s:any)=>{const deps=data.skill_prerequisites.filter((p:any)=>p.after_id===s.id);return <li key={s.id}>{s.name}<span> · 先修：{deps.length?deps.map((p:any)=>p.before_name).join('、'):'无本课程内显式先修'}</span></li>})}</ul></details>)}
 {!!data.chapter_prerequisites.length&&<details><summary>章节之间的学习建议</summary><ul>{data.chapter_prerequisites.map((p:any)=><li key={p.before_id+p.after_id}>{p.before_name} → {p.after_name}。{p.reason}</li>)}</ul></details>}
 </>}</section>
}
