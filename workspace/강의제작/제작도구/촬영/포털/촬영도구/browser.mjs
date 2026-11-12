// 녹화용 브라우저를 띄워 두는 상주 프로세스(Playwright Chromium, 헤드리스). 헤드리스 화면 녹화는 CSS 픽셀 크기로 오므로 --force-device-scale-factor를 함께 줘야 1920x1080 프레임이 온다(2026-10-23 실측). 구간 녹화(ctrl.mjs)는 CDP로 붙었다 떨어지므로
// 구간 사이에도 같은 페이지 · 스크롤 · 선택 상태가 유지된다(ego의 작업 공간 역할). 사용: node browser.mjs  (run.sh up이 백그라운드로 띄움)
import {createRequire} from 'node:module';
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'/opt/node22/lib/node_modules/playwright');
const HERE=fileURLToPath(new URL('.',import.meta.url));
// 다른 도구(neo4j)도 같은 상주 브라우저를 쓴다: HYD_BROWSER_CONFIG=<그 도구 촬영도구/config.json> node browser.mjs (값은 그 파일의 cdp · viewport).
const CFG=JSON.parse(fs.readFileSync(process.env.HYD_BROWSER_CONFIG||HERE+'config.json','utf8'));
// 페이지는 브라우저 기본 문맥에 둔다(launchPersistentContext, 빈 프로필 폴더 = 임시). 새 문맥(newContext)에 두면 CDP로 붙은 녹화 쪽이
// 내려받은 파일을 이 프로세스의 임시 폴더에서 찾지 못해 saveAs가 ENOENT로 실패한다(2026-11-03 06 촬영 C003a). 기본 문맥은 붙은 쪽이 내려받기 위치를 정한다.
// 글꼴: 학생 Windows 크롬과 같게 그린다(fonts.conf 머리말). 맑은 고딕은 사용자가 올린 파일을 /usr/share/fonts/malgun/에 둔다(포털 촬영준비 「자료 · 글꼴」).
// 없으면 시스템 설정 그대로 띄우되 학생 화면과 글꼴이 다르다고 남긴다. 글꼴은 띄울 때 한 번 정해지므로, 구간을 이어 찍는 도중에는 브라우저를 다시 띄우지 않는다.
const MALGUN=fs.existsSync('/usr/share/fonts/malgun/malgun.ttf');
if(!MALGUN)console.log(JSON.stringify({warning:'맑은 고딕 없음 — 학생 Windows 화면과 글꼴이 다르게 찍힌다(포털 촬영준비 「자료 · 글꼴」)'}));
// 설정 파일이 깨지면 fontconfig가 조용히 시스템 설정으로 돌아간다(주석 안의 빼기 두 개로 겪음). 띄우기 전에 실제로 맑은 고딕을 고르는지 확인하고, 아니면 멈춘다.
if(MALGUN){const {execFileSync}=await import('node:child_process');
 const got=execFileSync('fc-match',['sans-serif','family'],{env:{...process.env,FONTCONFIG_FILE:HERE+'fonts.conf'},encoding:'utf8',stdio:['ignore','pipe','pipe']}).trim();
 if(!/Malgun Gothic/.test(got))throw Error('fonts.conf가 맑은 고딕을 고르지 않음: '+got);}
const ctx=await chromium.launchPersistentContext('',{headless:true,...(MALGUN?{env:{...process.env,FONTCONFIG_FILE:HERE+'fonts.conf'}}:{}),args:[`--remote-debugging-port=${CFG.cdp}`,`--force-device-scale-factor=${CFG.viewport.deviceScaleFactor}`,'--hide-scrollbars','--font-render-hinting=none'],
 viewport:{width:CFG.viewport.width,height:CFG.viewport.height},deviceScaleFactor:CFG.viewport.deviceScaleFactor,locale:'ko-KR',timezoneId:'Asia/Seoul'});
const page=ctx.pages()[0]||await ctx.newPage();
// 빈 페이지로 시작한다. 각 구간이 자기 화면(GitHub · 포털)을 연다 — 포털이 꺼진 채 README만 찍을 때 여기서 죽었다(2026-10-23).
await page.goto('about:blank');
console.log(JSON.stringify({ready:true,cdp:CFG.cdp,url:page.url(),fonts:MALGUN?'windows(fonts.conf)':'system'}));
process.on('SIGTERM',async()=>{await ctx.close();process.exit(0);});
await new Promise(()=>{});
