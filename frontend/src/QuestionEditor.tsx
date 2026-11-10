type Question = {id:string;skill:string;prompt:string;kind:string;options:string[];answer:string;explanation:string};
export function QuestionEditor({questions,onChange}:{questions:Question[];onChange:(questions:Question[])=>void}){
 function update(index:number,patch:Partial<Question>){
  onChange(questions.map((q,i)=>i===index?{...q,...patch}:q));
 }
 return <section><h3>任务题目</h3>{questions.map((q,index)=><fieldset key={index} aria-label={'题目 '+(index+1)}>
  <legend>第{index+1}题</legend>
  <label>题目编号<input aria-label="题目编号" value={q.id} onChange={e=>update(index,{id:e.target.value})} required/></label>
  <label>知识点<input aria-label="知识点" value={q.skill} onChange={e=>update(index,{skill:e.target.value})} required/></label>
  <label>题干<textarea aria-label="题干" value={q.prompt} onChange={e=>update(index,{prompt:e.target.value})} required/></label>
  <label>题型<select aria-label="题型" value={q.kind||'single'} onChange={e=>update(index,{kind:e.target.value,options:['fill','subjective'].includes(e.target.value)?[]:q.options})}>
   <option value="single">单选</option><option value="boolean">判断</option><option value="fill">填空</option><option value="multi">多选</option><option value="subjective">主观复核</option>
  </select></label>
  {['single','boolean','multi'].includes(q.kind||'single')&&<label>选项（每行一个）<textarea aria-label="选项（每行一个）" value={(q.options||[]).join('\n')} onChange={e=>update(index,{options:e.target.value.split('\n')})}/></label>}
  {q.kind!=='subjective'&&<label>正确答案<input aria-label="正确答案" value={q.answer||''} onChange={e=>update(index,{answer:e.target.value})} required/><small>选择题填写从0开始的选项序号，多选用逗号分隔；填空填写答案文本。</small></label>}
  <label>解析<textarea aria-label="解析" value={q.explanation||''} onChange={e=>update(index,{explanation:e.target.value})}/></label>
  <button type="button" onClick={()=>onChange(questions.filter((_,i)=>i!==index))}>删除此题</button>
 </fieldset>)}
 <button type="button" onClick={()=>onChange([...questions,{id:'q'+(questions.length+1),skill:'functions',prompt:'',kind:'single',options:['',''],answer:'0',explanation:''}])}>添加题目</button>
 </section>
}
