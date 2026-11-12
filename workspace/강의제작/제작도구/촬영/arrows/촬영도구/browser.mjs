// 클라우드 녹화용 브라우저를 띄워 두는 상주 프로세스(Playwright 헤드리스 Chromium). run.sh up이 백그라운드로 띄운다.
// 화면은 config.json cloud.metrics(CSS 1536×864 × 배율 1.25 = 프레임 1920×1080 — ego 150 %의 CSS 1536×864와 같은 배치)다.
// 헤드리스 화면 녹화는 CSS 픽셀 크기로 오므로 --force-device-scale-factor를 함께 준다(포털 browser.mjs와 같은 까닭).
// 페이지는 기본 문맥 하나에 둔다(빈 프로필 = 저장소가 빈 새 브라우저, 처음 여는 학생과 같은 화면). 새 문맥에 두면 CDP로 붙은 녹화 쪽이 내려받은 파일을 찾지 못한다.
// 구간 녹화(ctrl.mjs)는 CDP로 붙었다 떨어지므로, 구간 사이에도 같은 페이지 · 그림 · 저장소가 유지된다.
import {createRequire} from 'node:module';
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'/opt/node22/lib/node_modules/playwright');
const HERE=fileURLToPath(new URL('.',import.meta.url));
const CFG=JSON.parse(fs.readFileSync(HERE+'config.json','utf8'));
const M=CFG.cloud.metrics;
const ctx=await chromium.launchPersistentContext('',{headless:true,args:[`--remote-debugging-port=${CFG.cloud.cdp}`,`--force-device-scale-factor=${M.deviceScaleFactor}`,'--hide-scrollbars','--font-render-hinting=none'],
 viewport:{width:M.width,height:M.height},deviceScaleFactor:M.deviceScaleFactor,locale:'ko-KR',timezoneId:'Asia/Seoul',acceptDownloads:true});
const page=ctx.pages()[0]||await ctx.newPage();
await page.goto('about:blank');
console.log(JSON.stringify({ready:true,cdp:CFG.cloud.cdp,url:page.url()}));
process.on('SIGTERM',async()=>{await ctx.close();process.exit(0);});
await new Promise(()=>{});
