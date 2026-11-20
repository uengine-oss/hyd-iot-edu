// 녹화용 브라우저(cloud · pc)를 띄워 두는 상주 프로세스(Playwright 헤드리스 Chromium). run.sh up이 백그라운드로 띄운다.
// 화면은 config.json 그 환경 칸의 metrics(CSS 크기 × 배율 = 프레임 1920×1080)다. screencast 크기는 브라우저를 띄울 때의 배율을 따르므로, 값을 바꾸면 띄운 뒤 장면 하나가 딱 1920×1080인지 잰다(촬영준비 함정).
// 헤드리스 화면 녹화는 CSS 픽셀 크기로 오므로 --force-device-scale-factor를 함께 준다(포털 browser.mjs와 같은 까닭).
// 페이지는 기본 문맥 하나에 둔다(빈 프로필 = 저장소가 빈 새 브라우저, 처음 여는 학생과 같은 화면). 새 문맥에 두면 CDP로 붙은 녹화 쪽이 내려받은 파일을 찾지 못한다.
// 구간 녹화(ctrl.mjs)는 CDP로 붙었다 떨어지므로, 구간 사이에도 같은 페이지 · 그림 · 저장소가 유지된다.
// 환경(cloud · pc)마다 다른 값은 config.json의 그 환경 칸에서 env.mjs가 읽는다(이 파일에 환경 분기를 두지 않는다).
import {ENV,PROFILE,playwright} from './env.mjs';
const {chromium}=playwright();
const M=PROFILE.metrics;
const ctx=await chromium.launchPersistentContext('',{headless:PROFILE.headless??true,args:[`--remote-debugging-port=${PROFILE.cdp}`,`--force-device-scale-factor=${M.deviceScaleFactor}`,'--hide-scrollbars','--font-render-hinting=none'],
 viewport:{width:M.width,height:M.height},deviceScaleFactor:M.deviceScaleFactor,locale:'ko-KR',timezoneId:'Asia/Seoul',acceptDownloads:true});
const page=ctx.pages()[0]||await ctx.newPage();
await page.goto('about:blank');
console.log(JSON.stringify({ready:true,env:ENV,cdp:PROFILE.cdp,pid:process.pid,url:page.url()}));
process.on('SIGTERM',async()=>{await ctx.close();process.exit(0);});
await new Promise(()=>{});
