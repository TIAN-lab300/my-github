import {chromium,expect} from '../frontend/node_modules/@playwright/test/index.mjs';
const browser=await chromium.launch({channel:'msedge',headless:true});
try{
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:9108/');
 await page.getByLabel('账号',{exact:true}).fill('student');
 await page.getByLabel('密码',{exact:true}).fill('BrowserAcceptance123!');
 await page.getByRole('button',{name:'登录',exact:true}).click();
 await page.locator('nav a[href="#goal"]').click();
 await expect(page.getByRole('heading',{name:'模型配置与题库说明'})).toBeVisible();
 await page.getByText('如何激活模型配置',{exact:true}).click();
 await expect(page.getByText('由管理员登录，在左侧进入“模型配置”。学生账号不能激活模型。')).toBeVisible();
 const catalog=await page.request.get('http://127.0.0.1:9108/api/v1/curriculum/skills');
 expect(catalog.status()).toBe(200);const skills=(await catalog.json()).skills;
 expect(skills.length).toBeGreaterThan(0);
 const title='题库页面回归 '+Date.now();
 const due=new Date(Date.now()+30*86400000).toISOString().slice(0,10);
 const g=await page.request.post('http://127.0.0.1:9108/api/v1/goals',{data:{title,target_skill_ids:[skills.find(s=>s.diagnostic_available).id],due_date:due,weekly_minutes:120,preference:'text'}});
 expect(g.status()).toBe(201);
 await page.getByRole('button',{name:'刷新',exact:true}).click();
 const card=page.locator('section.card').filter({has:page.getByRole('heading',{name:title,exact:true})});
 await card.getByRole('button',{name:'开始/查看诊断'}).click();
 await expect(page.getByRole('heading',{name:/目标诊断 · \d+题/})).toBeVisible();
 await page.screenshot({path:'docs/evidence/implementation/form-layout/goal-readiness.png',fullPage:true});
 expect(errors).toEqual([]);console.log(JSON.stringify({catalog:skills.length,diagnosisVisible:true,activationHelp:true,errors}));
}finally{await browser.close();}
