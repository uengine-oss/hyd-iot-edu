// 녹화 없이 큐의 조작 대상을 시험한다(길뚫기). 상태를 바꾸지 않는 조작만 실제로 하고, 끝나면 원래 메뉴 · 스크롤로 되돌린다.
//   node dry.mjs <구간 모듈(segs/ 기준, 예: manual.mjs)> <구간 번호> [화면 저장 폴더]
// 실제로 하는 것: point · scroll · wait, 그리고 왼쪽 메뉴 누르기(click tab:…). 화면 이동만 한다.
// 건너뛰는 것(되돌릴 수 없거나 서버에 남는다): file(파일 고르기), select, waittext, 메뉴가 아닌 click(미리보기 · 추출 요청 · 적재 · 주입 · 승인 …).
//   건너뛴 조작 뒤에 나오는 화면의 대상은 이 시험으로 확인할 수 없다 → 그 시점 화면을 녹화 없이 보는 look.mjs와 코드(it/portal/www)로 확인한다.
// 결과: 큐마다 대상 좌표 · 실패, 큐 끝 화면 PNG. 실패가 하나라도 있으면 종료 코드 1.
import fs from 'node:fs';
import {createRequire} from 'node:module';
import {fileURLToPath, pathToFileURL} from 'node:url';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'/opt/node22/lib/node_modules/playwright');
const HERE=fileURLToPath(new URL('.',import.meta.url));
const CFG=JSON.parse(fs.readFileSync(HERE+'config.json','utf8'));
const [mod,segArg,outArg]=process.argv.slice(2);
if(!mod||!segArg){console.error('사용: node dry.mjs <segs 모듈> <구간 번호> [화면 폴더]');process.exit(2);}
const seg=Number(segArg);const out=outArg||HERE+'../../../../.evidence/dry/'+mod.replace('.mjs','')+'-'+seg;fs.mkdirSync(out,{recursive:true});
const {portal,installPointerInPage}=await import(pathToFileURL(HERE+'ui.mjs').href);
const M=await import(pathToFileURL(HERE+'segs/'+mod).href);
const b=await chromium.connectOverCDP(`http://127.0.0.1:${CFG.cdp}`);const p=b.contexts()[0].pages()[0];
if(!p.url().startsWith(CFG.portal))await p.goto(CFG.portal,{waitUntil:'domcontentloaded'}).then(()=>p.waitForTimeout(2500));   // 상주 브라우저가 빈 페이지면 포털부터
const cdp=await p.context().newCDPSession(p);
await cdp.send('Emulation.setDeviceMetricsOverride',{width:CFG.viewport.width,height:CFG.viewport.height,deviceScaleFactor:CFG.viewport.deviceScaleFactor,mobile:false});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));let q=Promise.resolve();const serial=fn=>{const r=q.then(fn);q=r.catch(()=>{});return r;};
const save=await p.evaluate(()=>({tab:document.querySelector('.rail nav button.active')?.dataset.tab,rail:document.querySelector('.rail')?.scrollTop,main:document.querySelector('main#content')?.scrollTop}));
// 화살표 · 실제 마우스를 같은 자리에 둔다(실제 마우스가 (0,0)이면 휠이 엉뚱한 영역을 굴린다)
await p.evaluate(installPointerInPage,{x:760,y:430});await p.mouse.move(760,430);
const c=await portal({p,serial,sleep,commitAt:0,waitFor:async()=>{}});
const cues=JSON.parse(fs.readFileSync(M.CUES,'utf8')).cues.filter(x=>x.segment===seg);
if(!cues.length){console.error('구간 '+seg+' 큐 없음');process.exit(2);}
let fails=0;
for(const cue of cues){
 for(const o of cue.ops||[]){
  const [kind,name]=o;const safe=kind==='point'||kind==='scroll'||kind==='wait'||(kind==='click'&&String(name).startsWith('tab:'));
  if(!safe){console.log(cue.id,kind,name,'건너뜀(녹화로만 — 되돌릴 수 없거나 서버에 남음)');continue;}
  try{const r=await M.op(c,o);console.log(cue.id,kind,name,'ok',r?`${Math.round(r.x)},${Math.round(r.y)}`:'');}
  catch(e){fails++;console.log(cue.id,kind,name,'실패',e.message.slice(0,200));}
  await sleep(kind==='click'?1500:300);
 }
 await p.screenshot({path:`${out}/${cue.id}.png`});
}
// 되돌리기: 원래 메뉴 · 스크롤
if(save.tab){await p.evaluate(t=>document.querySelector(`.rail nav button[data-tab="${t}"]`)?.click(),save.tab);await sleep(1200);
 await p.evaluate(s=>{const r=document.querySelector('.rail'),m=document.querySelector('main#content');if(r)r.scrollTop=s.rail;if(m)m.scrollTop=s.main;},save);}
console.log(fails?`실패 ${fails}개`:'모두 통과','· 화면',out);
process.exit(fails?1:0);
