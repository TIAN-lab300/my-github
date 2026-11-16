import {useEffect,useState,ReactNode} from 'react';
import {api} from './api';

export function DiagnosisWorkspace({goals,selectedGoal,onSelect,onStart,busy,onContinueDraft,draftVersion,children}:{goals:any[];selectedGoal:string;onSelect:(id:string)=>void;onStart:()=>void;busy:boolean;onContinueDraft:(id:string)=>void;draftVersion:number;children?:ReactNode}){
 // A confirmed goal remains draft until its first path is accepted. Engineering
 // text drafts live in proposals, so both goal states are eligible for diagnosis.
 const active=goals.filter(g=>g.status==='active'||g.status==='draft');
 const [drafts,setDrafts]=useState<any[]>([]),[loading,setLoading]=useState(true),[error,setError]=useState(''),[message,setMessage]=useState('');
 async function load(){setLoading(true);try{setDrafts(await api('/engineering-goals/drafts'));setError('')}catch(e){setError((e as Error).message)}finally{setLoading(false)}}
 useEffect(()=>{void load()},[draftVersion]);
 useEffect(()=>{if(!selectedGoal&&active.length===1)onSelect(active[0].id)},[selectedGoal,active.length,active[0]?.id]);
 const selected=active.some(g=>g.id===selectedGoal);
 return <section className="card" aria-label="诊断与作答"><h2>诊断与作答</h2><p>先确认目标的知识范围，再在这里做题；交卷后生成学习路径。</p>
 {error&&<p role="alert">读取工程草稿失败：{error}<button onClick={()=>void load()}>重新读取草稿</button></p>}
 {!active.length?<><p className="notice" role="status">当前没有已确认的学习目标，因此暂时没有诊断题。保存工程草稿不等于确认了知识范围。</p>{loading&&<p>正在读取已保存草稿…</p>}{drafts.map(d=><div className="listrow" key={d.id}><strong>{d.description}</strong><p>{d.analysed?'已解析，尚未核对知识范围并确认目标。':'目前是未解析草稿，需要补充具体成果并选择知识范围。'}</p><button className="primary" disabled={busy} onClick={()=>onContinueDraft(d.id)}>继续完善草稿：{d.description}</button></div>)}{!loading&&!drafts.length&&<p>还没有工程草稿。请先填写目标，再选择模型分析、手动知识点或本地OpenGL模板。</p>}<button disabled={busy} onClick={()=>onContinueDraft('')}>前往填写工程目标</button>{goals.some(g=>g.status==='archived')&&<p>已归档目标不能用于新诊断；历史数据仍然保留。</p>}</>:<>
 <label className="field">选择诊断目标<select aria-label="选择诊断目标" value={selectedGoal} onChange={e=>{onSelect(e.target.value);setMessage('')}}><option value="">请选择已确认的学习目标</option>{active.map(g=><option key={g.id} value={g.id}>{g.title}{g.requires_diagnosis?' · 待诊断':' · 已提交诊断'}</option>)}</select></label>
 <button className="primary goal-save-button" disabled={busy} onClick={()=>{if(!selected){setMessage('请先在上方选择一个活动目标，再开始诊断。');return;}setMessage('');onStart()}}>{busy?'正在处理…':'开始／继续本目标诊断'}</button>{message&&<p role="status">{message}</p>}{selected&&children}
 </>}
 </section>;
}
