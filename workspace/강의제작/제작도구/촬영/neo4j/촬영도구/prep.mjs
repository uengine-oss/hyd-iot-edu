// 녹화 밖에서 상주 브라우저의 탭을 열고 맞춘다(화면에 남지 않는 준비). rec.sh prep이 부른다.
//   open <Neo4j Browser 주소>          Neo4j Browser 탭(첫 탭)을 그 주소로 새로 연다 — 학생이 lab_db.py로 여는 주소
//   guide <안내.html 경로> [절 id]      안내 문서 탭을 열거나 찾아, 그 절의 머리가 화면 위쪽에 오게 굴려 둔다
//   shot <png 경로> [main|guide]        그 탭의 화면을 녹화와 같은 크기로 찍는다(길뚫기 확인용)
//   eval <main|guide> <JS 식>           그 탭에서 식을 돌려 결과를 찍는다(길뚫기 — 상태를 바꾸지 않는 식만)
import {createRequire} from 'node:module';
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
const HERE=fileURLToPath(new URL('.',import.meta.url));
const CFG=JSON.parse(fs.readFileSync(HERE+'config.json','utf8'));
const {chromium}=createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE||'/opt/node22/lib/node_modules/playwright');
const b=await chromium.connectOverCDP(`http://127.0.0.1:${CFG.cdp}`),ctx=b.contexts()[0];
await ctx.grantPermissions(['clipboard-read','clipboard-write']).catch(()=>{});
const [cmd,...a]=process.argv.slice(2);
const main=()=>ctx.pages().find(x=>x.url().includes('/browser/'))||ctx.pages()[0];
const guide=()=>ctx.pages().find(x=>x.url().startsWith('file:')&&x.url().endsWith('.html'));
const metrics=async pg=>{const s=await ctx.newCDPSession(pg);await s.send('Emulation.setDeviceMetricsOverride',{...CFG.viewport,mobile:false});return s;};
if(cmd==='open'){const p=main();await metrics(p);await p.goto(a[0]);await p.waitForSelector('[role="dialog"] input[name="hostname"]',{timeout:30000});await p.bringToFront();console.log('open',p.url());}
else if(cmd==='guide'){let g=guide();if(!g){g=await ctx.newPage();await metrics(g);await g.goto('file://'+a[0]);}else await metrics(g);
 if(a[1])await g.evaluate(id=>{const e=document.getElementById(id)||document.querySelector(`[id$="${id}"]`);if(!e)throw Error('절 없음: '+id);window.scrollTo(0,e.getBoundingClientRect().top+scrollY-40);},a[1]);
 await main().bringToFront();console.log('guide',g.url(),await g.evaluate(()=>scrollY));}
else if(cmd==='shot'){const p=a[1]==='guide'?guide():main();const s=await metrics(p);const r=await s.send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(a[0],Buffer.from(r.data,'base64'));console.log('shot',a[0]);}
else if(cmd==='eval'){const p=a[0]==='guide'?guide():main();console.log(JSON.stringify(await p.evaluate(a[1]),null,1));}
else{console.log(fs.readFileSync(HERE+'prep.mjs','utf8').split('\n').slice(0,5).join('\n'));process.exit(2);}
await b.close();process.exit(0);
