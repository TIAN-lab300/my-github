import {chromium} from '../frontend/node_modules/@playwright/test/index.mjs';
import {pathToFileURL} from 'node:url';
import path from 'node:path';
const browser=await chromium.launch({channel:'msedge',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1800,height:1080},deviceScaleFactor:1.5});
 for(const name of ['04-evidence-retrieval','05-resource-processing','06-agent-orchestration','07-profile-snapshot-recovery','08-docker-judge-retention']){
  await page.goto(pathToFileURL(path.resolve('docs/diagrams',name+'.svg')).href);
  await page.screenshot({path:path.resolve('docs/diagrams',name+'.png')});
 }
}finally{await browser.close()}
