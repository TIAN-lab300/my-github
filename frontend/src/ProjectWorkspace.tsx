import {useEffect,useState} from 'react';
import {api,ApiError} from './api';
const errorText=(e:unknown)=>e instanceof ApiError&&e.status===404&&e.message==='Not Found'?'当前后端尚未加载工程实施接口。请停止旧服务，重新运行启动云端搜索版.cmd，再刷新页面。':(e as Error).message;

const names:Record<string,string>={pending_acceptance:'候选，尚未生效',active:'活动计划',not_started:'待实施',submitted:'待验收',accepted:'已验收',needs_changes:'需修改',pending:'待验收',superseded:'历史版本'};
const lines=(value:FormDataEntryValue|null)=>String(value||'').split('\n').map(x=>x.trim()).filter(Boolean);

export function ProjectWorkspace({goalId,reviewer=false}:{goalId:string;reviewer?:boolean}){
  const [data,setData]=useState<any>(null),[resources,setResources]=useState<any[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
  const base='/engineering-goals/'+goalId;
  async function load(){setData(await api(base+'/workspace'))}
  useEffect(()=>{void load().catch(e=>setError(errorText(e)));if(!reviewer)api<any[]>('/resources?scope=private').then(setResources).catch(e=>setError(errorText(e)))},[goalId,reviewer]);
  async function work(fn:()=>Promise<any>,success='已保存'){if(busy)return;setBusy(true);setError('');setMessage('');try{await fn();await load();setMessage(success)}catch(e){setError(errorText(e))}finally{setBusy(false)}}
  if(!data)return <section className="card" aria-label="工程实施与验收"><h3>工程实施与验收</h3>{error?<p role="alert">{error}</p>:<p>正在读取工程…</p>}</section>;
  const archived=data.goal.status==='archived';const active=data.plans.find((p:any)=>p.status==='active');
  const activeKeys=new Set(active?.payload.milestones.map((m:any)=>m.key)||[]);
  const milestones=active?active.payload.milestones.map((m:any)=>data.milestones.find((x:any)=>x.milestone_key===m.key)).filter(Boolean):[];
  return <section className="card" aria-label="工程实施与验收"><h3>工程实施与验收</h3>
    <p>{data.completed?'工程阶段已全部验收通过':'课程测验验证知识掌握，工程完成由真实成果及人工量规验收决定。'}</p>
    {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
    {!reviewer&&<details open={!data.version}><summary>交付目标与运行环境</summary><form key={data.version} onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);void work(()=>api(base+'/workspace','PUT',{version:data.version,spec:{deliverable:f.get('deliverable'),language:f.get('language'),platform:f.get('platform'),toolchain:f.get('toolchain'),acceptance_criteria:lines(f.get('criteria')),excluded_features:lines(f.get('excluded')),auto_replan:f.has('auto')}}))}}>
      <fieldset disabled={busy||archived}><label>最终交付<textarea name="deliverable" defaultValue={data.spec.deliverable} required maxLength={2000}/></label>
      <label>实现语言<input name="language" defaultValue={data.spec.language} placeholder="例如：C++" required maxLength={100}/></label>
      <label>运行平台<input name="platform" defaultValue={data.spec.platform} placeholder="系统、图形环境及版本" required maxLength={200}/></label>
      <label>构建与工具链<input name="toolchain" defaultValue={data.spec.toolchain} placeholder="编译器、构建和运行方式" required maxLength={500}/></label>
      <label>最终验收条件（每行一项）<textarea name="criteria" defaultValue={data.spec.acceptance_criteria.join('\n')} required/></label>
      <label>本次不包含的功能（每行一项）<textarea name="excluded" defaultValue={data.spec.excluded_features.join('\n')}/></label>
      <button type="submit">保存工程设定</button></fieldset></form></details>}
    {reviewer&&<p>交付：{data.spec.deliverable} · 环境：{data.spec.language} / {data.spec.platform} / {data.spec.toolchain}</p>}
    {data.material_pack==='opengl'&&<details><summary>OpenGL原创起步材料与调试练习</summary><p>提供指南、着色器片段和调试清单，不是完整可运行的渲染器；需在实际环境配置窗口、上下文及构建。</p>{['guide.md','triangle.vert','triangle.frag','checklist.md'].map(name=><p key={name}><a href={'/api/v1/project-material-pack/'+name}>{name} · 下载</a></p>)}</details>}
    {!reviewer&&active&&!archived&&<details><summary>上传工程附件（个人资料）</summary><form onSubmit={e=>{e.preventDefault();const form=new FormData(e.currentTarget);form.set('description','工程成果附件');form.set('tags','工程成果');form.set('source_license','本人提交用于工程验收');form.set('cloud_allowed','true');void work(async()=>{const result=await api<any[]>('/resources','POST',form);setResources(await api('/resources?scope=private'));const failures=result.filter(r=>r.error);if(failures.length)throw new Error(failures.map(r=>r.filename+'：'+r.error).join('；'))},'附件已上传，请在阶段提交时选择') }}><input type="file" name="files" multiple required accept=".c,.cpp,.h,.hpp,.py,.glsl,.vert,.frag,.log,.txt,.md,.pdf,.png,.jpg,.jpeg,.webp,.mp4,.webm"/><button disabled={busy}>上传工程附件</button></form></details>}
    {milestones.map((m:any)=><section className="card" key={m.id}><h4>{m.payload.title} · {names[m.status]||m.status}</h4><p>累计实际时间 {m.actual_minutes}分钟</p>{m.locked_reason&&<p>{m.locked_reason}</p>}
      {!reviewer&&!archived&&activeKeys.has(m.milestone_key)&&!['accepted','submitted'].includes(m.status)&&<form key={m.id+':'+m.status} onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);void work(()=>api(base+'/milestones/'+m.id+'/submissions','POST',{notes:f.get('notes'),code:f.get('code'),build_log:f.get('build_log'),repository_url:f.get('repository'),commit_ref:f.get('commit_ref'),resource_ids:f.getAll('resources'),actual_minutes:Number(f.get('minutes'))}),'成果已提交，等待教师或管理员验收；未自动增加掌握度')}}>
        <fieldset disabled={busy||!!m.locked_reason}><label>实现、测试与已知限制<textarea name="notes" required maxLength={6000}/></label><label>源码片段<textarea name="code" maxLength={50000}/></label><label>真实构建和运行日志<textarea name="build_log" maxLength={20000}/></label><label>Git源码仓库链接<input name="repository" type="url" maxLength={2048}/></label><label>Git提交哈希（使用仓库时必填）<input name="commit_ref" maxLength={64}/></label>
        <label>累计实际分钟<input name="minutes" type="number" min={m.actual_minutes} max={10080} defaultValue={m.actual_minutes} required/></label><fieldset><legend>选择本人上传的成果附件</legend>{resources.map(r=><label key={r.id}><input type="checkbox" name="resources" value={r.id}/>{r.title}</label>)}</fieldset><button>提交本阶段成果</button></fieldset></form>}
      {m.deliveries.map((d:any)=><details key={d.id} open={reviewer&&d.status==='pending'}><summary>成果修订{d.revision} · {names[d.status]||d.status}</summary><p>{d.evidence.notes}</p>{d.evidence.repository_url&&<p><a href={d.evidence.repository_url} target="_blank" rel="noopener noreferrer">查看源码仓库</a> · 提交 {d.evidence.commit_ref}</p>}<details><summary>源码与构建日志（学生提交，需核验）</summary><pre style={{whiteSpace:'pre-wrap'}}>{d.evidence.code}</pre><pre style={{whiteSpace:'pre-wrap'}}>{d.evidence.build_log}</pre></details>{d.evidence.artifacts.map((a:any)=><p key={a.resource_id}><a href={'/api/v1/project-deliveries/'+d.id+'/artifacts/'+a.resource_id+'/download'}>{a.filename} · 冻结版本附件</a> · SHA256 {a.sha256}</p>)}
        {d.reviews.map((r:any)=><p key={r.id}>{r.accepted?'验收通过':'退回修改'}：{r.comment}</p>)}
        {reviewer&&d.status==='pending'&&!archived&&<ProjectReviewForm delivery={d} onReview={async body=>{await api('/project-deliveries/'+d.id+'/review','POST',body);await load()}}/>}
      </details>)}
    </section>)}
    <button disabled={busy} onClick={()=>void work(load,'工程状态已刷新')}>刷新工程状态</button>
  </section>;
}

