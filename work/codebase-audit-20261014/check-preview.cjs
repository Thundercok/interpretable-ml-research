const {chromium} = require('/Users/thundercock2/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const dir = __dirname;
(async () => {
  const browser = await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const page = await browser.newPage();
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const results=[];
  for (const width of [736,360,320]) {
    await page.setViewportSize({width,height:1100});
    await page.goto('file://'+path.join(dir,'preview.html'));
    const frame=page.frames().find(f=>f.parentFrame());
    await frame.waitForSelector('svg.cb-treemap a.cb-node',{timeout:20000});
    await frame.locator('#cb-scope').selectOption('all');
    await frame.waitForFunction(()=>document.querySelector('#cb-size').textContent.startsWith('978 file'));
    await page.waitForTimeout(450);
    const before=await frame.locator('#cb-size').textContent();
    const allLayout=await frame.evaluate(()=>{
      const root=document.getElementById('codebase-scope-20261014');
      const svg=root.querySelector('svg');
      return {width:root.getBoundingClientRect().width,scrollWidth:root.scrollWidth,nodes:svg.querySelectorAll('a').length};
    });
    await page.screenshot({path:path.join(dir,`preview-all-${width}.png`),fullPage:true});
    await frame.locator('#cb-scope').selectOption('tests');
    await frame.waitForFunction(()=>document.querySelector('#cb-size').textContent.startsWith('74 file'));
    const tests=await frame.locator('#cb-size').textContent();
    await frame.locator('#cb-scope').selectOption('core');
    await frame.waitForFunction(()=>document.querySelector('#cb-size').textContent.startsWith('26 file'));
    const core=await frame.locator('#cb-size').textContent();
    const groups=await frame.locator('#cb-group option').evaluateAll(os=>os.map(o=>o.value));
    const pick=groups.find(g=>g!=='_small');
    await frame.locator('#cb-group').selectOption(pick);
    const detail=await frame.locator('#cb-selected').textContent();
    await page.waitForTimeout(450);
    const layout=await frame.evaluate(()=>{
      const root=document.getElementById('codebase-scope-20261014');
      const svg=root.querySelector('svg');
      const bounds=svg.getBoundingClientRect();
      const clips=[...svg.querySelectorAll('a')].flatMap(a=>{
        const rect=a.querySelector('rect').getBoundingClientRect();
        return [...a.querySelectorAll('tspan')].filter(t=>{
          const box=t.getBoundingClientRect();
          return box.left<rect.left-1||box.right>rect.right+1||box.top<rect.top-1||box.bottom>rect.bottom+1;
        }).map(t=>t.textContent);
      });
      return {rootWidth:root.getBoundingClientRect().width,scrollWidth:root.scrollWidth,plotWidth:bounds.width,nodes:svg.querySelectorAll('a').length,clippedLabels:clips};
    });
    await page.screenshot({path:path.join(dir,`preview-${width}.png`),fullPage:true});
    results.push({width,before,tests,core,detail,allLayout,layout});
  }
  await page.emulateMedia({colorScheme:'dark'});
  await page.setViewportSize({width:736,height:1100});
  await page.goto('file://'+path.join(dir,'preview.html'));
  const frame=page.frames().find(f=>f.parentFrame());
  await frame.waitForSelector('svg.cb-treemap a.cb-node',{timeout:20000});
  await frame.locator('#cb-scope').selectOption('all');
  await page.waitForTimeout(450);
  await page.screenshot({path:path.join(dir,'preview-dark.png'),fullPage:true});
  await browser.close();
  const verification={results,errors};
  await fs.writeFile(path.join(dir,'browser-verification.json'),JSON.stringify(verification,null,2));
  console.log(JSON.stringify(verification,null,2));
  if(errors.length||results.some(r=>r.allLayout.scrollWidth>r.allLayout.width+1||r.layout.scrollWidth>r.layout.rootWidth+1||r.layout.clippedLabels.length)) process.exitCode=1;
})().catch(e=>{console.error(e.message);process.exitCode=1;});
