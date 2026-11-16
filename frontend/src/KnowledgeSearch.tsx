import {useEffect,useState} from 'react';
import {api} from './api';
import {PersonalResources} from './PersonalResources';

export function KnowledgeSearch({classes,role}:{classes:any[];role:string}) {
  const [query,setQuery]=useState('');
  const [scope,setScope]=useState('all');
  const [personalVersion,setPersonalVersion]=useState(0);
  const [local,setLocal]=useState<any>(null);
  const [external,setExternal]=useState<any>(null);
  const [classId,setClassId]=useState('');
  const [saved,setSaved]=useState<Record<string,string>>({});
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const [busy,setBusy]=useState(false);
  const [searchStatus,setSearchStatus]=useState<any>(null);
  useEffect(()=>{api('/retrieval/search/status').then(setSearchStatus).catch(()=>setSearchStatus(null))},[]);

  async function perform(work:()=>Promise<void>) {
    setBusy(true);setError('');setNotice('');
    try {await work()}
    catch(failure){setError((failure as Error).message)}
    finally{setBusy(false)}
  }

  return <>{role==='student'&&<PersonalResources key={personalVersion}/>}<section className="card">
    <h2>资料检索与外部补充</h2>
    <form onSubmit={event=>{event.preventDefault();setExternal(null);perform(async()=>setLocal(await api('/retrieval/search','POST',{query,scope})))}}>
      <label>检索范围<select aria-label="检索范围" value={scope} onChange={e=>{setScope(e.target.value);setLocal(null);setExternal(null)}}><option value="private">我的个人资料</option><option value="class">已加入班级的资料</option><option value="school">学校共享资料</option><option value="all">全部有权查看的资料</option></select></label><label>查询内容<input value={query} onChange={event=>setQuery(event.target.value)} required maxLength={200}/></label>
      <p>课程目录、知识点和MOOC入口请选“学校共享资料”或“全部有权查看的资料”；“我的个人资料”只查本人文件与收藏。</p><button disabled={busy}>搜索课程与资料</button>
    </form>
    {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
    {local&&<><p>{local.coverage}</p>{local.scope_hint&&<p className="notice">{local.scope_hint}</p>}{scope==='private'&&<button disabled={busy} onClick={()=>perform(async()=>{setScope('school');setLocal(await api('/retrieval/search','POST',{query,scope:'school'}))})}>改为搜索学校课程</button>}
      {!!local.course_results?.length&&<section aria-label="课程搜索结果"><h3>课程与学习入口（非已导入正文）</h3>{local.course_results.map((c:any)=><div key={c.course_id} className="listrow"><h3>{c.name}</h3><p>{c.skill_count}个候选知识点 · {c.matched_skills.length?'匹配知识点：'+c.matched_skills.map((s:any)=>s.name).join('、'):'课程名称或学习入口匹配'}</p><a href={'#resources?course='+encodeURIComponent(c.course_id)}>查看课程章节与知识点</a>{c.links.map((l:any)=><p key={l.url}>{l.school} · <a href={l.url} target="_blank" rel="noopener noreferrer">{l.title} · 前往原站学习 ↗</a></p>)}{!c.links.length&&<p>尚未添加已核对的MOOC课程入口。</p>}{c.sources.map((s:any)=><p key={s.url}><a href={s.url} target="_blank" rel="noopener noreferrer">公开资料原站：{s.title} ↗</a></p>)}</div>)}</section>}
      {!!local.results.length&&<h3>已导入正文命中</h3>}<p>{local.vector_available?'已使用关键词与本地中文向量':'当前使用关键词，向量索引就绪后参与检索'}</p>
      {local.results.map((item:any,index:number)=><div className="listrow" key={index}>
        <h3>{item.title}</h3><p className="reading">{item.excerpt}</p><p>{item.location}</p>
        <a href={`/api/v1/resources/${item.resource_id}/versions/${item.resource_version_id}/download`}>下载该来源版本</a>
      </div>)}
      {!local.results.length&&local.metadata_results?.map((item:any)=><div className="listrow" key={item.resource_id}><h3>{item.title}</h3><p>仅标题、标签或说明匹配，尚无可引用正文。</p></div>)}
      <p>如果仍缺资料，可主动搜索外部网址。学生可保存为个人链接收藏；教师可登记到班级。网页正文需另行导入审核。</p>
      {searchStatus&&<p role="status">{searchStatus.configured?'联网搜索服务已配置，点击后获取实时网址。':'自动联网搜索尚未启用；可先使用下方外部搜索入口。管理员在“模型配置 → 联网搜索服务”查看配置步骤。'}</p>}
      <button disabled={busy||!query.trim()||searchStatus?.configured===false} onClick={()=>perform(async()=>setExternal(await api('/retrieval/supplement','POST',{query,mode:'web_allowed'})))}>搜索外部补充网址</button>
      {!!query.trim()&&<section aria-label="手动外部搜索"><h3>在外部网站搜索</h3><p>以下是搜索入口，不是本系统实时取得或审核的结果。找到课程网址后，可在上方“收藏个人网页链接”中保存。</p><p><a href={'https://www.bing.com/search?q='+encodeURIComponent(query+' 教程 官方文档')} target="_blank" rel="noopener noreferrer">必应搜索 ↗</a> · <a href={'https://www.baidu.com/s?wd='+encodeURIComponent(query+' 课程')} target="_blank" rel="noopener noreferrer">百度搜索 ↗</a> · <a href={'https://www.icourse163.org/search.htm?search='+encodeURIComponent(query)} target="_blank" rel="noopener noreferrer">中国大学MOOC搜索 ↗</a></p></section>}
    </>}
    {external&&<>
      {external.error&&<p role="alert">{external.error}</p>}
      <p>{external.message}</p>
      {role==='teacher'&&<label>收录班级<select value={classId} onChange={event=>setClassId(event.target.value)}><option value="">选择班级</option>{classes.filter(item=>item.status==='active').map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
      {external.results.map((item:any)=><div className="listrow" key={item.url}>
        <h3><a href={item.url} target="_blank" rel="noopener noreferrer">{item.title}</a></h3>
        <p>{item.reason}</p><p>{item.domain} · 待核实 · {new Date(item.retrieved_at).toLocaleString()}</p>
        {['teacher','student'].includes(role)&&!saved[item.url]&&<button disabled={busy||(role==='teacher'&&!classId)} onClick={()=>perform(async()=>{
          const result:any=await api('/resources/links','POST',{...(role==='teacher'?{class_id:classId}:{}),url:item.url,title:item.title,description:item.reason||query});
          setSaved(current=>({...current,[item.url]:result.id}));if(role==='student')setPersonalVersion(v=>v+1);setNotice(role==='student'?'已保存为个人链接收藏，上方列表已更新':'已登记班级待审核网址');
        })}>{role==='student'?'收藏到我的个人资料':'登记班级待审核网址'}</button>}
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
  </section></>;
}
