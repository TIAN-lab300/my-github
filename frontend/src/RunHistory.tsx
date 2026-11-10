import {useState} from 'react';
import {api} from './api';
export function RunHistory({goalId,onSelect}:{goalId:string;onSelect:(run:any)=>void}){
 const [runs,setRuns]=useState<any[]>([]);
 const [error,setError]=useState('');
 return <section><button onClick={async()=>{try{setRuns(await api('/goals/'+goalId+'/runs'));setError('')}catch(e){setError((e as Error).message)}}}>查看规划运行历史</button>
  {error&&<p role="alert">{error}</p>}
  {runs.map(run=><p key={run.id}>{run.kind} · {run.status} · 重试{run.retry_count}次
   <button onClick={async()=>{try{onSelect(await api('/runs/'+run.id))}catch(e){setError((e as Error).message)}}}>恢复查看此运行</button>
  </p>)}
 </section>
}
export function RunTrace({run}:{run:any}){
 return <section><h3>运行输入与检查点</h3><p>已完成阶段 {run.checkpoint?.last_agent||'暂无'} · {run.checkpoint?.resumable?'检查点已保存':'等待检查点'}</p>
  {run.steps?.map((step:any,index:number)=>{
   const input=JSON.parse(step.input_fingerprint||'{}'),output=JSON.parse(step.output_summary||'{}');
   return <p key={index}>第{step.attempt_no+1}次执行 · {step.agent} · {new Date(step.created_at).toLocaleString()} · 目标版本{input.goal} · 预算版本{input.budget} · 输出任务{output.task_ids?.length||0}项 · 规则{output.rules?.length||0}条</p>;
  })}
 </section>
}
