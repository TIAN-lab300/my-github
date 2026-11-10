import {useEffect,useState} from 'react';
import {api} from './api';
export function ProfileExplorer({classId}:{classId?:string}){
 const base=classId?'/teacher/classes/'+classId+'/profile':'/learners/me/profile';
 const [profile,setProfile]=useState<any>(null);
 const [history,setHistory]=useState<any[]>([]);
 const [events,setEvents]=useState<any[]>([]);
 const [error,setError]=useState('');
 const [busy,setBusy]=useState(false);
 const [historical,setHistorical]=useState(false);
 useEffect(()=>{let active=true;setProfile(null);setHistory([]);setHistorical(false);setError('');
  api<any>(base).then(p=>{if(active)setProfile(p)}).catch(e=>{if(active)setError(e.message)});
  return()=>{active=false};
 },[base]);
 async function load(kind:'current'|'history'|'events'){
  setBusy(true);setError('');
  try{
   if(kind==='current'){setProfile(await api(base+(classId?'':'/refresh'),classId?'GET':'POST'));setHistorical(false)}
   if(kind==='history')setHistory(await api<any[]>(base+'/history'));
   if(kind==='events')setEvents(await api<any[]>(base+'/refresh-events'));
  }catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 return <section className="card"><h2>{classId?'班级画像快照':'完整学习画像'}</h2>
  {error&&<p role="alert">{error}</p>}
  <button disabled={busy} onClick={()=>load('current')}>刷新当前画像</button>
  <button disabled={busy} onClick={()=>load('history')}>查看画像历史</button>
  {!classId&&<button disabled={busy} onClick={()=>load('events')}>查看刷新任务</button>}
  {profile&&<><p>版本{profile.version} · {historical?'历史快照':'当前读取'} · {profile.generated_at} · {profile.data_quality?.status}</p>
   {profile.data_quality?.status==='stale'&&<p role="alert">刷新失败，正在显示上一有效版本，请重试。</p>}
   {classId?<><p>统计窗口 全部本班授权记录 · 完成{profile.task_metrics.completed}/{profile.task_metrics.assigned} · 学习{profile.learning_time}分钟 · 风险{profile.risk_students}人</p>
    {Object.entries(profile.mastery_distribution||{}).map(([skill,value]:any)=><p key={skill}>{skill} · 已测{value.tested}人 · 掌握{value.mastered}人 · 薄弱{value.weak}人</p>)}
   </>:<>
    <p>统计窗口 {profile.query_window?.kind||'all_time'} · {profile.query_window?.from||'暂无起点'} 至 {profile.query_window?.through||'暂无记录'}</p><h3>学习上下文</h3>{profile.learning_context.goals.map((g:any)=><p key={g.id}>{g.title}</p>)}
    <h3>学习行为</h3><p>真实时长{profile.learning_behavior.actual_minutes}分钟 · 已交{profile.learning_behavior.completed}/{profile.learning_behavior.assigned}</p>
    <h3>知识掌握</h3>{Object.entries(profile.mastery_state).map(([skill,m]:any)=><p key={skill}>{skill} · {Math.round(m.probability*100)}% · 证据{m.evidence_count}</p>)}
    {!Object.keys(profile.mastery_state).length&&<p>暂无测验证据，当前掌握情况未知</p>}
    <h3>证据质量</h3><p>有效观察{profile.evidence_quality.valid_observations} · 待复核{profile.evidence_quality.pending_review}</p>
    <h3>风险依据</h3>{profile.risk_summary.map((r:any,i:number)=><p key={i}>{r.reason} · {r.observed_at} · 证据{r.evidence_ids?.join('、')}</p>)}
    {!profile.risk_summary.length&&<p>当前无已识别风险</p>}
    <h3>数据质量</h3><p>规则{profile.data_quality.rules_version} · 状态{profile.data_quality.status}</p>
   </>}
  </>}
  {!!history.length&&<details open><summary>画像历史（{history.length}版）</summary>{history.map(h=><button key={h.id} disabled={busy} onClick={()=>{setProfile({...JSON.parse(h.payload),version:h.version,generated_at:h.created_at,snapshot_id:h.id});setHistorical(true)}}>查看画像版本{h.version}</button>)}</details>}
  {events.map(e=><p key={e.id}>刷新水位{e.source_watermark} · {e.status} · {e.error||'无错误'}</p>)}
 </section>
}
