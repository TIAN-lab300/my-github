import {chromium} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const root=path.resolve('..');
const credentials=fs.readFileSync(path.join(root,'backend/data/initial-accounts.txt'),'utf8');
const accounts=Object.fromEntries(credentials.split(/\r?\n/).map(line=>line.match(/^(\w+): (\S+)/)).filter(Boolean).map(m=>[m[1],m[2]]));
const output=path.join(root,'docs/evidence/implementation');
fs.mkdirSync(output,{recursive:true});
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
const errors=[];
try{
 for(const name of ['student','teacher','admin']){
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  const page=await context.newPage();
  page.on('pageerror',error=>errors.push(name+': '+error.message));
  await page.goto('http://127.0.0.1:8000');
  await page.getByLabel('账号',{exact:true}).fill(name);
  await page.getByLabel('密码',{exact:true}).fill(accounts[name]);
  await page.getByRole('button',{name:'登录',exact:true}).click();
  await page.getByRole('heading',{name:'首次登录，请设置自己的密码'}).waitFor();
  const own=crypto.randomBytes(12).toString('base64url');
  await page.getByLabel('当前密码').fill(accounts[name]);
  await page.getByLabel('新密码（10至128位）').fill(own);
  await page.getByLabel('确认新密码').fill(own);
  await page.getByRole('button',{name:'修改并重新登录'}).click();
  await page.getByRole('heading',{name:'欢迎回来'}).waitFor();
  accounts[name]=own;
  await page.getByLabel('账号',{exact:true}).fill(name);
  await page.getByLabel('密码',{exact:true}).fill(own);
  await page.getByRole('button',{name:'登录',exact:true}).click();
  await page.getByRole('button',{name:'退出登录'}).waitFor();
  if(name==='student'){
   await page.getByRole('link',{name:'课程知识库'}).click();
   await page.getByRole('button',{name:'查看资料'}).first().click();
   await page.getByLabel('本次实际学习分钟').fill('18');
   await page.getByRole('button',{name:'保存学习记录（重复保存更新同一记录）'}).click();
   await page.getByRole('status').filter({hasText:'操作成功'}).waitFor();
   await page.getByRole('link',{name:'学习概览'}).click();
   await page.getByText('18 分钟',{exact:true}).waitFor();
  }
  if(name==='teacher'){
   await page.getByRole('link',{name:'班级进度'}).click();
   await page.getByText('班级任务完成率',{exact:true}).waitFor();
  }
  if(name==='admin'){
   await page.getByRole('heading',{name:'创建教师/学生账号'}).waitFor();
  }
  await page.screenshot({path:path.join(output,`${name}-desktop.png`),fullPage:true});
  if(name==='student'){
   await page.setViewportSize({width:390,height:844});
   await page.screenshot({path:path.join(output,'student-mobile.png'),fullPage:true});
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
   if(overflow)errors.push('student: mobile horizontal overflow');
  }
  await context.close();
 }
}finally{
 await browser.close();
 fs.writeFileSync(path.join(root,'backend/data/initial-accounts.txt'),Object.entries(accounts).map(([name,pw])=>`${name}: ${pw} （本机验证账号；已验证角色已改密）`).join('\n'),'utf8');
}
fs.writeFileSync(path.join(output,'browser-smoke.json'),JSON.stringify({roles:['student','teacher','admin'],screenshots:4,errors,checked_at:new Date().toISOString()},null,2));
if(errors.length)throw Error(errors.join('\n'));
console.log('Three role login/password flows, persisted study, teacher projection and four screenshots passed.');
