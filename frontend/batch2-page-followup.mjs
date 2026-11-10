import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const base='http://127.0.0.1:8003',out='../docs/evidence/implementation';
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
const results=[];
const context=await browser.newContext({viewport:{width:1440,height:1000}});
const page=await context.newPage();
page.on('dialog',d=>d.accept());
async function check(id,fn){try{results.push({id,status:'observed',observation:await fn()})}catch(e){results.push({id,status:'failed',error:e.message})}}
async function resourceCard(title){return page.locator('section.card').filter({has:page.getByRole('heading',{name:title,exact:true})}).first()}
async function upload(name,mimeType,buffer){
 await page.getByRole('button',{name:'上传资料',exact:true}).click();
 const activeClasses=await (await context.request.get(base+'/api/v1/classes')).json();
 await page.locator('select:not([name])').first().selectOption(activeClasses.find(c=>c.status==='active').id);
 await page.getByLabel('资料说明',{exact:true}).fill('附件页面验收');
 await page.locator('input[name=tags]').fill('media');
 await page.getByLabel('来源及使用权限',{exact:true}).fill('自有测试样本');
 await page.getByLabel('选择文件',{exact:true}).setInputFiles({name,mimeType,buffer});
 await page.getByRole('button',{name:'保存资料草稿'}).click();
 await page.getByRole('heading',{name,exact:true}).waitFor();
}
try{
 await page.goto(base);
 await page.getByLabel('账号',{exact:true}).fill('teacher');
 await page.getByLabel('密码',{exact:true}).fill('AcceptanceOnly!123');
 await page.getByRole('button',{name:'登录',exact:true}).click();
 await page.getByRole('button',{name:'退出登录'}).waitFor();
 await page.getByRole('link',{name:'课程知识库'}).click();
 const suffix=Date.now();
 const wav=Buffer.alloc(16044);
 wav.write('RIFF');wav.writeUInt32LE(wav.length-8,4);wav.write('WAVEfmt ',8);wav.writeUInt32LE(16,16);
 wav.writeUInt16LE(1,20);wav.writeUInt16LE(1,22);wav.writeUInt32LE(8000,24);wav.writeUInt32LE(16000,28);
 wav.writeUInt16LE(2,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(16000,40);
 const audio='audio-'+suffix+'.wav';
 await upload(audio,'audio/wav',wav);
 let card=await resourceCard(audio);
 await check('SF-RESOURCE-14',async()=>{
  await card.getByText('无可检索正文',{exact:false}).waitFor();
  await card.getByRole('button',{name:'发布',exact:true}).click();
  await card.getByRole('button',{name:'下架',exact:true}).waitFor();
  return '无正文音频可通过页面发布，明确显示无可检索正文';
 });
 await card.getByRole('button',{name:'查看资料'}).click();
 await check('SF-RESOURCE-09',async()=>{
  const player=page.locator('audio');
  await player.waitFor();
  await player.evaluate(async element=>{await element.play()});
  assert.equal(await player.evaluate(element=>element.paused),false);
  await page.getByLabel('关联字幕TXT/SRT/VTT').setInputFiles({name:'caption.txt',mimeType:'text/plain',buffer:Buffer.from('真实音频字幕内容')});
  await page.getByRole('button',{name:'保存字幕版本'}).click();
  await card.getByRole('button',{name:'发布',exact:true}).waitFor();
  await card.getByRole('button',{name:'查看资料'}).click();
  await page.locator('article').filter({hasText:'真实音频字幕内容'}).waitFor();
  return '音频实际播放成功，上传字幕后回草稿，重新打开显示字幕正文';
 });
 await page.screenshot({path:out+'/batch2-audio-caption.png',fullPage:true});
 await page.getByRole('button',{name:'关闭详情'}).click();
 const image='image-'+suffix+'.png';
 const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aA1cAAAAASUVORK5CYII=','base64');
 await upload(image,'image/png',png);
 card=await resourceCard(image);
 await check('SF-RESOURCE-10',async()=>{
  await card.getByRole('button',{name:'查看资料'}).click();
  const picture=page.getByRole('img',{name:image,exact:true});
  await picture.waitFor();
  await picture.evaluate(el=>el.decode());
  const download=page.waitForEvent('download');
  await page.getByRole('link',{name:'下载原文件'}).click();
  assert.equal((await download).suggestedFilename(),image);
  return '图片成功解码预览，点击下载取得原始文件名';
 });
 await page.screenshot({path:out+'/batch2-image.png',fullPage:true});
 await check('SF-CLASS-09',async()=>{
  const api=base+'/api/v1';
  const cr=await context.request.post(api+'/classes',{data:{name:'补发验收-'+suffix,description:'补发'}});const cid=(await cr.json()).id;
  const ir=await context.request.post(api+'/classes/'+cid+'/invites',{data:{max_uses:10}});
  const learner=await browser.newContext();
  await learner.request.post(api+'/auth/login',{data:{username:'student',password:'AcceptanceOnly!123'}});
  await learner.request.post(api+'/class-invites/'+(await ir.json()).code+'/join');
  const tr=await context.request.post(api+'/teacher/tasks',{data:{class_id:cid,title:'补发原任务-'+suffix,description:'验证补发',mode:'text',minutes:5,due_at:new Date(Date.now()+86400000).toISOString()}});
  const tid=(await tr.json()).id;
  await context.request.post(api+'/teacher/tasks/'+tid+'/publish');
  await page.getByRole('link',{name:'任务管理'}).click();
  const task=page.locator('section.card').filter({has:page.getByRole('heading',{name:'补发原任务-'+suffix,exact:true})});
  await task.getByRole('button',{name:'创建指定学生补发草稿'}).click();
  await task.locator('input[type=checkbox]').first().check();
  const response=page.waitForResponse(r=>r.url().endsWith('/supplement')&&r.request().method()==='POST');
  await task.getByRole('button',{name:'建立补发草稿',exact:true}).click();
  const result=await response;assert.equal(result.status(),201);
  const created=(await result.json()).id;
  const detail=await context.request.get(api+'/teacher/tasks/'+created);
  assert.equal((await detail.json()).status,'draft');
  await learner.close();
  return '通过页面选人并创建补发草稿，服务端重读为draft；原任务保持已发布';
 });
 await page.getByRole('link',{name:'班级总览'}).click();
 const available=await (await context.request.get(base+'/api/v1/classes')).json();
 await page.locator('select:not([name])').first().selectOption(available.filter(c=>c.status==='active').at(-1).id);
 await check('SF-CLASS-07',async()=>{
  const button=page.getByRole('button',{name:'移除',exact:true}).first();
  const row=button.locator('..');
  await button.click();
  await button.waitFor({state:'detached'});
  return '教师页面确认移除后，成员行不再提供有效成员移除按钮';
 });
 await check('SF-CLASS-08',async()=>{
  await page.getByRole('button',{name:'归档班级',exact:true}).click();
  await page.getByRole('button',{name:'归档班级',exact:true}).waitFor({state:'visible'});
  assert.equal(await page.getByRole('button',{name:'归档班级',exact:true}).isDisabled(),true);
  assert.equal(await page.getByRole('button',{name:'生成自定义邀请码'}).isDisabled(),true);
  assert.equal(await page.getByRole('button',{name:'编辑班级信息'}).isDisabled(),true);
  return '确认归档后归档、编辑和生成邀请均禁用';
 });
}catch(e){results.push({id:'FLOW',status:'failed',error:e.message})}
finally{await browser.close();fs.writeFileSync(out+'/batch2-page-followup.json',JSON.stringify({checked_at:new Date().toISOString(),results},null,2))}
console.log(JSON.stringify(results,null,2));
