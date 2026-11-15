import {useEffect, useState} from 'react';
import {api, parse} from './api';

type RecordData = Record<string, any>;
const statuses: Record<string, string> = {draft:'草稿',pending:'待审核',approved:'审核通过',published:'已发布',rejected:'已驳回',disabled:'已停用',open:'作答中',submitted:'已提交',invalid:'已失效'};
const emptyQuestion = {skill:'functions',prompt:'',options:['','',''],answer:'0',explanation:'',difficulty:'medium',purpose:'both',group:'functions-基础',family:'',source:''};

export function QuestionBank({role}:{role:'admin'|'teacher'}) {
    const [records,setRecords] = useState<RecordData[]>([]);
    const [editor,setEditor] = useState<RecordData|null>(null);
    const [editingId,setEditingId] = useState('');
    const [message,setMessage] = useState('');
    const [busy,setBusy] = useState(false);
    const [skill,setSkill] = useState('');
    const [status,setStatus] = useState('');
    const [purpose,setPurpose] = useState('');
    const [comments,setComments] = useState<Record<string,string>>({});
    const [skills,setSkills] = useState<RecordData[]>([]);

    async function reload() { setRecords(await api('/question-bank')); }
    useEffect(()=>{reload().catch(e=>setMessage(e.message));api('/curriculum/skills').then(r=>setSkills(r.skills)).catch(e=>setMessage(e.message));},[]);
    async function operate(work:()=>Promise<unknown>, success:string) {
        setBusy(true);setMessage('');
        try { await work();await reload();setMessage(success); }
        catch(error) { setMessage((error as Error).message); }
        finally { setBusy(false); }
    }
    const visible = records.filter(r=>(!skill||r.content.skill===skill)&&(!status||r.status===status)&&(!purpose||r.content.purpose===purpose));
    return <section className="card">
        <h2>题库与审核</h2>
        <p>发布后供学生测验使用。修改发布内容需建立新版本，历史测验保留原题。</p>
        {message&&<p role="status" className="notice">{message}</p>}
        <div className="actions">
            <label>知识点<select value={skill} onChange={e=>setSkill(e.target.value)}><option value="">全部</option>{skills.map(s=><option key={s.id} value={s.id}>{s.name||s.id}</option>)}</select></label>
            <label>状态<select value={status} onChange={e=>setStatus(e.target.value)}><option value="">全部</option>{Object.entries(statuses).filter(([id])=>!['open','submitted','invalid'].includes(id)).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
            <label>用途<select value={purpose} onChange={e=>setPurpose(e.target.value)}><option value="">全部</option><option value="diagnostic">目标诊断</option><option value="practice">首次测验</option><option value="retest">复测</option><option value="both">首次与复测</option></select></label>
            <button disabled={busy} onClick={()=>{setEditingId('');setEditor({...emptyQuestion});}}>新建题目</button>
            <button disabled={busy} onClick={()=>operate(reload,'列表已刷新')}>刷新题库</button>
        </div>
        {editor&&<form onSubmit={e=>{e.preventDefault();operate(async()=>{await api(editingId?'/question-bank/'+editingId:'/question-bank',editingId?'PUT':'POST',editor);setEditor(null)},'草稿已保存')}}>
            <h3>{editingId?'修改草稿':'新建题目'}</h3>
            <label>知识点<select value={editor.skill} onChange={e=>setEditor({...editor,skill:e.target.value,group:e.target.value+'-基础'})}>{skills.map(s=><option key={s.id} value={s.id}>{s.name||s.id}</option>)}</select></label>
            <label>题干<textarea required minLength={5} maxLength={4000} value={editor.prompt} onChange={e=>setEditor({...editor,prompt:e.target.value})}/></label>
            {editor.options.map((option:string,index:number)=><label key={index}>选项 {index+1}<input required value={option} onChange={e=>setEditor({...editor,options:editor.options.map((v:string,i:number)=>i===index?e.target.value:v)})}/></label>)}
            <div className="actions"><button type="button" disabled={editor.options.length>=6} onClick={()=>setEditor({...editor,options:[...editor.options,'']})}>增加选项</button><button type="button" disabled={editor.options.length<=2} onClick={()=>setEditor({...editor,options:editor.options.slice(0,-1),answer:'0'})}>减少选项</button></div>
            <label>正确答案<select value={editor.answer} onChange={e=>setEditor({...editor,answer:e.target.value})}>{editor.options.map((_:string,i:number)=><option key={i} value={String(i)}>选项 {i+1}</option>)}</select></label>
            <label>答案解析<textarea required minLength={5} maxLength={4000} value={editor.explanation} onChange={e=>setEditor({...editor,explanation:e.target.value})}/></label>
            <label>难度<select value={editor.difficulty} onChange={e=>setEditor({...editor,difficulty:e.target.value})}><option value="easy">基础</option><option value="medium">中等</option><option value="hard">进阶</option></select></label>
            <label>用途<select value={editor.purpose} onChange={e=>setEditor({...editor,purpose:e.target.value})}><option value="diagnostic">目标诊断</option><option value="practice">首次测验</option><option value="retest">复测</option><option value="both">首次与复测</option></select></label>
            <label>等价题组<input required value={editor.group} onChange={e=>setEditor({...editor,group:e.target.value})}/></label>
            <label>近似题标识（仅换变量或选项顺序的题目填写相同标识）<input value={editor.family||''} onChange={e=>setEditor({...editor,family:e.target.value})}/></label>
            <label>来源说明<input required value={editor.source} onChange={e=>setEditor({...editor,source:e.target.value})}/></label>
            <button disabled={busy}>保存草稿</button><button type="button" onClick={()=>setEditor(null)}>取消编辑</button>
        </form>}
        <p>共 {visible.length} 个版本</p>
        {visible.map(record=><article className="card" key={record.id}>
            <h3>{record.content.prompt}</h3><p>{record.content.skill} · 版本 {record.version} · {statuses[record.status]} · {record.content.group}</p>
            <ol>{record.content.options.map((option:string,i:number)=><li key={i}>{option}{String(i)===record.content.answer?'（正确答案）':''}</li>)}</ol>
            <p>{record.content.explanation}</p><p>来源 {record.content.source}</p>
            {record.previous_content&&<details><summary>与上个版本比较</summary><p>上版题干 {record.previous_content.prompt}</p><p>上版选项 {record.previous_content.options.join(' / ')}</p><p>上版答案 {Number(record.previous_content.answer)+1}</p><p>上版解析 {record.previous_content.explanation}</p></details>}
            <details><summary>审核记录</summary>{record.reviews.map((review:RecordData)=><p key={review.id}>{review.created_at} · {review.actor_id} · {review.action} · {review.comment}</p>)}</details>
            <div className="actions">
                {['draft','rejected'].includes(record.status)&&<button disabled={busy} onClick={()=>{setEditingId(record.id);setEditor({...record.content});}}>编辑草稿</button>}
                {['published','disabled'].includes(record.status)&&<button disabled={busy} onClick={()=>operate(async()=>{const result=await api(`/question-bank/${record.id}/versions`,'POST');const list=await api('/question-bank');const draft=list.find((r:RecordData)=>r.id===result.id);setEditingId(result.id);setEditor({...draft.content});},'新版本草稿已打开')}>创建新版本</button>}
                {record.status==='draft'&&<button disabled={busy} onClick={()=>operate(()=>api(`/question-bank/${record.id}/review`,'POST',{action:'submit'}),'已提交审核')}>提交审核</button>}
            </div>
            {role==='admin'&&['pending','approved','published'].includes(record.status)&&<div>
                <label>审核或停用意见<input value={comments[record.id]||''} onChange={e=>setComments({...comments,[record.id]:e.target.value})}/></label>
                {(record.status==='pending'?['approve','reject']:record.status==='approved'?['publish']:['disable']).map(action=><button disabled={busy} key={action} onClick={()=>operate(()=>api(`/question-bank/${record.id}/review`,'POST',{action,comment:comments[record.id]||''}),'操作已保存')}>{({approve:'审核通过',reject:'驳回',publish:'发布',disable:'停用'} as Record<string,string>)[action]}</button>)}
            </div>}
        </article>)}
    </section>;
}

export function SessionAssessment({path,item,onChanged}:{path:string;item:string;onChanged:()=>Promise<void>}) {
    const [session,setSession] = useState<RecordData|null>(null);
    const [history,setHistory] = useState<RecordData[]>([]);
    const [message,setMessage] = useState('');
    const [busy,setBusy] = useState(false);
    async function reload(selected?:string) {
        const list = await api(`/paths/${path}/items/${item}/sessions`);
        setHistory(list);setSession(list.find((s:RecordData)=>s.id===selected)||list[0]||null);
    }
    useEffect(()=>{setSession(null);setHistory([]);setMessage('');let alive=true;api(`/paths/${path}/items/${item}/sessions`).then(list=>{if(alive){setHistory(list);setSession(list[0]||null)}}).catch(e=>{if(alive)setMessage(e.message)});return()=>{alive=false}},[path,item]);
    async function operate(work:()=>Promise<void>) {setBusy(true);setMessage('');try{await work()}catch(error){setMessage((error as Error).message)}finally{setBusy(false)}}
    function start(repeat=false) {operate(async()=>{const result=await api(`/paths/${path}/items/${item}/${repeat?'retests':'sessions'}`,'POST');await reload(result.id)})}
    return <section>
        {message&&<p role="status" className="notice">{message}</p>}
        {!session&&<button disabled={busy} onClick={()=>start()}>开始测验</button>}
        {session&&<>
            <p>{statuses[session.status]} · {session.previous_id?'复测':'首次测验'} · {new Date(session.created_at).toLocaleString()}</p>
            {session.invalid_reason&&<p className="error">{session.invalid_reason}</p>}
            <form onSubmit={e=>{e.preventDefault();operate(async()=>{const result=await api(`/assessment-sessions/${session.id}/submit`,'POST',{answers:session.answers,minutes:session.minutes});await reload(result.id);await onChanged();setMessage('测验已提交，掌握证据与路径状态已刷新')})}}>
                {session.questions.map((question:RecordData)=><fieldset key={question.id} disabled={busy||session.status!=='open'}><legend>{question.prompt}</legend>{question.options.map((option:string,i:number)=><label key={i}><input type="radio" name={question.id} required checked={session.answers[question.id]===String(i)} onChange={()=>setSession({...session,answers:{...session.answers,[question.id]:String(i)}})}/>{option}</label>)}</fieldset>)}
                {session.status==='open'&&<><label>累计测验用时（分钟）<input type="number" min={1} max={1440} required value={session.minutes} onChange={e=>setSession({...session,minutes:Number(e.target.value)})}/></label>
                    <button type="button" disabled={busy} onClick={()=>operate(async()=>{await api(`/assessment-sessions/${session.id}/answers`,'PUT',{answers:session.answers,minutes:session.minutes});setMessage('答案与用时已保存')})}>保存答案</button><button disabled={busy}>提交评分</button></>}
            </form>
            {session.result&&<><h3>测验结果 · {Math.round(session.result.score*100)}%</h3><p>本次测验已计入掌握证据，重复查看不会增加证据。</p>{session.review_questions?.map((q:RecordData)=><p key={q.id}>正确答案 {q.options[Number(q.answer)]}。{q.explanation}</p>)}<p>{Object.entries(session.mastery||{}).map(([skill,value])=>`${skill} 当前掌握度 ${Math.round((value as RecordData).probability*100)}%`).join(' · ')}</p><button disabled={busy} onClick={()=>start(true)}>申请复测</button></>}
        </>}
        <h3>历次测验与原题复习</h3><p>选择已提交记录可回看题目与解析。</p>
        {history.map(record=><p key={record.id}><button disabled={busy} onClick={()=>setSession(record)}>{new Date(record.created_at).toLocaleString()} · {statuses[record.status]}{record.result?` · ${Math.round(record.result.score*100)}%`:''}</button></p>)}
    </section>;
}

export function TeacherAssessments({classId}:{classId:string}) {
    const [records,setRecords] = useState<RecordData[]>([]);
    const [error,setError] = useState('');
    useEffect(()=>{let alive=true;api(`/teacher/classes/${classId}/assessment-sessions`).then(r=>{if(alive)setRecords(r)}).catch(e=>{if(alive)setError(e.message)});return()=>{alive=false}},[classId]);
    return <section className="card"><h2>班级路径测验记录</h2>{error&&<p>{error}</p>}{records.map(r=><details key={r.id}><summary>{r.student_name} · {new Date(r.created_at).toLocaleString()} · {statuses[r.status]} {r.result?Math.round(r.result.score*100)+'%':''}</summary>{r.questions.map((q:RecordData)=><p key={q.id}>{q.prompt}</p>)}{r.result&&parse(r.result.feedback).map((f:RecordData)=><p key={f.id}>{f.correct?'正确':'需补强'} · {f.explanation}</p>)}</details>)}</section>;
}
