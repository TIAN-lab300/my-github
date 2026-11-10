import {useState,useEffect} from 'react';
import {api} from './api';
export function PlanningReadiness(){
 const [status,setStatus]=useState<any>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function load(){setBusy(true);setError('');try{setStatus(await api('/planning/model-status'))}catch(e){setStatus(null);setError((e as Error).message)}finally{setBusy(false)}}
 useEffect(()=>{void load()},[]);
 return <section className="card"><h2>模型配置与题库说明</h2>{error&&<p className="error" role="alert">模型状态读取失败：{error}</p>}{status&&<p role="status">{status.ready?'云端模型已就绪：'+status.model:status.active?'已激活模型，但后端缺少对应密钥':'尚未激活云端模型配置'}</p>}<button disabled={busy} onClick={()=>void load()}>刷新模型状态</button><details><summary>如何激活模型配置</summary><ol><li>由管理员登录，在左侧进入“模型配置”。学生账号不能激活模型。</li><li>选择服务商、填写模型名称，保存配置；在后端进程配置对应密钥环境变量并重启服务。</li><li>点击“真实能力试验”，完成JSON连通性验证。</li><li>执行60场景质量评价，在模型配置页逐例复核并批准质量报告。</li><li>点击该配置的“激活”，再回到本页刷新状态，选择“真实云端四智能体”。</li></ol></details><p className="footnote">诊断题来自内置或管理员审核题库，不需要激活云端模型。无云端配置时可选择“本地规则规划”。题库不足需由管理员在“知识图谱”补充并激活经审核的版本。</p></section>;
}
