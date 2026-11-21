import {CourseLearning} from './CourseLearning';
import {CourseLinks} from './CourseLinks';
import {useEffect,useState} from 'react';
import {api} from './api';
export function CurriculumCatalog({onOpen,role}:{role:string;onOpen:(id:string)=>void}){
 const [courses,setCourses]=useState<any[]>([]),[selected,setSelected]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[query,setQuery]=useState(''),[year,setYear]=useState(''),[type,setType]=useState('');
 async function load(){setBusy(true);setError('');try{const r=await api('/curriculum/catalog');setCourses(r.courses);setSelected(old=>{const requested=new URLSearchParams(location.hash.split('?')[1]||'').get('course');return r.courses.some((c:any)=>c.id===requested)?requested!:r.courses.some((c:any)=>c.id===old)?old:''})}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 useEffect(()=>{void load()},[]);
 const [guide,setGuide]=useState<{id:string;body:string}|null>(null);
 async function openGuide(id:string){
  setError('');
  try {
   const resource=await api('/resources/'+encodeURIComponent(id));
   setGuide({id,body:resource.body?.trim()||'此条目暂无中文导读正文，可打开原站查看。'});
  } catch(e){setError((e as Error).message)}
 }
 const current=courses.find(c=>c.id===selected);
 const references=(current?.sources||[]).filter((source:any)=>{
  if(source.resource_id==='public-source-S02')return current?.id==='public-C01';
  if(source.resource_id==='public-source-S10')return current?.id==='public-C08'&&source.url==='https://15445.courses.cs.cmu.edu/spring2026/assignments.html';
  return true;
 });
 return <section className="card"><h2>专业课程知识库</h2>{role==='student'&&<p><a href="#search">上传个人资料与管理收藏</a></p>}<p>按课程查看知识点、正式学习内容和检测情况。候选目录仍需核对教学大纲；正式题目数量以各知识点已审核题库为准。</p>{error&&<p className="error" role="alert">{error}</p>}<button disabled={busy} onClick={()=>void load()}>刷新课程资料</button>{!busy&&!error&&!courses.length&&<p>尚未导入课程资料。</p>}{!!courses.length&&<><label>搜索课程<input value={query} onChange={e=>setQuery(e.target.value)}/></label><label>年级<select value={year} onChange={e=>setYear(e.target.value)}><option value="">全部</option>{[1,2,3,4].map(y=><option key={y} value={y}>大{y}</option>)}</select></label><label>课程类型<select value={type} onChange={e=>setType(e.target.value)}><option value="">全部</option><option value="required">非选修</option><option value="elective">选修</option></select></label>{!current&&courses.filter(c=>c.name.toLowerCase().includes(query.toLowerCase())&&(!year||String(c.year)===year)&&(!type||Boolean(c.elective)===(type==='elective'))).map(c=><div className="listrow" key={c.id}><button onClick={()=>{setSelected(c.id);const params=new URLSearchParams(location.hash.split('?')[1]||'');params.set('course',c.id);history.replaceState(null,'',location.hash.split('?')[0]+'?'+params.toString())}}>{c.name}</button><p>{c.chapter_count??0}章 · {c.skills.length}个知识点 · {c.readable_material_count??0}份本地文档（{c.parsed_material_count??c.readable_material_count??0}份正文就绪） · {c.external_material_count??0}个外部参考资料</p></div>)}{current&&<button onClick={()=>{setSelected('');const params=new URLSearchParams(location.hash.split('?')[1]||'');params.delete('course');history.replaceState(null,'',location.hash.split('?')[0]+(params.size?'?'+params:''))}}>返回课程列表</button>}{current&&<><p>{current.skills.length}个候选知识／能力点 · 正式题库及规划衔接见下方检查</p>{current.assessment_mode==='project_rubric'&&<p>本课程以项目成果和教师评价为主，目录不能替代正式评分量规。</p>}<CourseLearning key={'learning-'+current.id} courseId={current.id} role={role} onOpen={onOpen}/>{(references.length>0||!!current.external_courses?.length)&&<details key={current.id}><summary>外部参考</summary><CourseLinks key={'links-'+current.id} links={current.external_courses||[]}/>{references.map((s:any)=><div key={s.id} className="listrow"><b>{s.resource_id==='public-source-S02'?'外部练习 · CS50公开练习':s.resource_id==='public-source-S10'?'进阶参考 · CMU数据库课程作业':s.title}</b><p>{s.description}</p><div className="actions"><button onClick={()=>guide?.id===s.resource_id?setGuide(null):void openGuide(s.resource_id)}>{guide?.id===s.resource_id?'关闭中文导读':'阅读中文导读'}</button>{s.url&&<a href={s.url} target="_blank" rel="noopener noreferrer">打开资料原站 ↗</a>}</div>{guide?.id===s.resource_id&&<article className="reading" style={{whiteSpace:'pre-wrap'}}>{guide?.body}</article>}</div>)}</details>}</>}</>}</section>;
}
