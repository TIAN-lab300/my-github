import {chromium,expect} from '../frontend/node_modules/@playwright/test/index.mjs';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.launch({channel:'msedge',headless:true}),errors=[];
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:9121');await page.getByLabel('账号',{exact:true}).fill('student');await page.getByLabel('密码',{exact:true}).fill('TestPassword123!');
 await page.getByRole('button',{name:'登录',exact:true}).click();await page.locator('nav a[href="#resources"]').click();
 await page.getByLabel('选择专业课程',{exact:true}).selectOption('public-C01');
 await expect(page.getByRole('heading',{name:'课程、章节与先修关系',exact:true})).toBeVisible();
 await page.getByText('第2章 · 数组、函数与递归（3个知识点）',{exact:true}).click();
 await expect(page.locator('details').filter({has:page.getByText('第2章 · 数组、函数与递归（3个知识点）',{exact:true})}).locator('li').filter({hasText:'递归基础'})).toContainText('函数与参数传递');
 await page.screenshot({path:'docs/evidence/implementation/curriculum-structure-c.png',fullPage:true});
 await page.getByLabel('选择专业课程',{exact:true}).selectOption('public-C10');
 await expect(page.getByText(/建议先具备：计算机组成原理/)).toBeVisible();
 await page.getByLabel('选择专业课程',{exact:true}).selectOption('public-C21');
 await expect(page.getByText(/目录外基础：.*线性代数/)).toBeVisible();
 const response=await page.request.get('http://127.0.0.1:9121/api/v1/learning/courses/public-C21/structure');
 expect(response.status()).toBe(200);expect((await response.json()).version.official_verified).toBe(0);
 expect(errors).toEqual([]);
 const result={chapterMembershipVisible:true,skillPrerequisitesVisible:true,coursePrerequisitesVisible:true,externalMathVisible:true,projectBasisLabeled:true,pageErrors:errors};
 await writeFile('docs/evidence/implementation/curriculum-structure-browser.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await browser.close()}
