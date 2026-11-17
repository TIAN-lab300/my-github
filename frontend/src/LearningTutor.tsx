import {useEffect,useRef,useState} from 'react';
import {api} from './api';
type Target={skill_id:string;item_id:string;prompt:string}|null;
export function LearningTutor({courseId,skills,target,onClear,assessmentPending}:{courseId:string;skills:any[];target:Target;onClear:()=>void;assessmentPending:boolean}){
 const [skillId,setSkillId]=useState(skills[0]?.id||''),[question,setQuestion]=useState(''),[mode,setMode]=useState('local'),[level,setLevel]=useState(1),[consent,setConsent]=useState(false);
 const [result,setResult]=useState<any>(null),[history,setHistory]=useState<any[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const panel=useRef<HTMLElement>(null);
 useEffect(()=>{setResult(null);setError('');if(target){setSkillId(target.skill_id);setQuestion('请分步讲解这道已提交的题目，帮助我理解思路：'+target.prompt.slice(0,1200));panel.current?.scrollIntoView({behavior:'smooth',block:'start'})}},[target]);
 async function loadHistory(){setHistory(await api('/learning/courses/'+courseId+'/tutor/history'))}
 function show(r:any){return <div className="listrow"><p>{r.model_called?'云端学习辅导 · '+r.model:'本地阅读引导 · 未调用大模型'}</p><article className="reading">{r.explanation}</article><ol>{r.hints?.map((h:string,i:number)=><li key={i}>{h}</li>)}</ol>{r.citations?.map((ref:any,i:number)=>{const source=r.sources?.find((s:any)=>s.id===ref.source_id);return <blockquote key={i}><p>{ref.quote}</p>{source&&<p>来源：{source.title} · {source.location} · 正文版本 {source.version_id} · <a href={'/api/v1/resources/'+source.resource_id+'/versions/'+source.version_id+'/download'}>下载引用版本</a></p>}</blockquote>})}</div>}
 return <section ref={panel} className="card" aria-label="学习辅导智能体"><h3>学习辅导智能体</h3><p>以已关联的正式正文为依据，提供逐步提示与讲解。辅导不会修改成绩、掌握度或完成记录；相关测验未交卷时暂不提供辅导。</p>{assessmentPending&&<p role="status">请先独立完成当前测验并交卷，再使用辅导。</p>}
 {target&&<p>题目辅导：{target.prompt}<button type="button" disabled={busy} onClick={()=>{onClear();setQuestion('');setResult(null)}}>返回知识点提问</button></p>}
 <form onSubmit={e=>{e.preventDefault();setBusy(true);setError('');setResult(null);void api('/learning/courses/'+courseId+'/tutor','POST',{skill_id:skillId,question,mode,level,cloud_consent:consent,assessment_item_id:target?.item_id||null}).then(setResult).catch(e=>setError(e.message)).finally(()=>setBusy(false))}}>
 <label>辅导知识点<select aria-label="辅导知识点" value={skillId} disabled={busy||!!target} onChange={e=>{setSkillId(e.target.value);setResult(null)}} required>{skills.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
 <label>我的学习问题<textarea aria-label="我的学习问题" value={question} disabled={busy} onChange={e=>setQuestion(e.target.value)} required maxLength={2000} rows={4}/></label>
 <label>辅导方式<select aria-label="辅导方式" value={mode} disabled={busy} onChange={e=>{setMode(e.target.value);setResult(null);setConsent(false)}}><option value="local">本地阅读引导（不调用模型）</option><option value="cloud">云端学习辅导（需已激活模型）</option></select></label>
 <label>提示程度<select aria-label="提示程度" value={level} disabled={busy} onChange={e=>setLevel(Number(e.target.value))}><option value={1}>一级：启发提示</option><option value={2}>二级：分步思路</option><option value={3}>三级：详细讲解</option></select></label>
 {mode==='cloud'&&<label className="choice"><input type="checkbox" checked={consent} disabled={busy} onChange={e=>setConsent(e.target.checked)}/>同意将本次问题、所选已交卷题目的作答上下文及必要的已授权正文片段发送至已配置的模型</label>}
 <button disabled={busy||assessmentPending||!skillId||!question.trim()||(mode==='cloud'&&!consent)}>{busy?'正在生成辅导…':'获取学习辅导'}</button></form>
 {error&&<p role="alert">{error}</p>}{result&&show(result)}
 <button disabled={busy||assessmentPending} onClick={()=>{setError('');void loadHistory().catch(e=>setError(e.message))}}>查看本人辅导历史</button>
 {history.map(r=><details key={r.id}><summary>{new Date(r.created_at).toLocaleString()} · {r.mode==='cloud'?'云端':'本地'} · {r.status==='succeeded'?'已完成':r.status==='failed'?'失败':'处理中'}</summary><p>{r.question}</p>{r.error_code&&<p>错误：{r.error_code}；可调整后重新请求。</p>}{!r.evidence_available?<p>来源或测验状态已变化，暂不展示历史辅导内容。</p>:r.status==='succeeded'&&show({...r.result,sources:r.sources})}</details>)}
 </section>
}
