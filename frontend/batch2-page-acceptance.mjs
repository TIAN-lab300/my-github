import {chromium} from '@playwright/test';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const base='http://127.0.0.1:8003';
const out='../docs/evidence/implementation';
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
const results=[];
async function login(name){
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 const page=await context.newPage();
 await page.goto(base);
 await page.getByLabel('账号',{exact:true}).fill(name);
 await page.getByLabel('密码',{exact:true}).fill('AcceptanceOnly!123');
 await page.getByRole('button',{name:'登录',exact:true}).click();
 await page.getByRole('button',{name:'退出登录'}).waitFor();
 return {page,context};
}
const t=await login('teacher'),s=await login('student');
t.page.on('dialog',d=>d.accept());
s.page.on('dialog',d=>d.accept());
async function check(id,fn){
 try{const observation=await fn();results.push({id,status:'observed',observation});}
 catch(e){results.push({id,status:'failed',error:e.message});}
}
try{
 const response=await t.context.request.post(base+'/api/v1/classes',{data:{name:'页面验收班-'+Date.now(),description:'独立验收'}});
 assert.equal(response.status(),201);
 const cid=(await response.json()).id;
 const invite=await t.context.request.post(base+'/api/v1/classes/'+cid+'/invites',{data:{max_uses:10}});
 await s.context.request.post(base+'/api/v1/class-invites/'+(await invite.json()).code+'/join');
 await t.page.reload();
 await t.page.getByRole('heading',{name:/页面验收班/}).waitFor();
 await check('SF-CLASS-03',async()=>{
  await t.page.locator('input[name=hours]').fill('12');
  await t.page.locator('input[name=uses]').fill('2');
  await t.page.getByRole('button',{name:'生成自定义邀请码'}).click();
  await t.page.getByRole('button',{name:'复制邀请码'}).waitFor();
  return '自定义有效期与次数可填写，生成成功后显示复制入口；剪贴板内容待验证';
 });
 await check('SF-CLASS-07',async()=>{await t.page.getByRole('button',{name:'移除',exact:true}).waitFor();return '教师成员列表显示移除入口，实际移除及退班后续验证';});
 await check('SF-CLASS-08',async()=>{await t.page.getByRole('button',{name:'归档班级',exact:true}).waitFor();return '归档入口可见，归档后只读待独立操作验证';});
 await t.page.getByRole('link',{name:'课程知识库'}).click();
 await t.page.getByRole('button',{name:'应用筛选'}).waitFor();
 await check('SF-RESOURCE-01',async()=>{
  await t.page.locator('select[name=kind]').selectOption('text');
  const req=t.page.waitForResponse(r=>r.url().includes('/resources?')&&r.url().includes('kind=text'));
  await t.page.getByRole('button',{name:'应用筛选'}).click();
  assert.equal((await req).status(),200);
  return '页面组合筛选触发kind=text服务端查询并返回200';
 });
 await t.page.getByRole('button',{name:'上传资料',exact:true}).click();
 await check('SF-RESOURCE-02',async()=>{
  for(const label of ['资料说明','标签','来源及使用权限','选择文件'])await t.page.getByLabel(label,{exact:true}).last().waitFor();
  await t.page.getByText('允许将必要正文发送云端').waitFor();
  return '上传信息与云端授权字段可见';
 });
 await t.page.getByLabel('资料说明',{exact:true}).fill('页面资料');
 await t.page.locator('input[name=tags]').fill('test');
 await t.page.getByLabel('来源及使用权限',{exact:true}).fill('自有');
 await t.page.getByLabel('选择文件',{exact:true}).setInputFiles([
  {name:'page-notes.txt',mimeType:'text/plain',buffer:Buffer.from('函数 recursion stack <script>window.injected=true</script>')},
  {name:'fake.mp4',mimeType:'video/mp4',buffer:Buffer.from('invalid')}
 ]);
 await check('SF-RESOURCE-03',async()=>{
  await t.page.getByRole('button',{name:'保存资料草稿'}).click();
  await t.page.getByRole('heading',{name:'page-notes.txt',exact:true}).waitFor();
  return '混合上传页面显示正常文件，伪装媒体失败提示需结合接口证据';
 });
 await check('SF-RESOURCE-04',async()=>{await t.page.getByText('文件内容与类型不符',{exact:false}).waitFor();return '伪装MP4在上传结果显示格式失败';});
 const card=t.page.locator('section.card').filter({has:t.page.getByRole('heading',{name:'page-notes.txt',exact:true})}).first();
 await card.getByRole('button',{name:'查看资料'}).click();
 await check('SF-RESOURCE-05',async()=>{await t.page.getByText('解析状态：ready',{exact:true}).waitFor();return '详情显示正文ready解析状态；排队失败重试待演练';});
 await check('SF-RESOURCE-06',async()=>{await t.page.getByRole('button',{name:'查看版本历史'}).click();await t.page.getByRole('button',{name:'保存新版本'}).waitFor();return '版本历史与新正文上传入口可用，候选切换由接口测试覆盖';});
 await check('SF-RESOURCE-08',async()=>{
  await t.page.getByRole('link',{name:'下载原文件'}).waitFor();
  assert.equal(await t.page.evaluate(()=>window.injected),undefined);
  return '正文脚本文本未执行，原文件下载入口可见';
 });
 await t.page.screenshot({path:out+'/batch2-resource-page.png',fullPage:true});
 await check('SF-RESOURCE-07',async()=>{
  await card.getByRole('button',{name:'发布',exact:true}).click();
  await card.getByRole('button',{name:'下架',exact:true}).waitFor();
  return '教师页面发布成功并切换为下架操作';
 });
 await check('SF-RESOURCE-11',async()=>{await t.page.getByLabel('HTTP/HTTPS网址').fill('https://example.com/');await t.page.getByLabel('推荐理由').fill('登记审核');return '网址及推荐理由可编辑，保存发布待验证';});
 await s.page.getByRole('link',{name:'课程知识库'}).click();
 await s.page.getByRole('heading',{name:'page-notes.txt',exact:true}).waitFor();
 const sc=s.page.locator('section.card').filter({has:s.page.getByRole('heading',{name:'page-notes.txt',exact:true})}).first();
 await sc.getByRole('button',{name:'查看资料'}).click();
 await check('SF-RESOURCE-13',async()=>{
  await s.page.getByLabel('本次实际学习分钟').fill('17');
  await s.page.getByRole('button',{name:'保存学习记录（重复保存更新同一记录）'}).click();
  await s.page.getByRole('status').filter({hasText:'操作成功'}).waitFor();
  return '学生通过详情页面保存17分钟学习记录';
 });
 await check('SF-RESOURCE-12',async()=>{await s.page.getByRole('button',{name:'上传私有资料'}).click();await s.page.getByRole('heading',{name:'上传课程资料'}).waitFor();return '学生私有上传入口可操作，隔离由接口测试覆盖';});
 await s.page.goto(base+'/#password');
 await check('SF-ACCOUNT-04',async()=>{
  await s.page.getByLabel('显示姓名').fill('页面验收学生');
  await s.page.getByRole('button',{name:'保存姓名',exact:true}).click();
  await s.page.getByRole('status').filter({hasText:'已保存'}).waitFor();
  assert.equal((await (await s.context.request.get(base+'/api/v1/auth/me')).json()).name,'页面验收学生');
  return '页面修改姓名成功，服务端重读一致';
 });
 for(const id of ['SF-ACCOUNT-01','SF-CLASS-09','SF-RESOURCE-09','SF-RESOURCE-10','SF-RESOURCE-14'])
  results.push({id,status:'pending',observation:'本次页面演练未覆盖完整判据'});
}catch(e){results.push({id:'FLOW',status:'failed',error:e.message});}
finally{
 await browser.close();
 fs.writeFileSync(out+'/batch2-page-acceptance.json',JSON.stringify({checked_at:new Date().toISOString(),results},null,2));
}
console.log(JSON.stringify(results,null,2));
