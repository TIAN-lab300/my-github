import {useEffect,useState} from 'react';
import {api} from './api';
import {ResourcePreview} from './ResourcePreview';
import {RecordEditor} from './RecordEditor';
export function PersonalResources(){
 const [items,setItems]=useState<any[]>([]),[detail,setDetail]=useState<any>(null),[editor,setEditor]=useState<any>(null);
 const [query,setQuery]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 async function load(){setItems(await api('/resources?scope=private&q='+encodeURIComponent(query)))}
 useEffect(()=>{void load().catch(e=>setError(e.message))},[]);
 async function act(fn:()=>Promise<void>){if(busy)return;setBusy(true);setError('');setNotice('');try{await fn()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <section className="card" aria-label="我的个人资料"><h2>我的个人资料与补充</h2><p>上传和收藏仅保存到本人资料库，无需加入班级，其他学生和教师不能查看。允许云端处理是独立授权。</p>
 {error&&<p role="alert" className="error">{error}</p>}{notice&&<p role="status">{notice}</p>}
 <details><summary>上传个人文件</summary><form onSubmit={e=>{e.preventDefault();const form=e.currentTarget;const data=new FormData(form);void act(async()=>{const results=await api<any[]>('/resources','POST',data);setNotice(results.map(r=>r.filename+'：'+(r.error||'已保存到个人资料库')).join('；'));if(results.every(r=>!r.error))form.reset();await load()})}}>
 <label className="field">个人资料标题<input name="title" maxLength={200}/></label><label className="field">资料说明<textarea name="description" required maxLength={3000}/></label><label className="field">资料标签<input name="tags" required maxLength={500}/></label><label className="field">来源与使用权限<input name="source_license" required maxLength={1000}/></label><label className="field">个人资料文件<input name="files" type="file" multiple required accept=".md,.txt,.pdf,.docx,.pptx,.srt,.vtt,.mp4,.webm,.mov,.m4a,.mp3,.wav,.ogg,.png,.jpg,.jpeg,.gif,.webp"/></label><label className="choice"><input name="cloud_allowed" type="checkbox" value="true"/>允许必要正文发送云端（默认不允许）</label><p>文档和图片每份20MiB，音视频每份200MiB，每批最多10份。</p><button disabled={busy}>保存到个人资料库</button></form></details>
 <details><summary>收藏个人网页链接</summary><form onSubmit={e=>{e.preventDefault();const form=e.currentTarget;const data=Object.fromEntries(new FormData(form));void act(async()=>{await api('/resources/links','POST',data);form.reset();await load();setNotice('网址已保存为个人收藏；未自动导入网页正文')})}}><label className="field">收藏标题<input name="title" required maxLength={200}/></label><label className="field">网页网址<input name="url" type="url" required maxLength={2048}/></label><label className="field">收藏说明<textarea name="description" required maxLength={3000}/></label><button disabled={busy}>保存个人链接</button></form></details>
 <form className="actions" onSubmit={e=>{e.preventDefault();void act(load)}}><label>个人资料关键词<input value={query} onChange={e=>setQuery(e.target.value)}/></label><button disabled={busy}>查询我的资料</button></form>
 {!items.length&&<p>暂无匹配的个人资料，可先上传文件或收藏链接。</p>}
 {items.map(r=><div className="listrow" key={r.id}><h3>{r.title}</h3><p>仅自己可见 · {({text:'文档',link:'网页收藏',video:'视频',audio:'音频',image:'图片'} as Record<string,string>)[r.kind]||'资料'} · {({ready:'正文可检索',not_applicable:r.kind==='link'?'外链，尚无导入正文':'尚未识别正文，可查看原文件',queued:'等待解析',running:'解析中',failed:'解析失败',review_required:'识别结果待核对',cancelled:'已取消解析'} as Record<string,string>)[r.parse_status]||'查看解析状态'}</p><p>{r.description}</p><div className="actions"><button disabled={busy} onClick={()=>void act(async()=>setDetail(await api('/resources/'+r.id)))}>查看个人资料</button><button disabled={busy} onClick={()=>setEditor(r)}>编辑个人资料</button></div></div>)}
 {detail&&<section className="card"><h3>{detail.title}</h3><button onClick={()=>setDetail(null)}>关闭个人资料</button><ResourcePreview resource={detail}/>{detail.kind==='link'?<a href={detail.filename} target="_blank" rel="noopener noreferrer">打开个人收藏原站</a>:<a href={'/api/v1/resources/'+detail.id+'/download'}>下载个人文件</a>}</section>}
 {editor&&<RecordEditor kind="resource" record={editor} members={[]} classes={[]} onClose={()=>setEditor(null)} onSave={async(path,body)=>{await api(path,'PATCH',body);setEditor(null);await load();if(detail?.id===editor.id)setDetail(await api(path));setNotice('个人资料修改已保存')}}/>}
 </section>
}
