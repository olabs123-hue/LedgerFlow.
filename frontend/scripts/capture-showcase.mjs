import {chromium, devices} from '@playwright/test';
import {mkdir} from 'node:fs/promises';
import {join} from 'node:path';

const destination = process.env.SCREENSHOT_OUTPUT_DIR || 'portfolio-screenshots';
const root = process.env.SHOWCASE_URL || 'http://127.0.0.1:4173/';
await mkdir(destination,{recursive:true});

for (const [name,options] of [
  ['desktop',{viewport:{width:1440,height:900},deviceScaleFactor:1}],
  ['mobile',{...devices['Pixel 7']}],
]) {
  const browser=await chromium.launch({headless:true});
  const context=await browser.newContext(options);
  const page=await context.newPage();
  const responses=[];
  page.on('response',response=>{
    if (response.url().includes('/auth/') || response.url().includes('/transfers'))
      responses.push(response.url());
  });
  await page.goto(root,{waitUntil:'networkidle'});
  await page.getByRole('heading',{name:'Financial overview'}).waitFor();
  await page.screenshot({path:join(destination,`ledgerflow-showcase-${name}.png`),fullPage:true});
  if (responses.length>0) throw Error('Public showcase unexpectedly used financial API');
  console.log(`Captured ${name} screenshot without financial API calls`);
  await browser.close();
}
