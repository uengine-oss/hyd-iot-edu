// 녹화용 브라우저를 띄워 두는 상주 프로세스(Playwright Chromium, 헤드리스). 헤드리스 화면 녹화는 CSS 픽셀 크기로 오므로 --force-device-scale-factor를 함께 줘야 1920x1080 프레임이 온다(2026-10-23 실측). 구간 녹화(ctrl.mjs)는 CDP로 붙었다 떨어지므로
// 구간 사이에도 같은 페이지 · 스크롤 · 선택 상태가 유지된다(ego의 작업 공간 역할). 사용: node browser.mjs  (run.sh up이 백그라운드로 띄움)
import {createRequire} from 'node:module';
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'/opt/node22/lib/node_modules/playwright');
const HERE=fileURLToPath(new URL('.',import.meta.url));
const CFG=JSON.parse(fs.readFileSync(HERE+'config.json','utf8'));
// 페이지는 브라우저 기본 문맥에 둔다(launchPersistentContext, 빈 프로필 폴더 = 임시). 새 문맥(newContext)에 두면 CDP로 붙은 녹화 쪽이
// 내려받은 파일을 이 프로세스의 임시 폴더에서 찾지 못해 saveAs가 ENOENT로 실패한다(2026-11-03 06 촬영 C003a). 기본 문맥은 붙은 쪽이 내려받기 위치를 정한다.
const ctx=await chromium.launchPersistentContext('',{headless:true,args:[`--remote-debugging-port=${CFG.cdp}`,`--force-device-scale-factor=${CFG.viewport.deviceScaleFactor}`,'--hide-scrollbars','--font-render-hinting=none'],
 viewport:{width:CFG.viewport.width,height:CFG.viewport.height},deviceScaleFactor:CFG.viewport.deviceScaleFactor,locale:'ko-KR',timezoneId:'Asia/Seoul'});
const page=ctx.pages()[0]||await ctx.newPage();
// 빈 페이지로 시작한다. 각 구간이 자기 화면(GitHub · 포털)을 연다 — 포털이 꺼진 채 README만 찍을 때 여기서 죽었다(2026-10-23).
await page.goto('about:blank');
console.log(JSON.stringify({ready:true,cdp:CFG.cdp,url:page.url()}));
process.on('SIGTERM',async()=>{await ctx.close();process.exit(0);});
await new Promise(()=>{});
