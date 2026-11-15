import {useEffect,useState} from 'react';
import {api} from './api';
const labels:Record<string,string>={MODEL_KEY_MISSING:'服务端未设置模型密钥',MODEL_AUTH_ERROR:'模型密钥或权限无效',MODEL_QUOTA_EXHAUSTED:'模型调用额度不足',MODEL_RATE_LIMIT:'模型服务正在限流',MODEL_NOT_FOUND:'模型ID或接口不可用',MODEL_REQUEST_INVALID:'模型ID或请求参数不被接受'};
export function CloudMode({value,onChange}:{value:string;onChange:(value:string)=>void}){
 const [status,setStatus]=useState<any>(null),[error,setError]=useState('');
 async function refresh(){try{setStatus(await api('/planning/model-status'));setError('')}catch(e){setError((e as Error).message)}}
 useEffect(()=>{refresh()},[]);
 const reason=status?.ready?'模型已启用，可以生成真实云端规划':!status?.key_ready?'服务端缺少模型密钥，请管理员从云端版入口启动':status?.latest_status==='failed'?(labels[status.last_error_code]||'上次连通性评估失败，请管理员检查模型配置'):status?.latest_status==='approved'?'模型已连通，等待60场景质量报告与复核':'模型尚未通过质量评估并激活';
 return <section className="card"><label>规划方式<select value={value} onChange={event=>onChange(event.target.value)}><option value="local">本地规则规划</option><option value="cloud" disabled={!status?.ready}>真实云端四智能体</option></select></label><p role="status">云端状态：{error||reason}</p><button type="button" onClick={refresh}>刷新模型状态</button><p>云端规划仅使用已获云端授权的课程片段。</p></section>
}
