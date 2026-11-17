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
   const calls=output.model_calls||[];
   return <div className="listrow" key={index}><p>第{step.attempt_no+1}次执行{output.review_round?' · 第'+output.review_round+'轮':''} · {step.agent} · {new Date(step.created_at).toLocaleString()} · 目标版本{input.goal} · 预算版本{input.budget} · 输出任务{output.task_ids?.length||0}项 · 规则{output.rules?.length||0}条</p><p>{calls.length?(output.model_calls_semantics==='step-only-v1'?'本步骤模型调用 ':'累计模型调用（历史记录） ')+calls.length+' 次（成功 '+calls.filter((c:any)=>c.status==='succeeded').length+' 次）':'本步骤未记录模型调用；本地执行为确定性业务节点'}</p>{output.review_decision&&<p>审查结论：{output.review_decision==='approved'?'通过':'未通过'}</p>}{output.task_descriptions?.length>0&&<details><summary>查看本轮活动与引用</summary>{output.task_descriptions.map((task:any,i:number)=><div key={i}><p>{task.skill_id} · 示例 {task.example_id||'未提供项目示例'}</p><p>{task.instructions}</p><p>引用版本：{task.citation_version_ids.join('、')}</p></div>)}</details>}{output.semantic_issues?.map((issue:string,i:number)=><p key={'issue-'+i} className="notice">审查需修复：{issue}</p>)}{calls.map((call:any,i:number)=><p key={i}>{call.model||'绑定模型'} · {call.status} · {call.elapsed_ms} ms · 配置 {call.model_config_id}{call.request_id?' · 请求 '+call.request_id:''}</p>)}</div>;
  })}
 </section>
}
