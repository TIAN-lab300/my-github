import {useRef,useState} from 'react';

export function DeleteCandidate({onDelete}:{onDelete:()=>Promise<void>}){
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const lock=useRef(false);
  async function remove(){
    if(lock.current)return;
    lock.current=true;setBusy(true);setError('');
    try{await onDelete()}catch(e){setError((e as Error).message)}finally{lock.current=false;setBusy(false)}
  }
  return <div aria-label="删除候选路径">
    <button type="button" disabled={busy} onClick={()=>void remove()}>{busy?'正在删除…':'删除候选'}</button>
    {error&&<p role="alert">{error}</p>}
  </div>
}
