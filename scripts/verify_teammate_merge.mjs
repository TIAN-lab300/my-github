import {chromium,expect} from '../frontend/node_modules/@playwright/test/index.mjs';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.launch({channel:'msedge',headless:true});
const results=[],errors=[];
try{
 for(const role of ['admin','teacher','student']){
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  page.on('pageerror',e=>errors.push(role+': '+e.message));
  await page.goto('http://127.0.0.1:9108/');
  await page.getByLabel('账号',{exact:true}).fill(role);await page.getByLabel('密码',{exact:true}).fill('BrowserAcceptance123!');
  await page.getByRole('button',{name:'登录',exact:true}).click();await expect(page.locator('nav a').first()).toBeVisible();
  if(role!=='student'){
   await page.locator('nav a[href="#bank"]').click();await expect(page.locator('main')).toContainText('题库');
   expect((await page.request.get('http://127.0.0.1:9108/api/v1/question-bank')).status()).toBe(200);
  }else{
   await page.locator('nav a[href="#goal"]').click();await expect(page.getByText(/云端状态：/)).toBeVisible();
   const status=await page.request.get('http://127.0.0.1:9108/api/v1/planning/model-status');expect(status.status()).toBe(200);
   const value=await status.json();expect(typeof value.key_ready).toBe('boolean');
   await page.locator('nav a[href="#resources"]').click();await expect(page.getByLabel('选择专业课程',{exact:true}).locator('option')).toHaveCount(36);
   await page.getByLabel('选择专业课程',{exact:true}).selectOption('public-C03');
   await expect(page.getByRole('heading',{name:'课程学习、测验与评价'})).toBeVisible();
  }
  await page.screenshot({path:`docs/evidence/implementation/merged-${role}.png`,fullPage:true});
  results.push({role,passed:true});await page.close();
 }
 expect(errors).toEqual([]);
 await writeFile('docs/evidence/implementation/teammate-merge-browser.json',JSON.stringify({results,errors,liveCloudCalls:0},null,2));
 console.log(JSON.stringify({results,errors}));
}finally{await browser.close();}
