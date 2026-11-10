import {chromium,expect} from '../frontend/node_modules/@playwright/test/index.mjs';
import {mkdir,writeFile} from 'node:fs/promises';
const output='docs/evidence/implementation/form-layout';
await mkdir(output,{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true});
const results=[];const errors=[];
try{
 for(const role of ['admin','teacher','student']){
  const context=await browser.newContext();const page=await context.newPage();
  page.on('pageerror',error=>errors.push(role+': '+error.message));
  await page.goto('http://127.0.0.1:9108/');
  const toggle=page.getByLabel('显示密码',{exact:true});
  const alignment=await toggle.evaluate(input=>{
   const label=input.closest('label');const range=document.createRange();range.selectNodeContents(label.lastChild);
   const box=input.getBoundingClientRect(),text=range.getBoundingClientRect();
   return box.width<=20&&box.left<label.getBoundingClientRect().left+3&&box.bottom<=text.top+2;
  });
  if(!alignment)throw new Error('Password toggle alignment failed');
  await page.getByLabel('账号',{exact:true}).fill(role);
  await page.getByLabel('密码',{exact:true}).fill('BrowserAcceptance123!');
  await page.getByRole('button',{name:'登录',exact:true}).click();
  await expect(page.locator('.account-settings-link')).toBeVisible();
  const links=await page.locator('nav a').evaluateAll(nodes=>nodes.map(node=>({href:node.getAttribute('href'),text:node.textContent})));
  for(const link of links){
   await page.locator(`nav a[href="${link.href}"]`).click();
   await page.waitForTimeout(400);
   await expect(page.locator('main h1')).toBeVisible();
   const clipped=await page.locator('main input:not([type=hidden]), main textarea, main select, main button').evaluateAll(nodes=>nodes.filter(node=>{
    const box=node.getBoundingClientRect();if(!box.width||!box.height)return false;
    return box.width<8||box.height<8;
   }).map(node=>node.outerHTML.slice(0,120)));
   if(clipped.length)throw new Error(JSON.stringify(clipped));
   results.push({role,page:link.text,passed:true});
  }
  await page.locator('.account-settings-link').click();
  await expect(page.locator('input[name="old_password"]')).toBeVisible();
  results.push({role,page:'修改密码入口',passed:true});
  if(role!=='admin'){
   await page.locator(`nav a[href="${role==='teacher'?'#publish':'#resources'}"]`).click();
   await page.getByRole('button',{name:role==='teacher'?'上传资料':'上传私有资料',exact:true}).click();
   const form=page.locator('form').filter({has:page.locator('input[name="files"]')});
   await form.locator('textarea[name="description"]').fill('页面布局验收');
   await form.locator('input[name="tags"]').fill('布局');
   await form.locator('input[name="source_license"]').fill('自编');
   await form.locator('input[name="files"]').setInputFiles({name:`layout-${role}.txt`,mimeType:'text/plain',buffer:Buffer.from('函数与递归布局验收')});
   const submit=form.getByRole('button',{name:'提交资料并保存草稿'});
   await submit.scrollIntoViewIfNeeded();await expect(submit).toBeVisible();
   await page.setViewportSize({width:390,height:844});
   await submit.scrollIntoViewIfNeeded();await expect(submit).toBeVisible();
   await page.screenshot({path:`${output}/${role}-upload-mobile.png`,fullPage:true});
   const response=page.waitForResponse(response=>response.url().endsWith('/api/v1/resources')&&response.request().method()==='POST');
   await submit.click();if((await response).status()!==201)throw new Error('Upload failed');
   results.push({role,page:'窄屏上传并提交',passed:true});
  }
  await context.close();
 }
 if(errors.length)throw new Error(errors.join('\n'));
}finally{
 await writeFile(`${output}/results.json`,JSON.stringify({results,errors},null,2));await browser.close();
}
