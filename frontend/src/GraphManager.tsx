import {useEffect,useState} from 'react';
import {api} from './api';
const initial=[{id:'functions',name:'函数基础',minutes:30},{id:'recursion',name:'递归',minutes:45},{id:'stack',name:'调用栈',minutes:45}];
export function GraphManager(){
 const [resources,setResources]=useState<any[]>([]);
 const [advanced,setAdvanced]=useState('');
 const [nodes,setNodes]=useState(initial);
 const [edges,setEdges]=useState<string[][]>([['functions','recursion'],['recursion','stack']]);
 const [versions,setVersions]=useState<any[]>([]);
 const [message,setMessage]=useState('');
 const [busy,setBusy]=useState(false);
 async function load(){setVersions(await api('/admin/graphs'))}
 useEffect(()=>{load().catch(e=>setMessage(e.message));api<any[]>('/resources').then(setResources).catch(e=>setMessage(e.message))},[]);
 return <section className="card"><h2>版本化知识图谱</h2>
  <p>节点时长、先修边与题目映射将随路径版本保存。正式启用前会检查主题题库映射。</p>
  {message&&<p role="status">{message}</p>}
  <form onSubmit={async e=>{e.preventDefault();setBusy(true);try{await api('/admin/graphs','POST',{nodes,edges});setMessage('图谱版本已登记，核对后可启用');await load()}catch(e){setMessage((e as Error).message)}finally{setBusy(false)}}}>
   {nodes.map((node,index)=><fieldset key={node.id}><legend>{node.name}</legend>
    <label>预计分钟<input type="number" min={1} required value={node.minutes} onChange={e=>setNodes(nodes.map((n,i)=>i===index?{...n,minutes:Number(e.target.value)}:n))}/></label>
    <p>必须先学习</p>{nodes.filter(n=>n.id!==node.id).map(before=><label key={before.id}><input type="checkbox" checked={edges.some(e=>e[0]===before.id&&e[1]===node.id)} onChange={e=>setEdges(e.target.checked?[...edges,[before.id,node.id]]:edges.filter(edge=>!(edge[0]===before.id&&edge[1]===node.id)))}/>{before.name}</label>)}
   </fieldset>)}
   <button disabled={busy}>保存图谱版本</button>
  </form>
  <details><summary>根据授权资料生成新主题草稿</summary>
   <form onSubmit={async event=>{event.preventDefault();const form=new FormData(event.currentTarget);setBusy(true);try{const result:any=await api('/admin/graphs/generate','POST',{goal:form.get('goal'),resource_ids:form.getAll('resource_ids')});setMessage('图谱与题库草稿已生成，请逐题核对后启用 '+result.id);await load()}catch(error){setMessage((error as Error).message)}finally{setBusy(false)}}}>
    <label>主题目标<input name="goal" required maxLength={200}/></label>
    <fieldset><legend>选择已授权云端处理的来源</legend>{resources.filter(item=>item.cloud_allowed&&item.parse_status==='ready').map(item=><label key={item.id}><input type="checkbox" name="resource_ids" value={item.id}/>{item.title}</label>)}</fieldset>
    <button disabled={busy}>生成待审核草稿</button>
   </form>
  </details>
  <details open={!!advanced}><summary>登记新主题与独立题库</summary><p>新主题需填写nodes和edges。每个节点提供diagnostic_questions、retest_questions、practice_questions三套不同题目，题目含id、skill、prompt、options、answer和explanation。登记后请核对，再启用。</p>
   <form onSubmit={async event=>{event.preventDefault();setBusy(true);try{await api('/admin/graphs','POST',JSON.parse(advanced));setMessage('新主题草稿已登记，请审核后启用');await load()}catch(error){setMessage((error as Error).message)}finally{setBusy(false)}}}>
    <label>图谱与题库JSON<textarea value={advanced} onChange={event=>setAdvanced(event.target.value)} required rows={16}/></label><button disabled={busy}>登记主题草稿</button>
   </form>
  </details>
  {versions.map(v=><section className="card" key={v.id}><p>图谱版本 {v.id.slice(0,8)} · {new Date(v.created_at).toLocaleString()} · {v.active?'已启用':'已登记'}</p>
   <button disabled={busy} onClick={()=>setAdvanced(JSON.stringify({nodes:JSON.parse(v.nodes),edges:JSON.parse(v.edges)},null,2))}>查看图谱与题库</button>
   <button disabled={busy||!!v.active} onClick={async()=>{if(!confirm('启用此版本将使旧候选需要重新评估，确认？'))return;setBusy(true);try{await api('/admin/graphs/'+v.id+'/activate','POST');setMessage('图谱已启用，新规划将使用该版本');await load()}catch(e){setMessage((e as Error).message)}finally{setBusy(false)}}}>启用图谱版本</button>
  </section>)}
 </section>
}