function ProjectReviewForm({delivery,onReview}:{delivery:any;onReview:(body:any)=>Promise<void>}){
  const [checks,setChecks]=useState<number[]>([]),[comment,setComment]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  async function submit(accepted:boolean){setBusy(true);setError('');try{await onReview({accepted,checks,comment})}catch(e){setError(errorText(e))}finally{setBusy(false)}}
  return <section aria-label="工程量规验收"><p>核验源码、真实构建和运行证据；学生日志或模型自评不等于通过。验收不直接修改课程BKT掌握度。</p>{delivery.snapshot.criteria.map((c:string,i:number)=><label key={i}><input type="checkbox" disabled={busy} checked={checks.includes(i)} onChange={e=>setChecks(e.target.checked?[...checks,i]:checks.filter(x=>x!==i))}/>{c}</label>)}<button disabled={busy} onClick={()=>setChecks(delivery.snapshot.criteria.map((_:any,i:number)=>i))}>全选验收项</button><label>验收依据与修改意见<textarea value={comment} onChange={e=>setComment(e.target.value)} maxLength={3000} required/></label>{error&&<p role="alert">{error}</p>}<button disabled={busy||!comment.trim()||checks.length!==delivery.snapshot.criteria.length} onClick={()=>void submit(true)}>验收通过</button><button disabled={busy||!comment.trim()} onClick={()=>void submit(false)}>退回修改</button></section>;
}

export function ProjectReviewInbox(){
  const [items,setItems]=useState<any[]>([]),[selected,setSelected]=useState(''),[error,setError]=useState('');
  async function load(){try{setItems(await api('/project-deliveries/review-inbox'));setError('')}catch(e){setError(errorText(e))}}
  useEffect(()=>{void load()},[]);
  return <section className="card"><h2>工程成果验收</h2><button onClick={()=>void load()}>刷新待验收成果</button>{error&&<p role="alert">{error}</p>}{!items.length&&<p>暂无可审核的工程成果。</p>}{items.map(d=><p key={d.id}>{d.student_name} · {d.title} · {d.milestone_key} <button onClick={()=>setSelected(d.goal_id)}>查看成果与量规</button></p>)}{selected&&<ProjectWorkspace key={selected} goalId={selected} reviewer/>}</section>;
}
