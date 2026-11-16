import {useState} from 'react';
type Entry={title:string;school:string;platform:string;url:string;note:string;checked_at:string};
function embeddable(url:string){try{const u=new URL(url);return u.protocol==='https:'&&u.hostname==='www.icourse163.org'&&!u.username&&!u.password&&u.pathname.startsWith('/course/')}catch{return false}}
export function CourseLinks({links}:{links:Entry[]}){
 const [activeUrl,setActiveUrl]=useState<string|null>(null),[failed,setFailed]=useState(false);
 const active=links.find(link=>link.url===activeUrl)||null;
 return <section aria-label="课程视频学习入口"><h3>课程视频与原站学习</h3>{links.length?<>
 <p>可在本页打开原站课程窗口，无需把视频文件下载到项目服务器。登录、选课及播放权限以原站为准；观看进度暂不自动同步。</p>
 {links.map(link=><div className="listrow" key={link.url}><h4>{link.title}</h4><p>{link.school} · {link.platform}</p><p>{link.note}</p><div className="actions">{embeddable(link.url)&&<button type="button" aria-pressed={active?.url===link.url} onClick={()=>{setFailed(false);setActiveUrl(link.url)}}>在本页打开：{link.title}</button>}<a href={link.url} target="_blank" rel="noopener noreferrer">前往原站学习：{link.title} ↗</a></div><p className="footnote">课程主页核对日期：{link.checked_at}</p></div>)}
 {active&&<section aria-label="嵌入课程窗口"><div className="row"><h4>本页课程窗口 · {active.title}</h4><button type="button" onClick={()=>setActiveUrl(null)}>关闭课程窗口</button></div>
 <p role="status">请在下方原站窗口选择课程章节。若空白、提示禁止嵌入或无法登录，请使用“前往原站学习”；浏览器无法可靠判断跨站视频是否播放成功。</p>
 {failed&&<p role="alert">课程窗口加载失败，请在原站打开。</p>}
 <iframe key={active.url} title={'原站课程：'+active.title} src={active.url} allow="fullscreen; encrypted-media; picture-in-picture" allowFullScreen sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox" referrerPolicy="strict-origin-when-cross-origin" onError={()=>setFailed(true)} style={{width:'100%',height:'min(75vh, 780px)',minHeight:400,border:'1px solid #d5ded8',borderRadius:8}}/>
 <a href={active.url} target="_blank" rel="noopener noreferrer">无法观看？在原站打开 {active.title} ↗</a>
 </section>}
 </>:<p>本课程尚未添加已核对的视频课程入口，可先查看下方公开资料原站链接。</p>}</section>;
}
