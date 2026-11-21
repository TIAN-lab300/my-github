import {useEffect,useState,ReactNode} from 'react';

export function DiagnosisWorkspace({goals,selectedGoal,onSelect,onStart,busy,onCreateGoal,children}:{goals:any[];selectedGoal:string;onSelect:(id:string)=>void;onStart:()=>void;busy:boolean;onCreateGoal:()=>void;children?:ReactNode}){
 const active=goals.filter(g=>g.status==='active'||g.status==='draft');
 const [message,setMessage]=useState('');
 useEffect(()=>{if(!selectedGoal&&active.length===1)onSelect(active[0].id)},[selectedGoal,active.length,active[0]?.id]);
 const selected=active.some(g=>g.id===selectedGoal);
 return <section className="card" aria-label="诊断与作答"><h2>诊断与作答</h2><p>先确认目标的知识范围，再在这里做题，交卷后查看评分。</p>
 {!active.length?<><p className="notice" role="status">请先在“目标设定”中保存并确认学习目标，再开始诊断。</p><button type="button" disabled={busy} onClick={onCreateGoal}>前往目标设定</button>{goals.some(g=>g.status==='archived')&&<p>已归档目标不能用于新诊断；历史数据仍然保留。</p>}</>:<>
 <label className="field">选择诊断目标<select aria-label="选择诊断目标" value={selectedGoal} onChange={e=>{onSelect(e.target.value);setMessage('')}}><option value="">请选择已确认的学习目标</option>{active.map(g=><option key={g.id} value={g.id}>{g.title}{g.requires_diagnosis?' · 待诊断':' · 已提交诊断'}</option>)}</select></label>
 <button className="primary goal-save-button" disabled={busy} onClick={()=>{if(!selected){setMessage('请先在上方选择一个活动目标，再开始诊断。');return;}setMessage('');onStart()}}>{busy?'正在处理…':'开始／继续本目标诊断'}</button>{message&&<p role="status">{message}</p>}{selected&&children}
 </>}
 </section>;
}
