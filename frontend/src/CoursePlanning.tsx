import {useEffect,useState} from 'react';
import {api} from './api';
export function CoursePlanning({courseId,role,paper}:{courseId:string;role:string;paper:any}){
 const [data,setData]=useState<any>(null),[error,setError]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false);
 async function load(){setData(await api('/learning/courses/'+courseId+'/planning-readiness'))}
 useEffect(()=>{let live=true;setData(null);setError('');setMessage('');api('/learning/courses/'+courseId+'/planning-readiness').then(d=>{if(live)setData(d)}).catch(e=>{if(live)setError(e.message)});return()=>{live=false}},[courseId,paper?.status]);
 async function act(fn:()=>Promise<void>){if(busy)return;setBusy(true);setError('');try{await fn()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <section className="card"><h3>课程诊断与学习路径衔接</h3>{error&&<p role="alert" className="error">{error}</p>}{message&&<p role="status">{message}</p>}{data&&<>
 <p>用已提交的课程初测创建目标，直接关联课程知识点。未测先修会保留为未知。</p>
 <button disabled={busy} onClick={()=>void act(load)}>刷新课程规划检查</button>
 {role==='admin'&&<button disabled={busy} onClick={()=>void act(async()=>{
  const result=await api<any>('/admin/curriculum/question-teaching-review','POST',{});
  if(result.error_code||result.unavailable)throw new Error('教学复查暂停（'+(result.error_code||result.unavailable)+'），已保存结果。');
  setMessage(result.passed?'已记录一道历史题目的教学复查通过。':result.failed?'已记录一道历史题目的教学问题。':result.changed?'题目版本已变化，请再运行一次。':'当前模型配置下，已没有待复查的可用历史题目。');
 })}>复查下一道历史题目（全库）</button>}
 {data.coverage&&<p>课程覆盖 · 初测 {data.coverage.covered.diagnostic}/{data.coverage.denominator} · 练习 {data.coverage.covered.practice}/{data.coverage.denominator} · 重测 {data.coverage.covered.retest}/{data.coverage.denominator} · 校级正文 {data.coverage.resources_covered}/{data.coverage.denominator}</p>}
 {data.coverage&&<details><summary>查看资料实际可用性</summary>
 {data.coverage.skills.map((item:any)=><p key={item.skill_id}>{data.skills.find((s:any)=>s.id===item.skill_id)?.name||item.skill_id} · 已关联 {item.material_availability.catalog} · 可读 {item.material_availability.readable} · 可学习 {item.material_availability.learnable} · 可发模型 {item.material_availability.cloud_sendable}</p>)}
 </details>}
 <details><summary>查看各知识点接入情况</summary>{data.skills.map((s:any)=><p key={s.id}>{s.name} → {s.mapping?s.mapping.graph_skill_id:'尚未映射'} · {s.gaps.join('；')||'题库、正文与映射齐备（生成时仍会检查正文支持与预算）'}</p>)}</details>
 {role==='admin'&&<form onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);if(!confirm('确认两侧知识点代表相同能力？保存后不能覆盖此图谱版本的映射。'))return;void act(async()=>{await api('/learning/courses/'+courseId+'/planning-mappings','POST',{skill_id:f.get('skill'),graph_skill_id:f.get('graph'),graph_version:data.graph_version,confirmed:true});setMessage('映射审核已保存');await load()})}}><label className="field">课程知识点<select name="skill">{data.skills.map((s:any)=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label><label className="field">对应图谱知识点<select name="graph">{data.graph.map((s:any)=><option key={s.id} value={s.id}>{s.name}（{s.id}）· 先修：{s.prerequisites.join('、')||'无'}</option>)}</select></label><p>新课程需要的图谱节点可在“知识图谱”维护并审核激活；请按教学内容确认等价关系。</p><button disabled={busy||data.project_mode}>审核保存映射</button></form>}
 {role==='student'&&!data.project_mode&&<>{paper?.status==='submitted'&&paper.phase==='diagnostic'?<form onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);void act(async()=>{const r=await api('/learning/courses/'+courseId+'/goals','POST',{assessment_id:paper.id,title:f.get('title'),due_date:f.get('due'),weekly_minutes:Number(f.get('weekly'))});setMessage('课程初测已连接目标 '+r.id+'。可在目标与诊断查看。');await load()})}}><h4>用这次课程初测创建学习目标</h4><label className="field">目标名称<input name="title" required maxLength={200} defaultValue="课程知识补强"/></label><label className="field">截止日期<input name="due" type="date" required/></label><label className="field">本目标每周分钟<input name="weekly" type="number" min={1} max={10080} defaultValue={180} required/></label><button disabled={busy}>连接初测并创建目标</button></form>:<p>请先选择“初测”并交卷，或从历史中打开已交初测试卷，再创建目标。</p>}<p><a href="#goal">前往目标与诊断</a></p>{data.goals.map((g:any)=><p key={g.id}>已关联：{g.title} · {g.status}</p>)}</>}
 {data.project_mode&&<p>项目课程使用教师量规评价，此入口不以选择题替代项目验收。</p>}
 </>}</section>
}
