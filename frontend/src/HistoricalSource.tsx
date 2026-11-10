import {useState} from 'react';
import {api} from './api';

export function HistoricalSource({source}:{source:any}){
 const [body,setBody]=useState<string|null>(null);
 const [error,setError]=useState('');
 const [busy,setBusy]=useState(false);
 async function open(){
  setBusy(true);setError('');
  try{
   const result=await api<{body:string}>(`/resources/${source.resource_id}/versions/${source.version_id}/content`);
   setBody(result.body);
  }catch(e){setError((e as Error).message)}
  finally{setBusy(false)}
 }
 return <section><p>{source.title} · {source.location} · 版本{source.version_id.slice(0,8)}</p>
  {source.excerpt&&<p className="reading">{source.excerpt}</p>}<button disabled={busy} onClick={open}>查看引用版本正文</button>
  {error&&<p role="alert">{error}</p>}
  {body!==null&&<><article className="reading">{body}</article><button onClick={()=>setBody(null)}>收起引用正文</button></>}
 </section>;
}
