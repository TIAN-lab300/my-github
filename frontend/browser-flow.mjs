import {chromium} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
const root=path.resolve('..');
const credentials=fs.readFileSync(path.join(root,'backend/data/initial-accounts.txt'),'utf8');
const accounts=Object.fromEntries(credentials.split(/\r?\n/).map(line=>line.match(/^(\w+): (\S+)/)).filter(Boolean).map(m=>[m[1],m[2]]));
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
const errors=[];const steps=[];
async function login(name){
 const context=await browser.newContext({viewport:{width:1440,height:1000}});const page=await context.newPage();
 page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 await page.goto('http://127.0.0.1:8000');await page.getByLabel('账号',{exact:true}).fill(name);await page.getByLabel('密码',{exact:true}).fill(accounts[name]);await page.getByRole('button',{name:'登录',exact:true}).click();await page.getByRole('button',{name:'退出登录'}).waitFor();return {context,page};
}
try{
 const t=await login('teacher');
 await t.page.getByRole('link',{name:'任务管理'}).click();
 await t.page.getByLabel('任务标题').fill('浏览器集成验证 · 递归练习');
 await t.page.getByLabel('任务说明').fill('阅读课程讲义后选择正确递归边界。');
 const future=new Date(Date.now()+7*86400000).toISOString().slice(0,16);
 await t.page.getByLabel('截止时间').fill(future);
 await t.page.getByRole('button',{name:'保存任务草稿'}).click();
 await t.page.getByRole('button',{name:'发布任务',exact:true}).last().click();
 await t.page.getByRole('status').filter({hasText:'操作成功'}).waitFor();
 steps.push('教师通过页面创建并发布真实客观题任务');await t.context.close();
 const s=await login('student');
 await s.page.getByRole('link',{name:'任务与反馈'}).click();
 await s.page.getByRole('radio').first().check();
 await s.page.getByRole('button',{name:'提交并查看反馈'}).last().click();
 await s.page.getByRole('heading',{name:/已评分/}).waitFor();steps.push('学生通过页面提交并读取真实评分反馈');
 await s.page.getByRole('link',{name:'目标与诊断'}).click();
 await s.page.getByLabel('学习目标',{exact:true}).fill('Python函数与递归 · 浏览器集成验证');
 await s.page.getByLabel('截止日期').fill(future.slice(0,10));
 await s.page.getByRole('button',{name:'保存目标',exact:true}).click();
 await s.page.getByRole('button',{name:'开始/查看诊断'}).first().click();
 await s.page.getByRole('heading',{name:'目标诊断 · 6题'}).waitFor();
 for(const fieldset of await s.page.locator('fieldset.card').all())await fieldset.getByRole('radio').first().check();
 await s.page.getByRole('button',{name:'提交诊断',exact:true}).click();
 await s.page.getByRole('heading',{name:/已评分/}).waitFor();steps.push('目标创建、六题诊断与BKT证据保存');
 await s.page.getByRole('button',{name:'生成首次路径'}).first().click();
 await s.page.getByRole('button',{name:'查看生成路径'}).waitFor({timeout:15000});
 await s.page.getByRole('button',{name:'查看生成路径'}).click();
 await s.page.getByRole('button',{name:'接受此路径'}).click();
 await s.page.getByRole('heading',{name:'学习路径 · 活动中'}).waitFor();steps.push('LangGraph四节点生成、规则校验与路径接受');
 await s.page.screenshot({path:path.join(root,'docs/evidence/implementation/student-path.png'),fullPage:true});
 await s.context.close();
 const teacher=await login('teacher');await teacher.page.getByRole('link',{name:'班级进度'}).click();await teacher.page.getByText('班级任务完成率',{exact:true}).waitFor();await teacher.page.screenshot({path:path.join(root,'docs/evidence/implementation/teacher-after-submission.png'),fullPage:true});await teacher.context.close();steps.push('教师页面读取同一提交后的班级进度');
}finally{await browser.close();fs.writeFileSync(path.join(root,'docs/evidence/implementation/browser-flow.json'),JSON.stringify({steps,errors,checked_at:new Date().toISOString()},null,2));}
if(errors.length)throw Error(errors.join('\n'));
console.log(steps.join('\n'));
