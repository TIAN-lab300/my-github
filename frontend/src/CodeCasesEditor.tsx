import {useState} from 'react';

export function CodeCasesEditor({initialCases}:{initialCases?:{stdin:string;stdout:string}[]}){
  const [cases,setCases]=useState(initialCases?.length?initialCases:[{stdin:'',stdout:''}]);
  return <details><summary>代码任务测试用例</summary>
    <p>学生程序从标准输入读取数据，输出与预期逐字比较，忽略结尾空白。用例在发布后冻结。</p>
    <input type="hidden" name="code_cases" value={JSON.stringify(cases)}/>
    {cases.map((test,index)=><fieldset key={index}><legend>用例 {index+1}</legend>
      <label>标准输入<textarea value={test.stdin} maxLength={2000} onChange={event=>setCases(cases.map((item,i)=>i===index?{...item,stdin:event.target.value}:item))}/></label>
      <label>预期输出<textarea value={test.stdout} maxLength={2000} onChange={event=>setCases(cases.map((item,i)=>i===index?{...item,stdout:event.target.value}:item))}/></label>
      <button type="button" disabled={cases.length===1} onClick={()=>setCases(cases.filter((_,i)=>i!==index))}>删除用例</button>
    </fieldset>)}
    <button type="button" disabled={cases.length>=10} onClick={()=>setCases([...cases,{stdin:'',stdout:''}])}>增加用例</button>
  </details>;
}
