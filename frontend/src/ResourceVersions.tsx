import {useState,useEffect} from 'react';
import {api} from './api';

export function ResourceVersions({resource:r,onChanged}:{resource:any;onChanged:()=>void}) {
  const [items,setItems]=useState<any[]>([]);
  const [jobs,setJobs]=useState<any[]>([]);
  const [message,setMessage]=useState('');
  const [busy,setBusy]=useState(false);
  const [refresh,setRefresh]=useState(0);
  let extraction:any={};
  try{extraction=JSON.parse(r.extraction_json||'{}')}catch{extraction={}}
  const hasPending=jobs.some(job=>['queued','running'].includes(job.status));

  useEffect(()=>{
    let active=true;
    api<any[]>('/resources/'+r.id+'/parse-jobs').then(result=>{if(active)setJobs(result)})
      .catch(error=>{if(active)setMessage(error.message)});
    return()=>{active=false};
  },[r.id,refresh,r.current_version]);

  useEffect(()=>{
    if(!hasPending&&!['queued','running'].includes(r.parse_status))return;
    const timer=window.setInterval(()=>{setRefresh(value=>value+1);onChanged()},3000);
    return()=>window.clearInterval(timer);
  },[r.id,r.parse_status,hasPending,onChanged]);

  async function perform(work:()=>Promise<unknown>,notice:string) {
    setBusy(true);
    try {await work();setMessage(notice);setRefresh(value=>value+1);onChanged()}
    catch(error){setMessage((error as Error).message)}
    finally{setBusy(false)}
  }

  return <section className="card">
    <h3>正文版本与资料处理</h3>
    <p>解析状态 {r.parse_status} · 索引状态 {r.index_status}</p>
    {typeof extraction.confidence==='number'&&<p>{extraction.confidence_kind==='sequence_probability_proxy'?'转写质量代理分数':'文字识别分数'} {extraction.confidence.toFixed(3)}，低于0.85需人工复核。</p>}
    {extraction.subtitle_duration_verified===false&&<p>字幕时间尚未与媒体长度核验，请检查字幕与原媒体是否一致。</p>}
    {Array.isArray(extraction.unreadable_pages)&&extraction.unreadable_pages.length>0&&<p>未识别到文字的页码 {extraction.unreadable_pages.join('、')}，请对照原文件复核。</p>}
    <button onClick={()=>{setRefresh(value=>value+1);onChanged()}}>刷新状态</button>
    <p>识别结果产生新版本，低置信度正文需先复核，再审核发布。</p>
    {message&&<p role="status">{message}</p>}
    <div className="actions">
      {(r.kind==='image'||r.mime==='application/pdf')&&<button disabled={busy||hasPending} onClick={()=>perform(()=>api('/resources/'+r.id+'/process','POST',{version:r.version,operation:'ocr'}),'本地OCR已排队')}>识别图片或扫描PDF</button>}
      {['audio','video'].includes(r.kind)&&<button disabled={busy||hasPending} onClick={()=>perform(()=>api('/resources/'+r.id+'/process','POST',{version:r.version,operation:'transcribe'}),'本地语音转写已排队')}>自动转写音视频</button>}
      {r.parse_status==='ready'&&<button disabled={busy} onClick={()=>perform(()=>api('/resources/'+r.id+'/rebuild-index','POST',{version:r.version}),'正文索引已重建')}>重建正文索引</button>}
      {r.parse_status==='failed'&&r.kind==='text'&&<button disabled={busy} onClick={()=>perform(()=>api('/resources/'+r.id+'/retry-parse','POST'),'正文解析已重新排队')}>重试正文解析</button>}
      <button disabled={busy} onClick={()=>perform(async()=>setItems(await api('/resources/'+r.id+'/versions')),'已刷新历史版本')}>查看版本历史</button>
    </div>
    {jobs.map(job=><div className="listrow" key={job.id}>
      <p>{job.operation} · {job.status} · 已尝试{job.attempts}次</p>
      {job.error&&<p role="alert">{job.error}</p>}
      {['queued','running'].includes(job.status)&&<button disabled={busy} onClick={()=>perform(()=>api(`/resources/${r.id}/parse-jobs/${job.id}/cancel`,'POST'),'已取消处理')}>取消处理</button>}
      {['failed','cancelled'].includes(job.status)&&<button disabled={busy||job.attempts>=3} onClick={()=>perform(()=>api(`/resources/${r.id}/parse-jobs/${job.id}/retry`,'POST'),'重试已排队')}>重试此任务</button>}
    </div>)}
    {r.review_status==='pending'&&<form key={r.current_version} onSubmit={event=>{
      event.preventDefault();const form=new FormData(event.currentTarget);
      perform(()=>api('/resources/'+r.id+'/review-extraction','POST',{version:r.version,body:form.get('body')}),'复核正文已保存为新草稿，请审核后发布');
    }}><label>校正识别正文<textarea name="body" defaultValue={r.body} required rows={12}/></label><button disabled={busy}>确认复核正文</button></form>}
    {r.kind==='text'&&<form onSubmit={event=>{
      event.preventDefault();const form=new FormData(event.currentTarget);
      form.set('expected_version',String(r.version));form.set('background','true');
      perform(()=>api('/resources/'+r.id+'/versions','POST',form),'新正文已排队解析，处理期间当前正文可用');
    }}><label>上传新正文<input type="file" name="file" accept=".txt,.md,.pdf,.docx,.pptx,.srt,.vtt" required/></label><button disabled={busy}>保存新版本</button></form>}
    {items.map(version=><div className="listrow" key={version.id}>{version.filename} · {version.parse_status} · {new Date(version.created_at).toLocaleString()}</div>)}
  </section>;
}
