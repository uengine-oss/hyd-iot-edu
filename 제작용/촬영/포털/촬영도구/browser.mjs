// 녹화용 브라우저를 띄워 두는 상주 프로세스(Playwright Chromium, 헤드리스). 구간 녹화(ctrl.mjs)는 CDP로 붙었다 떨어지므로
// 구간 사이에도 같은 페이지 · 스크롤 · 선택 상태가 유지된다(ego의 작업 공간 역할). 사용: node browser.mjs  (run.sh up이 백그라운드로 띄움)
import {createRequire} from 'node:module';
import fs from 'node:fs';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'/opt/node22/lib/node_modules/playwright');
const HERE=new URL('.',import.meta.url).pathname;
const CFG=JSON.parse(fs.readFileSync(HERE+'config.json','utf8'));
const browser=await chromium.launch({headless:true,args:[`--remote-debugging-port=${CFG.cdp}`,'--hide-scrollbars','--font-render-hinting=none']});
const ctx=await browser.newContext({viewport:{width:CFG.viewport.width,height:CFG.viewport.height},deviceScaleFactor:CFG.viewport.deviceScaleFactor,locale:'ko-KR',timezoneId:'Asia/Seoul'});
const page=await ctx.newPage();
await page.goto(CFG.portal,{waitUntil:'domcontentloaded'});
console.log(JSON.stringify({ready:true,cdp:CFG.cdp,url:page.url()}));
process.on('SIGTERM',async()=>{await browser.close();process.exit(0);});
await new Promise(()=>{});
