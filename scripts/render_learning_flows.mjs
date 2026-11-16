import {chromium} from '../frontend/node_modules/@playwright/test/index.mjs';
import {pathToFileURL} from 'node:url';
import path from 'node:path';
const root=path.resolve('docs/diagrams');
const browser=await chromium.launch({channel:'msedge',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1800,height:1080},deviceScaleFactor:1.5});
 for(const name of ['01-initial-diagnosis','02-learning-replanning','03-course-knowledge-database']){
  await page.goto(pathToFileURL(path.join(root,name+'.svg')).href);
  await page.screenshot({path:path.join(root,name+'.png')});
 }
}finally{await browser.close()}
