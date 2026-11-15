import {createRequire} from 'node:module';
import fs from 'node:fs';
import {spawn} from 'node:child_process';
import path from 'node:path';
const root=process.cwd(),require=createRequire(path.join(root,'frontend/package.json'));
const {chromium}=require('playwright');
const config=JSON.parse(fs.readFileSync('stage3-browser-config.json','utf8'));
const port=18763,log=fs.openSync('stage3-browser-server.log','w');
const server=spawn(path.join(root,'.venv/Scripts/python.exe'),['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(port)],{cwd:root,env:{...process.env,PYTHONPATH:path.join(root,'backend'),ZHIXING_DATA:config.data,ZHIXING_MODEL_DIR:path.join(root,'backend/data/models'),PYTHONUTF8:'1'},stdio:['ignore',log,log],windowsHide:true});
let browser,page;const results=[];
try{
 for(let i=0;i<100;i++){try{if((await fetch(`http://127.0.0.1:${port}/api/v1/health`)).ok)break}catch{}await new Promise(r=>setTimeout(r,100))}
 browser=await chromium.launch({channel:'msedge',headless:true});fs.mkdirSync('阶段三验收截图',{recursive:true});
 page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 async function login(name){await page.goto(`http://127.0.0.1:${port}`);await page.getByLabel('账号',{exact:true}).fill(name);await page.getByLabel('密码',{exact:true}).fill('Acceptance123!');await page.getByRole('button',{name:'登录',exact:true}).click();await page.getByRole('button',{name:'退出登录'}).waitFor()}
 await login('teacher');await page.getByRole('link',{name:'题库管理'}).click();await page.getByRole('button',{name:'新建题目'}).click();
 await page.getByLabel('题干',{exact:true}).fill('函数中的return语句有什么作用？');
 for(let i=1;i<=3;i++)await page.getByLabel(`选项 ${i}`,{exact:true}).fill(['返回结果并结束本次调用','重新启动程序','清空所有变量'][i-1]);
 await page.getByLabel('答案解析').fill('return将结果交还调用者，并结束当前函数调用。');await page.getByLabel('来源说明').fill('浏览器验收自编题');
 await page.getByRole('button',{name:'保存草稿',exact:true}).click();await page.getByText('草稿已保存',{exact:true}).waitFor();
 const article=page.locator('article').filter({hasText:'函数中的return语句有什么作用？'});
 await article.getByRole('button',{name:'编辑草稿'}).click();await page.getByLabel('答案解析').fill('return返回计算结果，结束本次函数调用，调用者继续执行。');await page.getByRole('button',{name:'保存草稿',exact:true}).click();
 await article.getByRole('button',{name:'提交审核'}).click();await page.getByText('已提交审核',{exact:true}).waitFor();
 if(await article.getByRole('button',{name:'审核通过'}).count())throw Error('Teacher approval control');results.push('教师创建、编辑、提交和角色按钮通过');
 await page.getByRole('button',{name:'退出登录'}).click();await login('admin');await page.getByRole('link',{name:'题库审核'}).click();
 const review=page.locator('article').filter({hasText:'函数中的return语句有什么作用？'});
 await review.getByLabel('审核或停用意见').fill('浏览器验收核对答案解析通过');await review.getByRole('button',{name:'审核通过'}).click();await review.getByRole('button',{name:'发布',exact:true}).click();await review.getByRole('button',{name:'停用',exact:true}).waitFor();
 await page.screenshot({path:'阶段三验收截图/管理员题库.png',fullPage:true});results.push('管理员审核发布通过');
 await page.getByRole('button',{name:'退出登录'}).click();await login('student');
 async function openTask(){await page.getByRole('link',{name:'我的学习路径'}).click();await page.getByRole('button',{name:'查看路径与差异'}).first().click();await page.getByRole('button',{name:'知识测验与掌握验证'}).first().click()}
 await openTask();await page.getByRole('button',{name:'开始测验',exact:true}).click();await page.getByLabel('正确选项',{exact:true}).check();await page.getByLabel('累计测验用时（分钟）').fill('8');await page.getByRole('button',{name:'保存答案',exact:true}).click();await page.getByText('答案与用时已保存').waitFor();
 await page.reload();await openTask();if(!await page.getByLabel('正确选项',{exact:true}).isChecked())throw Error('Draft lost');if(await page.getByLabel('累计测验用时（分钟）').inputValue()!=='8')throw Error('Minutes lost');
 await page.getByRole('button',{name:'提交评分',exact:true}).click();await page.getByRole('heading',{name:'测验结果 · 100%'}).waitFor();await page.getByText('测验已提交，掌握证据与路径状态已刷新').waitFor();await page.getByRole('button',{name:'申请复测'}).click();await page.getByRole('button',{name:'提交评分',exact:true}).waitFor();await page.getByLabel('正确选项',{exact:true}).check();await page.getByRole('button',{name:'提交评分',exact:true}).click();await page.getByRole('heading',{name:'测验结果 · 100%'}).waitFor();
 await page.screenshot({path:'阶段三验收截图/学生复测.png',fullPage:true});results.push('学生保存、恢复、评分、复测和历史通过');
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:'阶段三验收截图/学生手机布局.png',fullPage:true});
 if(errors.length)throw Error(errors.join('\n'));fs.writeFileSync('stage3-browser-result.json',JSON.stringify({passed:true,checks:results,page_errors:errors},null,2));console.log(JSON.stringify(results));
}catch(e){if(page){await page.screenshot({path:'阶段三验收截图/失败现场.png',fullPage:true});console.log(await page.locator('main').innerText())}console.error(e);process.exitCode=1}finally{if(browser)await browser.close();server.kill();fs.closeSync(log)}
