import {useEffect,useState} from 'react';
import {api} from './api';

export function AuditLog(){
  const [filters,setFilters]=useState<Record<string,string>>({});
  const [page,setPage]=useState(1);
  const [rows,setRows]=useState<any[]>([]);
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(false);
  useEffect(()=>{
    let active=true;
    setLoading(true);
    api<any[]>('/admin/audit?'+new URLSearchParams({...filters,page:String(page)}))
      .then(result=>{if(active){setRows(result);setError('')}})
      .catch(e=>{if(active)setError(e.message)})
      .finally(()=>{if(active)setLoading(false)});
    return()=>{active=false};
  },[filters,page]);
  return <section className="card"><h2>操作审计</h2>
    <form onSubmit={e=>{
      e.preventDefault();
      const values=Object.fromEntries(new FormData(e.currentTarget)) as Record<string,string>;
      for(const key of ['start_at','end_at'])if(values[key])values[key]=new Date(values[key]).toISOString();
      setPage(1);setFilters(values);
    }}>
      <label>操作人编号<input name="actor_id"/></label>
      <label>对象编号<input name="target_id"/></label>
      <label>动作<input name="action"/></label><label>结果<select name="result"><option value="">全部结果</option><option value="success">成功</option><option value="failed">失败</option></select></label>
      <label>开始时间<input type="datetime-local" name="start_at"/></label>
      <label>结束时间<input type="datetime-local" name="end_at"/></label>
      <button disabled={loading}>查询</button>
    </form>
    {error&&<p role="alert">{error}</p>}
    <div className="scroll"><table><thead><tr><th>时间</th><th>操作人</th><th>动作</th><th>对象</th><th>结果</th></tr></thead>
      <tbody>{rows.map(row=><tr key={row.id}><td>{new Date(row.created_at).toLocaleString()}</td><td>{row.actor_id}</td><td>{row.action}</td><td>{row.target_id}</td><td>{row.result==='failed'?'失败':'成功'}</td></tr>)}</tbody></table></div>
    {!loading&&!rows.length&&<p>没有符合条件的审计记录</p>}
    <button disabled={loading||page===1} onClick={()=>setPage(page-1)}>上一页</button>
    <span>第{page}页</span>
    <button disabled={loading||rows.length<50} onClick={()=>setPage(page+1)}>下一页</button>
  </section>;
}
