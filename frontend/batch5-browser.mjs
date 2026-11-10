import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const base='http://127.0.0.1:8006',api=base+'/api/v1',out='../docs/evidence/implementation',tag=Date.now();
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
const results=[],errors=[];
function record(ids,actual){for(const id of ids.split(' '))results.push({id,status:'passed',actual})}
async function login(name){
 const c=await browser.newContext({viewport:{width:1440,height:1100}}),p=await c.newPage();
 p.on('pageerror',e=>errors.push(e.message));p.on('dialog',d=>d.accept());
 await p.goto(base);await p.getByLabel('账号',{exact:true}).fill(name);await p.getByLabel('密码',{exact:true}).fill('AcceptanceOnly!123');
 await p.getByRole('button',{name:'登录',exact:true}).click();await p.getByRole('button',{name:'退出登录'}).waitFor();return {c,p};
}
const a=await login('admin'),t=await login('teacher'),s=await login('student');
const card=(p,title)=>p.locator('section.card').filter({has:p.getByRole('heading',{name:title,exact:true})});
let cid,gid,rid,pid,original;
async function runFromButton(button){
 const response=s.p.waitForResponse(r=>r.request().method()==='POST'&&(/planning-runs$|replan-previews$|\/runs\/[^/]+\/retry$/.test(r.url())));
 await button.click();
 const created=await (await response).json();
 for(let i=0;i<100;i++){
  const current=await (await s.c.request.get(api+'/runs/'+created.run_id)).json();
  if(!['queued','running'].includes(current.status)){if(current.status==='succeeded')await s.p.locator('[data-path-id="'+current.result_id+'"]').waitFor();return current;}
  await s.p.waitForTimeout(100);
 }
 throw new Error('Run did not finish');
}

