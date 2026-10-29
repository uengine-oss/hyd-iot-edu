// 지금 녹화 브라우저 화면을 건드리지 않고 다른 메뉴를 살펴본 뒤 원래 메뉴 · 스크롤로 되돌린다(구간 사이 길뚫기).
//   node look.mjs <메뉴 data-tab> [CSS 선택자 ...]      예: node look.mjs process '#decDetail .hopt .hrank'
// 그 메뉴를 열어 위에서부터 한 화면씩 PNG로 저장하고, 선택자마다 보이는 요소의 글 · 위치를 출력한다. 버튼은 누르지 않는다.
// 같은 메뉴를 보려면 현재 메뉴 이름을 그대로 준다(스크롤만 내렸다가 되돌림).
import fs from 'node:fs';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'/opt/node22/lib/node_modules/playwright');
const HERE=fileURLToPath(new URL('.',import.meta.url));
const CFG=JSON.parse(fs.readFileSync(HERE+'config.json','utf8'));
const [tab,...sels]=process.argv.slice(2);
if(!tab){console.error('사용: node look.mjs <메뉴 data-tab> [선택자 ...]');process.exit(2);}
const out=HERE+'../../../../../../작업/촬영/포털/look/'+tab;fs.mkdirSync(out,{recursive:true});
const b=await chromium.connectOverCDP(`http://127.0.0.1:${CFG.cdp}`);const p=b.contexts()[0].pages()[0];
if(!p.url().startsWith(CFG.portal))await p.goto(CFG.portal,{waitUntil:'domcontentloaded'}).then(()=>p.waitForTimeout(2500));   // 상주 브라우저가 빈 페이지면 포털부터
const cdp=await p.context().newCDPSession(p);
await cdp.send('Emulation.setDeviceMetricsOverride',{width:CFG.viewport.width,height:CFG.viewport.height,deviceScaleFactor:CFG.viewport.deviceScaleFactor,mobile:false});
const save=await p.evaluate(()=>({tab:document.querySelector('.rail nav button.active')?.dataset.tab,rail:document.querySelector('.rail').scrollTop,main:document.querySelector('main#content').scrollTop}));
await p.evaluate(t=>{const e=document.querySelector(`.rail nav button[data-tab="${t}"]`);if(!e)throw Error('메뉴 없음: '+t);e.click();},tab);
await p.waitForTimeout(tab==='trends'?9000:2500);
const h=await p.evaluate(()=>document.querySelector('main#content').scrollHeight);
for(let y=0,i=0;y<h&&i<10;y+=600,i++){await p.evaluate(y=>document.querySelector('main#content').scrollTop=y,y);await p.waitForTimeout(300);await p.screenshot({path:`${out}/${i}.png`});}
await p.evaluate(()=>document.querySelector('main#content').scrollTop=0);
for(const s of sels)console.log(s,JSON.stringify(await p.evaluate(s=>[...document.querySelectorAll(s)].filter(e=>e.checkVisibility()).slice(0,8).map(e=>{const r=e.getBoundingClientRect();return `${e.tagName} ${Math.round(r.x)},${Math.round(r.y)} ${e.textContent.trim().replace(/\s+/g,' ').slice(0,80)}`;}),s)));
await p.evaluate(t=>document.querySelector(`.rail nav button[data-tab="${t}"]`)?.click(),save.tab);await p.waitForTimeout(1200);
await p.evaluate(s=>{document.querySelector('.rail').scrollTop=s.rail;document.querySelector('main#content').scrollTop=s.main;},save);
console.log('화면',out,'· 되돌림',JSON.stringify(save));process.exit(0);
