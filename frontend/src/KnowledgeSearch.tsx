import {useState} from 'react';
import {api} from './api';

export function KnowledgeSearch({classes,role}:{classes:any[];role:string}) {
  const [query,setQuery]=useState('');
  const [local,setLocal]=useState<any>(null);
  const [external,setExternal]=useState<any>(null);
  const [classId,setClassId]=useState('');
  const [saved,setSaved]=useState<Record<string,string>>({});
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const [busy,setBusy]=useState(false);

  async function perform(work:()=>Promise<void>) {
    setBusy(true);setError('');setNotice('');
    try {await work()}
    catch(failure){setError((failure as Error).message)}
    finally{setBusy(false)}
  }

  return <section className="card">
    <h2>课程资料检索与补充</h2>
    <form onSubmit={event=>{event.preventDefault();setExternal(null);perform(async()=>setLocal(await api('/retrieval/search','POST',{query})))}}>
      <label>查询内容<input value={query} onChange={event=>setQuery(event.target.value)} required maxLength={200}/></label>
      <button disabled={busy}>检索授权课程正文</button>
    </form>
    {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
    {local&&<><p>{local.coverage}</p><p>{local.vector_available?'已使用关键词与本地中文向量':'当前使用关键词，向量索引就绪后参与检索'}</p>
      {local.results.map((item:any,index:number)=><div className="listrow" key={index}>
        <h3>{item.title}</h3><p className="reading">{item.excerpt}</p><p>{item.location}</p>
        <a href={`/api/v1/resources/${item.resource_id}/versions/${item.resource_version_id}/download`}>下载该来源版本</a>
      </div>)}
      {!local.results.length&&local.metadata_results?.map((item:any)=><div className="listrow" key={item.resource_id}><h3>{item.title}</h3><p>仅标题、标签或说明匹配，尚无可引用正文。</p></div>)}
      <p>如果仍缺资料，可主动搜索外部网址。推荐页面经教师审核并导入后才能成为课程正文。</p>
      <button disabled={busy||!query.trim()} onClick={()=>perform(async()=>setExternal(await api('/retrieval/supplement','POST',{query,mode:'web_allowed'})))}>搜索外部补充网址</button>
    </>}
    {external&&<>
      {external.error&&<p role="alert">{external.error}</p>}
      <p>{external.message}</p>
      {role==='teacher'&&<label>收录班级<select value={classId} onChange={event=>setClassId(event.target.value)}><option value="">选择班级</option>{classes.filter(item=>item.status==='active').map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
      {external.results.map((item:any)=><div className="listrow" key={item.url}>
        <h3><a href={item.url} target="_blank" rel="noopener noreferrer">{item.title}</a></h3>
        <p>{item.reason}</p><p>{item.domain} · 待核实 · {new Date(item.retrieved_at).toLocaleString()}</p>
        {role==='teacher'&&!saved[item.url]&&<button disabled={busy||!classId} onClick={()=>perform(async()=>{
          const result:any=await api('/resources/links','POST',{class_id:classId,url:item.url,title:item.title,description:item.reason||query});
          setSaved(current=>({...current,[item.url]:result.id}));setNotice('已登记待审核网址');
        })}>登记待审核网址</button>}
        {role==='teacher'&&saved[item.url]&&<button disabled={busy} onClick={()=>{
          if(!window.confirm('确认已审阅该网页，并有权抓取其正文用于本班教学？'))return;
          perform(async()=>{
            const resource:any=await api('/resources/'+saved[item.url]);
            await api('/resources/'+resource.id+'/import-link','POST',{version:resource.version,authorized:true});
            setNotice('正文已导入草稿，请到课程知识库审核发布');
          });
        }}>审核并授权导入正文</button>}
      </div>)}
      {!external.results.length&&!external.error&&<p>本次未找到外部结果，请调整检索词或补充资料。</p>}
    </>}
  </section>;
}