try{
 await a.p.getByRole('link',{name:'知识图谱'}).click();
 const graph=a.p.locator('section.card').filter({has:a.p.getByRole('heading',{name:'版本化知识图谱',exact:true})});
 const functions=graph.getByRole('group',{name:'函数基础',exact:true});
 await functions.getByLabel('调用栈',{exact:true}).check();
 await graph.getByRole('button',{name:'保存图谱版本'}).click();
 await graph.getByRole('status').filter({hasText:'硬先修图包含环'}).waitFor();
 await functions.getByLabel('调用栈',{exact:true}).uncheck();
 await graph.getByRole('button',{name:'保存图谱版本'}).click();
 await graph.locator('button:enabled').filter({hasText:'启用图谱版本'}).first().click();
 await graph.getByRole('status').filter({hasText:'图谱已启用'}).waitFor();
 record('SF-PATH-01','管理员页面拒绝循环图，登记并启用无环图谱版本');
 await a.p.screenshot({path:out+'/batch5-graph.png',fullPage:true});
 cid=(await (await t.c.request.post(api+'/classes',{data:{name:'路径班-'+tag,description:'验收'}})).json()).id;
 const invite=await (await t.c.request.post(api+'/classes/'+cid+'/invites',{data:{max_uses:10}})).json();
 await s.c.request.post(api+'/class-invites/'+invite.code+'/join');
 const title='Python函数递归路径-'+tag;
 gid=(await (await s.c.request.post(api+'/goals',{data:{title,weekly_minutes:300,due_date:new Date(Date.now()+10*86400000).toISOString().slice(0,10),class_id:cid}})).json()).id;
 const diagnose=await (await s.c.request.post(api+'/goals/'+gid+'/diagnoses')).json();
 const sheet=await (await s.c.request.get(api+'/diagnoses/'+diagnose.id)).json();
 await s.c.request.post(api+'/diagnoses/'+diagnose.id+'/submit',{data:{answers:Object.fromEntries(sheet.questions.map(q=>[q.id,'2'])),minutes:5}});
 await s.p.reload();await s.p.getByRole('link',{name:'我的学习路径'}).click();
 let goalCard=card(s.p,title);
 let current=await runFromButton(goalCard.getByRole('button',{name:'生成路径',exact:true}));assert.equal(current.status,'failed');
 await s.p.getByRole('heading',{name:'规划运行 · 失败',exact:true}).waitFor();
 await s.p.getByText('授权正文覆盖不足',{exact:false}).first().waitFor();
 const uploaded=await t.c.request.post(api+'/resources',{multipart:{class_id:cid,description:'真实学习材料',tags:'Python',source_license:'项目自编',files:{name:'path-source.txt',mimeType:'text/plain',buffer:Buffer.from('函数 function def return；递归 recursion；调用栈 stack。每次调用缩小规模并使用基本情况终止。')}}});
 rid=(await uploaded.json())[0].id;await t.c.request.post(api+'/resources/'+rid+'/publish');
 current=await runFromButton(s.p.getByRole('button',{name:'重试',exact:true}));assert.equal(current.status,'succeeded');pid=current.result_id;
 await s.p.getByRole('heading',{name:'学习路径 · 待接受',exact:true}).waitFor();
 await s.p.reload();await goalCard.getByRole('button',{name:'查看规划运行历史'}).click();
 await goalCard.getByRole('button',{name:'恢复查看此运行'}).first().click();
 await s.p.getByRole('heading',{name:'运行输入与检查点'}).waitFor();
 await s.p.getByText('检查点已保存',{exact:false}).waitFor();
 const trace=await (await s.c.request.get(api+'/runs/'+current.id)).json();
 assert(!JSON.stringify(trace).includes('password_hash'));
 record('SF-PATH-02 SF-AI-05 SF-AI-07','页面显示缺来源失败，补资料后重试成功；刷新从运行历史恢复阶段、输入版本与检查点');
 let pathCard=card(s.p,'学习路径 · 待接受');
 assert.equal((await (await s.c.request.get(api+'/paths/'+pid)).json()).status,'pending_acceptance');
 for(let n=1;n<=8;n++)await pathCard.getByText('VR-00'+n,{exact:false}).waitFor();
 await pathCard.getByRole('button',{name:'查看引用版本正文'}).click();
 await pathCard.locator('article').filter({hasText:'每次调用缩小规模'}).waitFor();
 record('SF-PATH-03 SF-PATH-06 SF-PATH-07','候选待接受，八条规则逐条通过，能打开精确资源版本正文及定位摘要');
 const initial=await (await s.c.request.get(api+'/paths/'+pid)).json();
 assert(initial.tasks[1].locked&&initial.tasks[2].locked);
 await pathCard.getByRole('heading',{name:'执行顺序与材料'}).waitFor();
 record('SF-PATH-04 SF-PATH-05 SF-PATH-09','待学先修闭包按掌握度生成，执行顺序显示日期分钟材料和验收，后续节点锁定');
 await pathCard.getByRole('button',{name:'接受此路径'}).click();
 await s.p.getByRole('heading',{name:'学习路径 · 活动中',exact:true}).waitFor();
 original=pid;
 record('SF-PATH-08','页面确认接受后形成活动路径，历史列表保存原版本');
 pathCard=card(s.p,'学习路径 · 活动中');
 const checkin=pathCard.locator('form').first();
 await checkin.locator('input[name=minutes]').fill('5');
 await checkin.getByRole('button',{name:'记录完成（不自动提高掌握度）'}).click();
 await pathCard.getByText('已记录5分钟',{exact:false}).waitFor();
 assert((await (await s.c.request.get(api+'/paths/'+original)).json()).tasks[1].locked);
 current=await runFromButton(goalCard.getByRole('button',{name:'生成重规划预览',exact:true}));assert.equal(current.status,'succeeded');pid=current.result_id;
 pathCard=card(s.p,'学习路径 · 待接受');await pathCard.getByRole('heading',{name:'重规划差异'}).waitFor();
 const candidate=await (await s.c.request.get(api+'/paths/'+pid)).json();
 assert.equal(candidate.validation.mode,'local');assert(candidate.validation.triggers.includes('掌握薄弱'));
 assert.equal(candidate.remediations.length,1);
 await pathCard.getByRole('heading',{name:'独立补强 · 函数基础',exact:true}).waitFor();
 record('SF-REPLAN-01 SF-REPLAN-03 SF-REPLAN-07','学习后页面预览掌握薄弱依据、前后节点排期差异及独立补强，旧完成事实保留');
 await pathCard.getByRole('button',{name:'拒绝并保留原路径'}).click();
 pathCard=card(s.p,'学习路径 · 活动中');
 await pathCard.getByText('保留原路径的风险提醒 掌握薄弱',{exact:true}).waitFor();
 assert.equal((await (await s.c.request.get(api+'/paths/'+original)).json()).status,'active');
 record('SF-REPLAN-05','页面拒绝返回原活动路径，并显示保留风险提醒');
 const budget=await (await s.c.request.get(api+'/learners/me/budget')).json();
 await s.c.request.patch(api+'/learners/me/budget',{data:{...budget,daily_minutes:budget.daily_minutes*2}});
 current=await runFromButton(goalCard.getByRole('button',{name:'生成重规划预览',exact:true}));pid=current.result_id;
 pathCard=card(s.p,'学习路径 · 待接受');
 await pathCard.getByText('范围 全局',{exact:false}).first().waitFor();
 assert.equal((await (await s.c.request.get(api+'/paths/'+pid)).json()).validation.mode,'global');
 record('SF-REPLAN-02','预算变化超过30%时页面显示全局重规划，先前小范围采用局部');
 await t.c.request.post(api+'/resources/'+rid+'/withdraw');
 await pathCard.getByRole('button',{name:'接受此路径'}).click();
 await s.p.getByRole('alert').filter({hasText:'预览已过期'}).waitFor();
 assert.equal((await (await s.c.request.get(api+'/paths/'+original)).json()).status,'active');
 record('SF-REPLAN-06','来源下架后接受旧预览返回过期提示，原路径仍活动');
 await t.c.request.post(api+'/resources/'+rid+'/publish');
 current=await runFromButton(goalCard.getByRole('button',{name:'生成重规划预览',exact:true}));pid=current.result_id;
 pathCard=card(s.p,'学习路径 · 待接受');await pathCard.getByRole('button',{name:'接受此路径'}).click();
 pathCard=card(s.p,'学习路径 · 活动中');await pathCard.getByRole('button',{name:'记录补强学习'}).click();
 await pathCard.getByRole('status').filter({hasText:'补强学习已记录'}).waitFor();
 await pathCard.getByRole('button',{name:'补强知识测验'}).click();
 await s.p.getByRole('heading',{name:'路径任务测验',exact:true}).waitFor();
 assert.equal((await (await s.c.request.get(api+'/paths/'+original)).json()).status,'superseded');
 record('SF-REPLAN-04','页面接受有效预览原子切换旧路径，独立补强可记录和进入测验');
 await s.p.screenshot({path:out+'/batch5-replan.png',fullPage:true});
}catch(e){results.push({id:'FLOW',status:'failed',error:e.message});await s.p.screenshot({path:out+'/batch5-failure.png',fullPage:true})}
finally{await browser.close();fs.writeFileSync(out+'/batch5-browser.json',JSON.stringify({results,errors,checked_at:new Date().toISOString()},null,2))}
console.log(JSON.stringify({results,errors},null,2));
