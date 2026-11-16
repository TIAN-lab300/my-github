import {chromium,expect} from '../frontend/node_modules/@playwright/test/index.mjs';
import {writeFile} from 'node:fs/promises';
const base='http://127.0.0.1:9120',errors=[];
const browser=await chromium.launch({channel:'msedge',headless:true});
try{
 async function login(name){
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.getByLabel('账号',{exact:true}).fill(name);await page.getByLabel('密码',{exact:true}).fill('TestPassword123!');
  await page.getByRole('button',{name:'登录',exact:true}).click();await expect(page.locator('nav a').first()).toBeVisible();return page;
 }
 const admin=await login('admin');await admin.locator('nav a[href="#publish"]').click();
 await admin.getByLabel('选择专业课程',{exact:true}).selectOption('public-C01');
 await expect(admin.getByRole('button',{name:'审核保存映射',exact:true})).toBeVisible();
 const mappingForm=admin.locator('form').filter({has:admin.getByRole('button',{name:'审核保存映射',exact:true})});
 await mappingForm.locator('select[name=skill]').selectOption('public-C01-K001');await mappingForm.locator('select[name=graph]').selectOption('functions');
 admin.once('dialog',d=>d.accept());await mappingForm.getByRole('button').click();await expect(admin.getByText('映射审核已保存',{exact:true})).toBeVisible();
 await admin.screenshot({path:'docs/evidence/implementation/course-bridge-admin.png',fullPage:true});
 const student=await login('student2');await student.locator('nav a[href="#resources"]').click();
 await student.getByLabel('选择专业课程',{exact:true}).selectOption('public-C01');
 for(const name of ['函数基础','递归与结束条件','调用栈与综合练习'])await student.getByLabel('选择'+name,{exact:true}).check();
 await student.locator('select').filter({has:student.locator('option[value="diagnostic"]')}).selectOption('diagnostic');
 await student.getByRole('button',{name:'按所选知识点开始测验',exact:true}).click();
 const quiz=student.locator('section.card').filter({has:student.getByRole('heading',{name:'知识检测 · 6题',exact:true})}).last();
 await expect(quiz).toBeVisible();for(const field of await quiz.locator('fieldset').all())await field.locator('input[type=radio]').nth(1).check();
 student.once('dialog',d=>d.accept());await quiz.getByRole('button',{name:'提交测验',exact:true}).click();await expect(quiz).toContainText('得分：0.0');
 const goalForm=student.locator('form').filter({has:student.getByRole('button',{name:'连接初测并创建目标',exact:true})});
 await goalForm.locator('input[name=title]').fill('浏览器课程闭环验收');
 await goalForm.locator('input[name=due]').fill(new Date(Date.now()+20*86400000).toISOString().slice(0,10));
 await goalForm.getByRole('button').click();await expect(student.getByText(/课程初测已连接目标/)).toBeVisible();
 await student.locator('nav a[href="#goal"]').click();
 const goal=student.locator('section.card').filter({has:student.getByRole('heading',{name:'浏览器课程闭环验收',exact:true})}).first();
 // Cards in the main app are div.card; resolve by heading when needed.
 const card=student.getByRole('heading',{name:'浏览器课程闭环验收',exact:true}).locator('..').locator('..');
 await card.getByRole('button',{name:'生成首次路径',exact:true}).click();
 await expect(student.getByRole('button',{name:'查看生成路径',exact:true})).toBeVisible({timeout:30000});
 await student.getByRole('button',{name:'查看生成路径',exact:true}).click();
 await student.getByRole('button',{name:'查看路径与差异',exact:true}).first().click();
 await student.getByText('查看本次规划使用的诊断与掌握度',{exact:true}).click();
 await expect(student.getByRole('columnheader',{name:'本次诊断答对 / 题数',exact:true})).toBeVisible();
 student.once('dialog',d=>d.accept());await student.getByRole('button',{name:'接受此路径',exact:true}).click();
 await expect(student.getByRole('button',{name:'知识测验与掌握验证',exact:true}).first()).toBeVisible();
 await student.getByRole('button',{name:'知识测验与掌握验证',exact:true}).first().click();
 await student.getByRole('button',{name:'开始测验',exact:true}).click();
 await expect(student.getByText(/functions practice 第/)).toBeVisible();
 await student.screenshot({path:'docs/evidence/implementation/course-bridge-student.png',fullPage:true});
 expect(errors).toEqual([]);
 const result={adminMappingSaved:true,courseDiagnosisSubmitted:true,goalCreated:true,pathGenerated:true,evidenceVisible:true,pathAccepted:true,coursePathAssessmentVisible:true,pageErrors:errors};
 await writeFile('docs/evidence/implementation/course-bridge-browser.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await browser.close()}
