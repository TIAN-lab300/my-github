import {chromium,expect} from '../frontend/node_modules/@playwright/test/index.mjs';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';

const base='http://127.0.0.1:9106';
const evidence=path.resolve('docs/evidence/implementation/remaining-browser');
await mkdir(evidence,{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true});
const results=[];
const errors=[];

async function login(username){
  const context=await browser.newContext();
  const page=await context.newPage();
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto(base);
  await page.getByLabel('账号',{exact:true}).fill(username);
  await page.getByLabel('密码',{exact:true}).fill('BrowserAcceptance123!');
  await page.getByRole('button',{name:'登录',exact:true}).click();
  await expect(page.getByRole('button',{name:'退出登录'})).toBeVisible();
  return {context,page};
}

try{
  const admin=await login('admin');
  await admin.page.getByRole('link',{name:/模型配置/}).click();
  await expect(admin.page.locator('input[name="timeout_seconds"]')).toHaveValue('45');
  await expect(admin.page.locator('input[name="prompt_version"]')).toHaveValue('zhixing-v1');
  results.push({name:'模型参数与提示词版本页面',passed:true});
  await admin.page.getByRole('button',{name:'查看场景响应并复核'}).click();
  const checks=admin.page.getByLabel('已核对本场景教学语义',{exact:true});
  await expect(checks).toHaveCount(60);
  for(const checkbox of await checks.all())await checkbox.check();
  await admin.page.getByLabel('实际复核依据').fill('浏览器契约样例，仅验证复核界面，没有真实供应商调用');
  await admin.page.getByRole('button',{name:'批准质量报告',exact:true}).click();
  await expect(admin.page.getByRole('status').filter({hasText:'质量报告已批准'})).toBeVisible();
  const configCard=admin.page.locator('section.card').filter({has:admin.page.getByRole('heading',{name:'BrowserContractModel',exact:true})});
  admin.page.once('dialog',dialog=>dialog.accept());
  await configCard.getByRole('button',{name:'激活',exact:true}).click();
  await expect(configCard.getByText('active',{exact:true})).toBeVisible();
  await admin.page.screenshot({path:path.join(evidence,'admin-quality.png'),fullPage:true});
  results.push({name:'60场景逐例复核与模型激活门槛（契约样例）',passed:true});

  await admin.page.getByRole('link',{name:/操作审计/}).click();
  await admin.page.locator('select[name="result"]').selectOption('failed');
  await admin.page.getByRole('button',{name:'查询',exact:true}).click();
  await expect(admin.page.getByRole('columnheader',{name:'结果'})).toBeVisible();
  results.push({name:'审计结果筛选页面',passed:true});
  await admin.page.getByRole('link',{name:/知识图谱/}).click();
  await expect(admin.page.getByText('根据授权资料生成新主题草稿',{exact:true})).toBeVisible();
  await admin.page.screenshot({path:path.join(evidence,'admin-graphs.png'),fullPage:true});
  results.push({name:'新主题草稿与题库入口',passed:true});

  const teacher=await login('teacher');
  await teacher.page.getByRole('link',{name:/课程知识库/}).click();
  await teacher.page.getByRole('button',{name:'上传资料',exact:true}).click();
  const upload=teacher.page.locator('form').filter({has:teacher.page.locator('input[name="files"]')});
  await upload.locator('textarea[name="description"]').fill('本地OCR页面验收');
  await upload.locator('input[name="tags"]').fill('OCR');
  await upload.locator('input[name="source_license"]').fill('本项目生成的测试图');
  await upload.locator('input[name="files"]').setInputFiles(path.resolve('backend/data/processing-smoke/ocr.png'));
  await teacher.page.getByRole('button',{name:'保存资料草稿'}).click();
  const card=teacher.page.locator('section.card').filter({has:teacher.page.getByRole('heading',{name:'ocr.png',exact:true})});
  await card.getByRole('button',{name:'查看资料'}).click();
  await teacher.page.getByRole('button',{name:'识别图片或扫描PDF'}).click();
  await expect(teacher.page.locator('article.reading')).toContainText('Python functions return values',{timeout:90000});
  await teacher.page.screenshot({path:path.join(evidence,'teacher-ocr.png'),fullPage:true});
  results.push({name:'教师上传图片并执行真实本地OCR',passed:true});

  const student=await login('student');
  await student.page.getByRole('link',{name:/目标与诊断/}).click();
  await expect(student.page.getByLabel('规划方式')).toBeVisible();
  await student.page.getByLabel('规划方式').selectOption('cloud');
  await expect(student.page.getByLabel('规划方式')).toHaveValue('cloud');
  results.push({name:'本地与云端四智能体模式选择',passed:true});
  await student.page.getByRole('link',{name:/资料检索与补充/}).click();
  await student.page.getByLabel('查询内容').fill('递归');
  await student.page.getByRole('button',{name:'检索授权课程正文'}).click();
  await expect(student.page.getByRole('link',{name:'下载该来源版本'}).first()).toBeVisible();
  await student.page.getByRole('button',{name:'搜索外部补充网址'}).click();
  await expect(student.page.getByRole('alert')).toContainText('尚未配置');
  await student.page.screenshot({path:path.join(evidence,'student-search.png'),fullPage:true});
  results.push({name:'授权检索、来源版本和未配置搜索状态',passed:true});
  if(errors.length)throw new Error(errors.join('\n'));
}catch(error){
  results.push({name:'浏览器执行失败',passed:false,error:String(error)});
  throw error;
}finally{
  await writeFile(path.join(evidence,'results.json'),JSON.stringify({time:new Date().toISOString(),results,pageErrors:errors},null,2));
  await browser.close();
}
