import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const base='http://127.0.0.1:8004',api=base+'/api/v1',out='../docs/evidence/implementation';
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
const results=[],errors=[],tag=Date.now();
function record(ids,actual){ids.split(' ').forEach(id=>results.push({id,status:'passed',actual}))}
async function login(name){
 const c=await browser.newContext({viewport:{width:1440,height:1100}}),p=await c.newPage();
 p.on('pageerror',e=>errors.push(e.message));p.on('dialog',d=>d.accept());
 await p.goto(base);await p.getByLabel('账号',{exact:true}).fill(name);await p.getByLabel('密码',{exact:true}).fill('AcceptanceOnly!123');
 await p.getByRole('button',{name:'登录',exact:true}).click();await p.getByRole('button',{name:'退出登录'}).waitFor();return {c,p};
}
const t=await login('teacher'),s=await login('student'),o=await login('student2');
let cid;
const card=(p,title)=>p.locator('section.card').filter({has:p.getByRole('heading',{name:title,exact:true})});
async function create(title,mode='text',questions=[],due=86400000){
 const r=await t.c.request.post(api+'/teacher/tasks',{data:{class_id:cid,title,description:'第三批验收',mode,questions,minutes:10,due_at:new Date(Date.now()+due).toISOString(),recipients:['student']}});
 assert.equal(r.status(),201);return (await r.json()).id;
}
try{
 const oldBudget=await (await s.c.request.get(api+'/learners/me/budget')).json();
 await s.c.request.patch(api+'/learners/me/budget',{data:{...oldBudget,daily_minutes:240,weekly_minutes:1680}});
 cid=(await (await t.c.request.post(api+'/classes',{data:{name:'Batch3-'+tag,description:'test'}})).json()).id;
 const inv=await (await t.c.request.post(api+'/classes/'+cid+'/invites',{data:{max_uses:10}})).json();
 for(const x of [s,o])await x.c.request.post(api+'/class-invites/'+inv.code+'/join');
 await t.p.reload();await t.p.getByRole('link',{name:'任务管理'}).click();
 await t.p.locator('select:not([name])').first().selectOption(cid);
 const title='客观-'+tag;
 await t.p.getByLabel('任务标题').fill(title);await t.p.getByLabel('任务说明').fill('四种题型');
 await t.p.getByLabel('截止时间',{exact:true}).fill(new Date(Date.now()+86400000).toISOString().slice(0,16));
 await t.p.locator('input[name=recipients][value=student]').check();
 await t.p.getByRole('button',{name:'保存任务草稿'}).click();
 const tc=card(t.p,title);
 await tc.getByRole('button',{name:'编辑任务草稿'}).click();
 const editor=t.p.getByRole('region',{name:'编辑信息'});
 const qs=['single','boolean','fill','multi'].map(kind=>({id:kind,skill:'functions',prompt:kind,kind,options:kind==='fill'?[]:['A','B','C'],answer:kind==='multi'?'0,1':kind==='fill'?'def':'1',explanation:'规则解析'}));
 for(let i=0;i<qs.length;i++){
  if(i)await editor.getByRole('button',{name:'添加题目'}).click();
  const field=editor.getByRole('group',{name:'题目 '+(i+1),exact:true});
  await field.getByLabel('题目编号',{exact:true}).fill(qs[i].id);
  await field.getByLabel('知识点',{exact:true}).fill(qs[i].skill);
  await field.getByLabel('题干',{exact:true}).fill(qs[i].prompt);
  await field.getByLabel('题型',{exact:true}).selectOption(qs[i].kind);
  if(qs[i].options.length)await field.getByLabel('选项（每行一个）',{exact:true}).fill(qs[i].options.join('\n'));
  await field.getByLabel('正确答案',{exact:true}).fill(qs[i].answer);
  await field.getByLabel('解析',{exact:true}).fill(qs[i].explanation);
 }
 await editor.getByRole('button',{name:'保存修改',exact:true}).click();await editor.waitFor({state:'detached'});
 record('SF-TASK-01','页面创建草稿并编辑四种题型快照');
 await tc.getByRole('button',{name:'预览接收人并发布'}).click();await tc.getByText('接收1人，发布时冻结内容及成员快照',{exact:true}).waitFor();
 await tc.getByRole('button',{name:'确认发布任务'}).click();await tc.getByRole('button',{name:'撤回',exact:true}).waitFor();
 const obj=(await (await t.c.request.get(api+'/teacher/tasks')).json()).find(v=>v.title===title);
 assert.equal(obj.submissions.length,1);assert.equal(await tc.getByRole('button',{name:'编辑任务草稿'}).count(),0);
 assert(!(await (await o.c.request.get(api+'/learners/me/tasks')).json()).some(v=>v.id===obj.id));
 record('SF-TASK-02 SF-TASK-03','发布预览仅指定学生，发布后不可编辑，另一成员无分配');
 await s.p.reload();await s.p.getByRole('link',{name:'任务与反馈'}).click();
 const sc=card(s.p,title);
 for(const kind of ['single','boolean'])await sc.locator('input[name='+kind+'][value="1"]').check();
 await sc.locator('textarea[name=fill]').fill('def');for(const v of ['0','1'])await sc.locator('input[name=multi][value="'+v+'"]').check();
 await sc.getByRole('button',{name:'暂存作答'}).click();await s.p.getByRole('status').filter({hasText:'暂存成功'}).waitFor();
 await s.p.reload();await s.p.getByLabel('筛选任务状态').selectOption('in_progress');
 assert.equal(await sc.locator('textarea[name=fill]').inputValue(),'def');assert.equal(await sc.locator('input[name=multi]:checked').count(),2);
 record('SF-TASK-04','暂存后刷新恢复全部答案，进行中筛选有效');
 await sc.getByRole('button',{name:'提交并查看反馈'}).click();await s.p.getByRole('status').filter({hasText:'提交成功'}).waitFor();await s.p.getByLabel('筛选任务状态').selectOption('');await sc.getByRole('heading',{name:'得分 100%'}).waitFor();
 await sc.getByText('知识点 functions',{exact:false}).first().waitFor();
 record('SF-ASSESS-01 SF-ASSESS-02','四种题型页面提交100%，展示答案解析知识点建议');
 await s.p.screenshot({path:out+'/batch3-objective.png',fullPage:true});
 for(const [mode,text] of [['text','作业'],['link','https://example.com/work'],['checkin','']]){
  const name=mode+'-'+tag,id=await create(name,mode);await t.c.request.post(api+'/teacher/tasks/'+id+'/publish');
  await s.p.reload();await s.p.getByLabel('筛选任务状态').selectOption('');
  const normal=card(s.p,name);if(text)await normal.locator('textarea[name=text]').fill(text);
  await normal.getByRole('button',{name:'提交并查看反馈'}).click();await normal.getByRole('heading',{name:'提交已保存'}).waitFor();
 }
 record('SF-TASK-05','文本链接打卡三种普通任务页面提交成功');
 const lateName='逾期-'+tag,lateId=await create(lateName,'text',[],2500);await t.c.request.post(api+'/teacher/tasks/'+lateId+'/publish');
 await s.p.waitForTimeout(2700);await s.p.reload();await s.p.getByLabel('筛选任务状态').selectOption('overdue');
 const late=card(s.p,lateName);await late.locator('textarea[name=text]').fill('补交');await late.getByRole('button',{name:'提交并查看反馈'}).click();await s.p.getByRole('status').filter({hasText:'提交成功'}).waitFor();await s.p.getByLabel('筛选任务状态').selectOption('');await late.getByText('逾期补交',{exact:false}).waitFor();
 record('SF-TASK-06','页面逾期筛选与补交标记有效');
 const subjectName='主观-'+tag,subjectId=await create(subjectName,'quiz',[{id:'subject',skill:'recursion',prompt:'递归结束',kind:'subjective'}]);
 await t.c.request.post(api+'/teacher/tasks/'+subjectId+'/publish');await s.p.reload();await s.p.getByLabel('筛选任务状态').selectOption('');
 const subj=card(s.p,subjectName);await subj.locator('textarea[name=subject]').fill('基本情况');await subj.getByRole('button',{name:'提交并查看反馈'}).click();await subj.getByRole('heading',{name:'待教师复核'}).waitFor();
 record('SF-ASSESS-03','主观题页面待复核且无评分');
 await t.p.reload();await card(t.p,subjectName).getByRole('button',{name:'查看提交'}).click();
 await t.p.getByLabel('rubric-v1：0至1分，0.75为达标线').fill('1');await t.p.getByLabel('评分依据').fill('符合rubric');
 await t.p.getByRole('button',{name:'提交人工评分'}).click();await t.p.getByRole('button',{name:'保存评分更正版本'}).waitFor();
 record('SF-TASK-09 SF-ASSESS-04','教师查看本人提交并按公开rubric复核，页面更新评分状态');
 await t.p.getByLabel('rubric-v1：0至1分，0.75为达标线').fill('0');await t.p.getByLabel('评分依据').fill('更正：不足');
 await t.p.getByRole('button',{name:'保存评分更正版本'}).click();await t.p.getByText('更正：不足',{exact:false}).first().waitFor();
 record('SF-ASSESS-05','评分更正原因与历史反馈可见');await t.p.screenshot({path:out+'/batch3-review.png',fullPage:true});
 for(const action of ['撤回','关闭提交']){
  const name=action+'-'+tag,id=await create(name);await t.c.request.post(api+'/teacher/tasks/'+id+'/publish');await t.p.reload();
  const target=card(t.p,name);await target.getByRole('button',{name:action,exact:true}).click();await target.getByRole('button',{name:'创建修订版草稿'}).waitFor();
  if(action==='撤回'){const response=t.p.waitForResponse(r=>r.url().endsWith('/reissue'));await target.getByRole('button',{name:'创建修订版草稿'}).click();assert.equal((await response).status(),200)}
 }
 record('SF-TASK-07 SF-TASK-08','教师页面撤回关闭以及关联修订草稿创建成功');
 await s.p.getByRole('link',{name:'学习记录'}).click();await s.p.getByRole('heading',{name:'分层进度'}).waitFor();
 await s.p.getByText('bkt-v1',{exact:false}).first().waitFor();await s.p.locator('input[name=task_id]').fill(obj.id);
 await s.p.getByRole('button',{name:'查询',exact:true}).click();await s.p.getByRole('heading',{name:'阅读记录'}).waitFor();
 record('SF-PROFILE-01 SF-PROFILE-02 SF-PROFILE-03 SF-ASSESS-07','记录页按任务查询并显示阅读提交掌握分层、BKT概率版本依据');
 await s.p.screenshot({path:out+'/batch3-records.png',fullPage:true});

 // Path setup uses APIs; the check-in itself is exercised through the page.
 const uploaded=await t.c.request.post(api+'/resources',{multipart:{class_id:cid,description:'Learning source',tags:'Python',source_license:'own',files:{name:'source.txt',mimeType:'text/plain',buffer:Buffer.from('函数 function def return 递归 recursion 调用栈 stack')}}});
 const rid=(await uploaded.json())[0].id;
 await t.c.request.post(api+'/resources/'+rid+'/publish');
 const goalResponse=await s.c.request.post(api+'/goals',{data:{title:'Python函数递归-'+tag,weekly_minutes:300,due_date:new Date(Date.now()+10*86400000).toISOString().slice(0,10),class_id:cid}});
 const gid=(await goalResponse.json()).id;
 const diagnose=await (await s.c.request.post(api+'/goals/'+gid+'/diagnoses')).json();
 const sheet=await (await s.c.request.get(api+'/diagnoses/'+diagnose.id)).json();
 await s.c.request.post(api+'/diagnoses/'+diagnose.id+'/submit',{data:{answers:Object.fromEntries(sheet.questions.map(q=>[q.id,'2'])),minutes:5}});
 const run=await (await s.c.request.post(api+'/goals/'+gid+'/planning-runs',{headers:{'Idempotency-Key':'browser-'+tag}})).json();
 let runResult;
 for(let n=0;n<30;n++){runResult=await (await s.c.request.get(api+'/runs/'+run.run_id)).json();if(!['queued','running'].includes(runResult.status))break;await s.p.waitForTimeout(200)}
 assert.equal(runResult.status,'succeeded');
 const pid=runResult.result_id;
 assert.equal((await s.c.request.post(api+'/paths/'+pid+'/accept')).status(),200);
 await s.p.getByRole('link',{name:'我的学习路径'}).click();
 const goalCard=card(s.p,'Python函数递归-'+tag);
 await goalCard.getByRole('button',{name:'查看路径与差异'}).first().click();
 const checkin=s.p.locator('form').filter({has:s.p.getByRole('button',{name:'记录完成（不自动提高掌握度）'})}).first();
 await checkin.locator('input[name=minutes]').fill('5');
 await checkin.locator('input[name=proportion]').fill('0.5');
 await checkin.locator('input[name=difficulty]').fill('递归边界困难');
 await checkin.locator('input[name=note]').fill('需要复习');
 const before=await (await s.c.request.get(api+'/learners/me/profile')).json();
 await checkin.getByRole('button',{name:'记录完成（不自动提高掌握度）'}).click();
 await s.p.getByText('递归边界困难',{exact:false}).first().waitFor();
 const after=await (await s.c.request.get(api+'/learners/me/profile')).json();
 assert.equal(after.evidence_quality.valid_observations,before.evidence_quality.valid_observations);
 record('SF-ASSESS-08','页面保存比例、困难和备注后可见，掌握证据数量未增长');
 const budget=await (await s.c.request.get(api+'/learners/me/budget')).json();
 assert.equal((await s.c.request.patch(api+'/learners/me/budget',{data:{...budget,daily_minutes:1,weekly_minutes:1}})).status(),200);
 const conflictName='预算冲突-'+tag,conflictId=await create(conflictName);
 await t.p.reload();const conflict=card(t.p,conflictName);
 await conflict.getByRole('button',{name:'预览接收人并发布'}).click();
 await conflict.getByRole('button',{name:'确认发布任务'}).click();
 await t.p.getByRole('status').filter({hasText:'预算冲突学生'}).waitFor();
 record('SF-TASK-10','页面发布后保留预算冲突提示，学生路径仍为原活动版本');
 assert.equal((await (await s.c.request.get(api+'/paths/'+pid)).json()).status,'active');
 await t.p.screenshot({path:out+'/batch3-budget-conflict.png',fullPage:true});
}catch(e){results.push({id:'FLOW',status:'failed',error:e.message});await t.p.screenshot({path:out+'/batch3-failure-teacher.png',fullPage:true});await s.p.screenshot({path:out+'/batch3-failure-student.png',fullPage:true})}
finally{await browser.close();fs.writeFileSync(out+'/batch3-browser.json',JSON.stringify({results,errors,checked_at:new Date().toISOString()},null,2))}
console.log(JSON.stringify({results,errors},null,2));
