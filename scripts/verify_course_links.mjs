import {chromium,expect} from '../frontend/node_modules/@playwright/test/index.mjs';
import {readFile,writeFile} from 'node:fs/promises';
const entries=JSON.parse(await readFile('docs/curriculum/mooc-course-links.json','utf8')).courses;
const browser=await chromium.launch({channel:'msedge',headless:true}),errors=[];
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:9121');await page.getByLabel('账号',{exact:true}).fill('student');await page.getByLabel('密码',{exact:true}).fill('TestPassword123!');
 await page.getByRole('button',{name:'登录',exact:true}).click();await page.locator('nav a[href="#resources"]').click();
 const region=page.locator('section[aria-label="课程视频学习入口"]');
 for(const cid of [...new Set(entries.map(e=>e.course_id))]){
  await page.getByLabel('选择专业课程',{exact:true}).selectOption(cid);
  const expected=entries.filter(e=>e.course_id===cid);
  await expect(region.getByRole('link')).toHaveCount(expected.length);
  for(const e of expected){
   const link=region.getByRole('link',{name:'前往原站学习：'+e.title+' ↗',exact:true});
   await expect(link).toHaveAttribute('href',e.url);await expect(link).toHaveAttribute('target','_blank');
   await expect(link.locator('..')).toContainText(e.school);
  }
 }
 await page.getByLabel('选择专业课程',{exact:true}).selectOption('public-C01');
 await region.screenshot({path:'docs/evidence/implementation/course-links-browser.png'});
 await expect(page.getByRole('link',{name:'打开资料原站 ↗'}).first()).toBeVisible();
 await page.getByLabel('选择专业课程',{exact:true}).selectOption('public-C18');
 await expect(region).toContainText('尚未添加已核对的视频课程入口');
 expect(errors).toEqual([]);
 const result={linkedCourses:7,courseLinks:10,matchingUrls:true,schoolLabels:true,newTab:true,sourceLinksVisible:true,emptyStateVisible:true,pageErrors:errors};
 await writeFile('docs/evidence/implementation/course-links-browser.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await browser.close()}
