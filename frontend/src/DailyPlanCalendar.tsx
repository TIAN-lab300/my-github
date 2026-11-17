import {useState} from 'react';
export function DailyPlanCalendar({path}:{path:any}){
 const [showAll,setShowAll]=useState(true);
 const entries=path.calendar||path.validation.schedule||[],execution=path.validation.execution||path.tasks;
 const minutes=entries.reduce((sum:number,d:any)=>sum+d.minutes,0),learningDays=entries.filter((d:any)=>d.minutes>0).length;
 const allMastered=path.validation.learner_evidence?.skills?.length&&path.validation.learner_evidence.skills.every((s:any)=>s.status==='mastered');
 return <section aria-label="每日学习日历"><h3>每日学习安排</h3><p>共 {minutes} 分钟 · {learningDays} 个安排日 · 截止日期 {path.validation.goal_snapshot?.due_date||'见目标设置'} · {path.validation.planning_options?.pace==='balanced'?'均衡安排至截止日':'按可用预算尽早完成'}</p>
 {!minutes&&<p className="notice" role="status">{allMastered?'本目标知识点已达到掌握阈值，因此本次没有新学任务。若要继续巩固，请勾选“已达标知识点仍安排复习”后重新生成路径。':'本次没有新增待执行任务，请查看掌握证据、保留历史和目标范围。'} 空排期与是否配置大模型无关。</p>}
 <p>表中是本目标计划时长。休息日和未安排日显示0分钟；预算是上限，不会为了占满截止日前每天时间而虚构任务。候选接受后才预约时间。</p>
 <label className="choice"><input type="checkbox" checked={showAll} onChange={e=>setShowAll(e.target.checked)}/>显示截止日前全部日期（含未安排日）</label>
 <div className="scroll"><table><thead><tr><th>日期</th><th>本目标学习时长</th><th>学习内容与材料</th></tr></thead><tbody>{entries.filter((d:any)=>showAll||d.minutes).map((d:any)=><tr key={d.date}><td>{d.date} {new Date(d.date+'T12:00:00').toLocaleDateString('zh-CN',{weekday:'short'})}</td><td>{d.minutes} 分钟</td><td>{d.minutes?execution.flatMap((t:any)=>(t.dates||[]).filter((date:any)=>date.date===d.date).map((date:any)=><p key={t.id}>{t.name} · {date.minutes}分钟 · {t.kind==='review'?'已达标复习':'学习／练习'} · 材料{t.citations?.length||0}份</p>)):d.available_day===false?'休息日（未设为可学习日）':'无本目标计划任务'}</td></tr>)}</tbody></table></div>
 </section>
}
