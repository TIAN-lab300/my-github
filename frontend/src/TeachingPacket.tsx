export function TeachingPacket({packet}:{packet:any}){
 if(!packet)return null;
 const example=packet.worked_example,assessment=packet.assessment;
 return <section className="card" aria-label="任务执行材料"><h4>{packet.purpose==='review'?'已达标复习材料':'学习与测评材料'}</h4><p>{packet.reading.instruction}</p>{packet.reading.sources.map((s:any)=><p key={s.version_id}><a href={`/api/v1/resources/${s.resource_id}/versions/${s.version_id}/download`}>{s.title} · 下载对应版本</a></p>)}
 {example?<details><summary>展开具体示例、完整代码与演算要求</summary><p>{example.origin}</p><p>{example.prompt}</p><pre style={{whiteSpace:'pre-wrap'}}>{example.code}</pre>{example.events&&<><p>完整追踪：{example.events.length}个事件，含初始态共{example.states.length}个快照（栈顶在右）。</p><table><thead><tr><th>事件</th><th>事件后状态</th></tr></thead><tbody>{example.states.map((s:any,i:number)=><tr key={i}><td>{i===0?'初始态':example.events[i-1]}</td><td>{JSON.stringify(s)}</td></tr>)}</tbody></table></>}<details><summary>查看示例解析（不是正式测验答案）</summary><p>{example.worked}</p><p>{example.rubric}</p></details></details>:<p>本任务未提供通用代码示例，仅以关联正文为准；不能假称存在原文图示。</p>}
 <p>{packet.deliverable}</p><p>{assessment.instruction}</p><p>生成时可用新题 {assessment.available_count} 道；本次领取 {assessment.question_count} 道，统计快照不代替领取时校验。</p>
 {!!packet.prerequisite_gate.skill_ids.length&&<p>先修门控：{packet.prerequisite_gate.skill_ids.join('、')}达到{packet.prerequisite_gate.required_probability*100}%；由有效测验证据解锁，不以阅读分钟替代。</p>}{packet.media_note&&<p>{packet.media_note}</p>}
 </section>
}
