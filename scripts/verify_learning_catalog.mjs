import {chromium,expect} from '../frontend/node_modules/@playwright/test/index.mjs';
const base='http://127.0.0.1:9108';const browser=await chromium.launch({channel:'msedge',headless:true});
const errors=[];
try{
 async function login(name){const page=await browser.newPage({viewport:{width:1440,height:1000}});page.on('pageerror',e=>errors.push(e.message));await page.goto(base);await page.getByLabel('账号',{exact:true}).fill(name);await page.getByLabel('密码',{exact:true}).fill('BrowserAcceptance123!');await page.getByRole('button',{name:'登录',exact:true}).click();await expect(page.locator('nav a').first()).toBeVisible();return page;}
 const admin=await login('admin');const api=admin.request;
 const upload=await api.post(base+'/api/v1/resources',{multipart:{files:{name:'learning.txt',mimeType:'text/plain',buffer:Buffer.from('算法复杂度描述输入规模增长时的时间或空间消耗。常数次操作是O(1)。')},title:'学习闭环验收正文',description:'独立浏览器验收资料',tags:'算法复杂度',source_license:'测试自编'}});
 expect(upload.status()).toBe(201);const resource=(await upload.json())[0];
 expect((await api.post(base+'/api/v1/resources/'+resource.id+'/publish')).status()).toBe(200);
 expect((await api.post(base+'/api/v1/learning/courses/public-C03/materials',{data:{skill_id:'public-C03-K001',resource_id:resource.id,locator:'第1段'}})).status()).toBe(201);
 for(let i=0;i<2;i++){
  const q=await api.post(base+'/api/v1/learning/questions',{data:{course_id:'public-C03',skill_id:'public-C03-K001',prompt:`验收题${i}：固定次数的操作对应哪一项？`,options:['O(1)','O(n)'],answer:0,explanation:'固定次数不随输入规模增长。',source:'隔离测试自编',phase:'practice'}});
  expect(q.status()).toBe(201);expect((await api.post(base+'/api/v1/learning/questions/'+(await q.json()).id+'/publish',{data:{confirmed:true}})).status()).toBe(200);
 }
 const student=await login('student');await student.locator('nav a[href="#resources"]').click();await student.getByLabel('选择专业课程',{exact:true}).selectOption('public-C03');
 const row=student.locator('tr').filter({has:student.getByLabel('选择算法复杂度',{exact:true})});
 await expect(row.getByRole('button',{name:'学习闭环验收正文',exact:true})).toBeVisible();
 await row.getByRole('button',{name:'保存本次学习',exact:true}).click();
 await student.getByLabel('选择算法复杂度',{exact:true}).check();
 await student.getByRole('button',{name:'按所选知识点开始测验',exact:true}).click();
 const paper=student.locator('section.card').filter({has:student.getByRole('heading',{name:'知识检测 · 2题',exact:true})}).last();
 await expect(paper).toBeVisible();
 for(const field of await paper.locator('fieldset').all())await field.locator('input[type=radio]').first().check();
 await paper.getByRole('button',{name:'暂存作答',exact:true}).click();
 student.once('dialog',d=>d.accept());await paper.getByRole('button',{name:'提交测验',exact:true}).click();
 await expect(paper).toContainText('得分：100.0');
 await expect(student.getByText(/算法复杂度 · 学习\d+分钟/)).toBeVisible();
 await student.screenshot({path:'docs/evidence/implementation/learning-assessment-browser.png',fullPage:true});
 expect(errors).toEqual([]);console.log(JSON.stringify({materialLinked:true,studySaved:true,questions:2,draftSaved:true,score:100,skillEvaluationVisible:true,pageErrors:errors}));
}finally{await browser.close();}
