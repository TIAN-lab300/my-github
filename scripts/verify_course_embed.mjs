import {chromium,expect} from '../frontend/node_modules/@playwright/test/index.mjs';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.launch({channel:'msedge',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 // Only UI lifecycle is tested with this explicitly labeled fixture.
 // The separate live check returned net::ERR_CONNECTION_CLOSED.
 await page.route('https://www.icourse163.org/**',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><meta charset="utf-8"><h1>C语言程序设计 · 嵌入控件验收样例</h1><p>这是窗口测试内容，不代表原站视频已播放。</p>'}));
 const networkFailures=[];page.on('requestfailed',r=>{if(r.isNavigationRequest())networkFailures.push({url:r.url(),error:r.failure()?.errorText})});
 await page.goto('http://127.0.0.1:9121');await page.getByLabel('账号',{exact:true}).fill('student');await page.getByLabel('密码',{exact:true}).fill('TestPassword123!');
 await page.getByRole('button',{name:'登录',exact:true}).click();await page.locator('nav a[href="#resources"]').click();
 await page.getByLabel('选择专业课程',{exact:true}).selectOption('public-C01');
 await expect(page.getByRole('button',{name:'在本页打开：C语言程序设计（上）',exact:true})).toHaveCount(1);
 await expect(page.locator('iframe')).toHaveCount(0);
 await page.getByRole('button',{name:'在本页打开：C语言程序设计（上）',exact:true}).click();
 const frame=page.locator('iframe[title="原站课程：C语言程序设计（上）"]');
 await expect(frame).toHaveAttribute('src','https://www.icourse163.org/course/BIT-20019');
 await expect(frame).toBeVisible();
 let originalPageRendered=false,videoElements=0,videoPlaybackVerified=false;
 try{
  const content=page.frameLocator('iframe[title="原站课程：C语言程序设计（上）"]');
  await expect(content.locator('body')).toContainText('C语言程序设计',{timeout:20000});
  originalPageRendered=true;videoElements=await content.locator('video').count();
  if(videoElements)videoPlaybackVerified=await content.locator('video').first().evaluate(v=>!v.paused&&v.currentTime>0);
 }catch{/* Keep truthful outcome for connectivity or provider restrictions. */}
 await page.locator('section[aria-label="嵌入课程窗口"]').screenshot({path:'docs/evidence/implementation/course-embed-browser.png'});
 await expect(page.getByRole('link',{name:'无法观看？在原站打开 C语言程序设计（上） ↗',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'关闭课程窗口',exact:true}).click();await expect(page.locator('iframe')).toHaveCount(0);
 await page.getByRole('button',{name:'在本页打开：C语言程序设计（下）',exact:true}).click();
 await page.getByLabel('选择专业课程',{exact:true}).selectOption('public-C03');await expect(page.getByLabel('选择专业课程',{exact:true})).toHaveValue('public-C03');
 await expect(page.getByRole('button',{name:'在本页打开：数据结构',exact:true})).toBeVisible();
 await expect(page.locator('iframe[title^="原站课程："]')).toHaveCount(0);
 const result={opensOnDemand:true,correctUrl:true,closeWorks:true,courseSwitchUnloadsFrame:true,fallbackVisible:true,fixturePageRendered:originalPageRendered,videoElements,videoPlaybackVerified,serverVideoDownloads:0,networkFailures,liveOriginalPageVerified:false,liveCheckError:'net::ERR_CONNECTION_CLOSED',verificationScope:'嵌入窗口生命周期通过；测试页不是原站视频，实际MOOC播放未验证'};
 await writeFile('docs/evidence/implementation/course-embed-browser.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await browser.close()}
