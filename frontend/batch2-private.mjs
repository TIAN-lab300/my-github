import {chromium} from '@playwright/test';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
const context=await browser.newContext(),page=await context.newPage();
const base='http://127.0.0.1:8003',results=[];
try{
 await page.goto(base);
 await page.getByLabel('账号',{exact:true}).fill('student');
 await page.getByLabel('密码',{exact:true}).fill('AcceptanceOnly!123');
 await page.getByRole('button',{name:'登录',exact:true}).click();
 await page.getByRole('button',{name:'退出登录'}).waitFor();
 await page.getByRole('link',{name:'课程知识库'}).click();
 await page.getByRole('button',{name:'上传私有资料'}).click();
 const name='private-'+Date.now()+'.txt';
 await page.getByLabel('资料说明',{exact:true}).fill('本人资料');
 await page.locator('input[name=tags]').fill('private');
 await page.getByLabel('来源及使用权限',{exact:true}).fill('个人原创');
 await page.getByLabel('选择文件',{exact:true}).setInputFiles({name,mimeType:'text/plain',buffer:Buffer.from('Python函数 function def return 递归 recursion 调用栈 stack')});
 const response=page.waitForResponse(r=>r.url().endsWith('/resources')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'保存资料草稿'}).click();
 const rid=(await (await response).json())[0].id;
 await page.getByRole('heading',{name,exact:true}).waitFor();
 const card=page.locator('section.card').filter({has:page.getByRole('heading',{name,exact:true})});
 await card.getByRole('button',{name:'查看资料'}).click();
 await page.locator('article').filter({hasText:'Python函数'}).waitFor();
 const detail=await (await context.request.get(base+'/api/v1/resources/'+rid)).json();
 assert.equal(detail.scope,'private');assert.equal(detail.cloud_allowed,false);
 const other=await browser.newContext();
 await other.request.post(base+'/api/v1/auth/login',{data:{username:'teacher',password:'AcceptanceOnly!123'}});
 assert.equal((await other.request.get(base+'/api/v1/resources/'+rid)).status(),404);
 assert.equal((await other.request.get(base+'/api/v1/resources/'+rid+'/download')).status(),404);
 await other.close();
 results.push({id:'SF-RESOURCE-12',status:'passed',actual:'学生页面上传私有资料并阅读，默认云端不允许，教师详情与下载均404'});
 await page.screenshot({path:'../docs/evidence/implementation/batch2-private.png',fullPage:true});
}catch(e){results.push({id:'FLOW',status:'failed',error:e.message})}
finally{await browser.close();fs.writeFileSync('../docs/evidence/implementation/batch2-private.json',JSON.stringify({results,checked_at:new Date().toISOString()},null,2))}
console.log(JSON.stringify(results,null,2));
