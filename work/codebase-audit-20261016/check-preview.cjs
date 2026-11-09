const {chromium}=require('/Users/thundercock2/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('node:fs/promises'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 const page=await browser.newPage();const errors=[],results=[];page.on('pageerror',e=>errors.push(e.message));
 for(const theme of ['light','dark'])for(const width of [736,360,320]){
  await page.emulateMedia({colorScheme:theme,reducedMotion:'reduce'});await page.setViewportSize({width,height:1200});
  await page.goto('file://'+path.join(__dirname,'preview.html'));const frame=page.frames().find(f=>f.parentFrame());await frame.waitForSelector('svg.rc-chart a',{timeout:20000});
  for(const scope of ['product','main','all']){
   await frame.locator('#rc-scope').selectOption(scope);await page.waitForTimeout(80);
   const data=await frame.evaluate(()=>{const r=document.getElementById('rat-cot-unified-20261016');const bad=[];for(const a of r.querySelectorAll('svg a')){const rect=a.querySelector('rect').getBoundingClientRect();for(const t of a.querySelectorAll('text')){const b=t.getBoundingClientRect();if(b.left<rect.left-1||b.right>rect.right+1||b.top<rect.top-1||b.bottom>rect.bottom+1)bad.push(t.textContent);}}return {total:r.querySelector('#rc-total').textContent,width:r.getBoundingClientRect().width,scrollWidth:r.scrollWidth,bad};});
   if(data.scrollWidth>data.width+1||data.bad.length)throw Error(JSON.stringify({width,theme,scope,...data}));results.push({width,theme,scope,...data});
  }
  await frame.locator('#rc-scope').selectOption('product');await frame.locator('#rc-pick').selectOption('evrp');if(!(await frame.locator('#rc-title').textContent()).includes('EVRP'))throw Error('Select failed');
  await frame.locator('a[data-role-id="reasoning"]').click();if(!(await frame.locator('#rc-title').textContent()).includes('Suy luận'))throw Error('Treemap failed');
  if(width===736)await page.screenshot({path:path.join(__dirname,`preview-product-${theme}.png`),fullPage:true});await frame.locator('#rc-scope').selectOption('main');await page.screenshot({path:path.join(__dirname,`preview-${theme}-${width}.png`),fullPage:true});
 }
 await browser.close();if(errors.length)throw Error(JSON.stringify(errors));await fs.writeFile(path.join(__dirname,'browser-verification.json'),JSON.stringify({errors,results},null,2));process.stdout.write(JSON.stringify({errors,statesChecked:results.length,interaction:'pass'}));
})().catch(e=>{process.stderr.write(String(e));process.exit(1)});
