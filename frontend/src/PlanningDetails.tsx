import {useState} from 'react';
import {api} from './api';
export function PlanningDetails({path,onChanged,onPractice}:{path:any;onChanged:()=>void;onPractice:(value:any)=>void}){
 const [message,setMessage]=useState('');
 const [busy,setBusy]=useState(false);
 const validation=path.validation;
 return <section><h3>规划依据与规则</h3><p>{validation.cloud_called?'云端四智能体生成':'本地规则规划'}</p>{validation.cloud_outputs?.diagnosis?.summary&&<p>{validation.cloud_outputs.diagnosis.summary}</p>}{validation.cloud_outputs?.replan?.reason&&<p>{validation.cloud_outputs.replan.reason}</p>}
  <p>图谱版本 {validation.graph_version||'历史版本'} · 范围 {({initial:'首次',local:'局部',global:'全局'} as any)[validation.mode]||'历史规划'}</p>
  {validation.triggers?.map((s:string)=><p key={s}>{s}</p>)}
  {path.replan_warnings?.map((s:string)=><p className="notice" key={s}>保留原路径的风险提醒 {s}</p>)}
  {validation.rules?.map((rule:any)=><p key={rule.rule_id}>{rule.rule_id} · {rule.passed?'通过':'未通过'} · {rule.reason}</p>)}
  {validation.diff&&<div><h3>重规划差异</h3><p>新增 {validation.diff.added.join('、')||'无'} · 移除 {validation.diff.removed.join('、')||'无'} · 保留 {validation.diff.kept.join('、')||'无'}</p>
   <p>补强 {validation.diff.reinforced.join('、')||'无'}</p>
   <p>原排期 {validation.diff.before_schedule.map((s:any)=>s.date+' '+s.minutes+'分钟').join('；')||'无'}</p>
   <p>新排期 {validation.diff.after_schedule.map((s:any)=>s.date+' '+s.minutes+'分钟').join('；')||'无需新增时间'}</p>
   <p>保留完成历史 {validation.preserved?.length||0}项</p>
  </div>}
  <h3>执行顺序与材料</h3>
  {validation.execution?.map((item:any,index:number)=><p key={item.id}>{index+1}. {item.name} · {item.minutes}分钟 · {item.dates?.map((d:any)=>d.date+' '+d.minutes+'分钟').join('；')} · 材料{item.citations?.length||0}份 · {item.assessment} · {item.instructions||''}</p>)}
  {message&&<p role="status">{message}</p>}
  {path.remediations?.map((item:any)=><section className="card" key={item.id}><h3>独立补强 · {item.name}</h3>
   <p>来源任务 {item.source_item_id} · {item.minutes}分钟 · {item.locked?'先修未达标':'可学习'}</p>
   {item.checkin&&<p>已记录{item.checkin.minutes}分钟</p>}
   {path.status==='active'&&!item.locked&&<><button disabled={busy||!!item.checkin} onClick={async()=>{setBusy(true);try{await api('/check-ins','POST',{path_id:path.id,item_id:item.id,minutes:item.minutes,proportion:1,difficulty:'补强学习',note:''});setMessage('补强学习已记录，掌握度需经测验验证');onChanged()}catch(e){setMessage((e as Error).message)}finally{setBusy(false)}}}>记录补强学习</button>
    <button disabled={busy} onClick={async()=>{setBusy(true);try{const assessment=await api<any>('/paths/'+path.id+'/items/'+item.id+'/assessment');onPractice({...assessment,path_id:path.id,item_id:item.id})}catch(e){setMessage((e as Error).message)}finally{setBusy(false)}}}>补强知识测验</button></>}
  </section>)}
 </section>
}
