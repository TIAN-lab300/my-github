import {chromium,expect} from '../frontend/node_modules/@playwright/test/index.mjs';
import {writeFile,mkdir} from 'node:fs/promises';
const dir='docs/evidence/implementation/admin-review';await mkdir(dir,{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true});
const results=[],errors=[];
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 page.on('pageerror',e=>errors.push(e.message));
 page.on('response',r=>{if(r.url().includes('/api/')&&r.status()>=400&&!r.url().endsWith('/auth/me'))errors.push(r.status()+' '+r.url())});
 await page.goto('http://127.0.0.1:9108/');
 await page.getByLabel('账号',{exact:true}).fill('admin');
 await page.getByLabel('密码',{exact:true}).fill('BrowserAcceptance123!');
 await page.getByRole('button',{name:'登录',exact:true}).click();
 for(const [hash,title,control] of [
 ['accounts','账号管理','创建账号，首次登录强制改密'],
 ['publish','共享课程知识库','上传资料'],
 ['settings','模型配置','登记配置'],
 ['audit','操作审计',null],
 ['graphs','知识图谱','保存图谱版本']]){
  await page.locator(`nav a[href="#${hash}"]`).click();
  await expect(page.locator('main h1')).toHaveText(title);
  if(control)await expect(page.getByRole('button',{name:control,exact:true})).toBeVisible();
  await page.waitForTimeout(500);
  await page.screenshot({path:`${dir}/${hash}.png`,fullPage:true});
  results.push({page:title,visible:true});
 }
 expect(errors).toEqual([]);
 await writeFile(`${dir}/results.json`,JSON.stringify({results,errors,scope:'Isolated browser fixture; read-only page checks; no cloud calls'},null,2));
 console.log(JSON.stringify({results,errors}));
}finally{await browser.close();}
