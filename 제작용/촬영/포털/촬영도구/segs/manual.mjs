// 매뉴얼 적재 → 쿨러 이상 처리 구간(1회차 실습3). 큐 · 조작은 ../매뉴얼적재_쿨러이상_큐.json.
// 대상 이름은 포털 소개(portal_tour.mjs)의 이름에 이 실습의 화면 요소를 더한다. 구간마다 녹화 전 준비(BEFORE)가 기다릴 조건을 맞춘다.
import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {portal} from '../ui.mjs';
import {target as tourTarget} from './portal_tour.mjs';
const HERE=fileURLToPath(new URL('.',import.meta.url));
export const CUES=HERE+'../../매뉴얼적재_쿨러이상_큐.json';
const MORE={
 'know:파일 선택 버튼':{text:'파일 선택',tag:'span',nth:0},
 'know:파일 이름':{text:'HM-8_cooler-fan-manual.md',within:'label.file-picker',anchor:'below'},
 'know:미리보기':{css:'#manualPreview'},
 'know:크기':{css:'.mprev > div.muted',nth:0,anchor:'below'},
 'know:수정할 항목':{text:'수정할 항목 있음',anchor:'after'},
 'know:추출 요청':{css:'#manualAgentExtract'},
 'know:추출 상태':{css:'#manualAgentStatus',anchor:'below'},
 'know:결과 확인':{css:'#manualAgentResult'},
 'know:에이전트 상태':{css:'#manualAgentStatus',anchor:'below'},
 'know:HM-8.4':{text:'HM-8.4',tag:'b',anchor:'below'},
 'know:고장 유형 FAN-11':{css:'select[data-fm="SOP-FAN-11"]',anchor:'below'},
 'know:절차 COOL-11':{css:'input[data-manual-id="SOP-COOL-11"]',top:150},
 'know:관계 COOL-11':{css:'select[data-rel="SOP-COOL-11"]',anchor:'below'},
 'know:종류 COOL-11':{css:'select[data-kind="SOP-COOL-11"]',anchor:'below'},
 'know:절차 COOL-14':{css:'input[data-manual-id="SOP-COOL-14"]',top:150},
 'know:관계 COOL-14':{css:'select[data-rel="SOP-COOL-14"]',anchor:'below'},
 'know:종류 COOL-14':{css:'select[data-kind="SOP-COOL-14"]',anchor:'below'},
 'know:검토 확인':{css:'#manualReviewed'},
 'know:적재':{css:'#manualCommit'},
 'know:적재 결과':{css:'#manualMsg',anchor:'below'},
 'onto:팬 최대 운전':{text:'팬 최대 운전',tag:'text',anchor:'below'},
 'onto:쿨러 핀 세척':{text:'쿨러 핀 세척',tag:'text',anchor:'below'},
 'scen:쿨러 열화 주입 버튼':{text:'쿨러 열화 주입',tag:'button'},
 'scen:HYD-01 위':{text:'HYD-01',tag:'strong',top:150},
 'scen:경보 발생':{text:'경보 발생',nth:0,anchor:'after'},
 'inst:HYD-01 건':{text:'설비 이상 조치 HYD-01',within:'#instList',nth:0},
 'ap:추천':{css:'#todoPanel .ap-kicker',nth:0,anchor:'after'},
 'ap:추천 이름':{css:'#todoPanel .ap-head',nth:0,anchor:'below'},
 'ap:승인':{css:'#tdGo'},
 'res:결과 머리':{text:'재관측 확인',within:'#instDetail',tag:'h4',top:150},
 'res:설비에 명령':{text:'설비에 명령',within:'#instDetail',tag:'span.rr-step',anchor:'after'},
 'res:효과 확인':{text:'효과 확인 (15분)',within:'#instDetail',tag:'span.rr-step',anchor:'after'},
 'res:재관측':{text:'재관측 확인',within:'#instDetail',tag:'h4',anchor:'after'},
 'res:정비 요청':{css:'#instDetail .rr-ref',nth:0,anchor:'after'},
 'res:고장 넣은 순간':{text:'수업 버튼 [쿨러 열화 주입]',within:'#instDetail',tag:'b',anchor:'after'},
 'res:조치 선택':{text:'조치 선택',within:'#instDetail',tag:'b',anchor:'after'},
 'dec:판단 결과':{text:'판단 결과',within:'#decDetail',tag:'h3',top:110},
 'dec:1':{css:'#decDetail .hopt .hrank',nth:0,anchor:'margin'},
 'dec:2':{css:'#decDetail .hopt .hrank',nth:1,anchor:'margin'},
 'dec:3':{css:'#decDetail .hopt .hrank',nth:2,anchor:'margin'},
 'dec:4':{css:'#decDetail .hopt .hrank',nth:3,anchor:'margin'},
 'dec:1 유온':{css:'#decDetail .hopt .hline b',nth:0,anchor:'after'},
 'dec:4 점수':{css:'#decDetail .hopt .hbar b',nth:3,anchor:'after'},
};
export function target(name){return MORE[name]||tourTarget(name);}
export async function op(c,o){
 const [kind,name]=o;const t=kind==='waittext'?null:target(name);
 if(kind==='waittext')return c.waitText(name,150000);
 if(kind==='wait')return c.appear(t);
 if(kind==='point')return c.point(t);
 if(kind==='click')return c.click(t);
 if(kind==='scroll')return c.scrollTop(t,t.top??96);
 // 파일 고르기: 헤드리스 녹화에는 운영체제 파일 창이 찍히지 않는다 — 누름은 실제로 하고, 뜬 파일 창 이벤트에 파일을 넘긴다(화면에는 파일 이름이 남는다)
 if(kind==='file'){const w=c.raw.waitForEvent('filechooser',{timeout:10000});await c.click(t);const fc=await w;await fc.setFiles(o[2]);await c.sleep(400);return;}
 throw Error('unknown op '+kind);
}
const frac=o=>o[0]==='file'?o[3]:o[2];
const tab=(p,t)=>p.evaluate(t=>document.querySelector(`.rail nav button[data-tab="${t}"]`).click(),t);
// 녹화 전 준비(화면에 남지 않음).
const BEFORE={
 1:async ctx=>{const p=ctx.p;if(!p.url().startsWith('http://127.0.0.1:8088/'))await p.goto('http://127.0.0.1:8088/',{waitUntil:'domcontentloaded'});
  if(!(await p.evaluate(()=>localStorage.getItem('hyd.me'))))throw Error('나(hyd.me)가 비어 있음 — 승인자가 최운전이어야 한다');
  await tab(p,'main');await p.evaluate(()=>{for(const e of document.querySelectorAll('.rail,main#content'))e.scrollTop=0;});await ctx.sleep(2500);await ctx.installPointer({x:760,y:430});},

 // 승인 요청(선택 시간 초과 경계 PT10M = 20배속 30초)이 오면 바로 녹화를 시작한다. 패널이 자동으로 안 뜨면 내 차례 항목을 눌러 연다(녹화 밖).
 5:async ctx=>{const p=ctx.p;const a=Date.now();
  for(;;){const s=await p.evaluate(()=>{const b=document.querySelector('#tdGo');return b&&b.checkVisibility()?(b.disabled?'disabled':'ready'):(document.querySelector('#todoList .item')?'item':'none');});
   if(s==='ready')break;
   if(s==='item'){await p.evaluate(()=>document.querySelector('#todoList .item').click());}
   if(Date.now()-a>600000)throw Error('승인 요청이 10분 안에 오지 않음');await ctx.sleep(300);}
  console.error('approval ready after '+(Date.now()-a)+'ms');},
};
export async function seg(ctx,n){
 const cues=JSON.parse(await fs.readFile(CUES,'utf8')).cues.filter(c=>c.segment===n);
 if(!cues.length)throw Error('구간 '+n+' 큐 없음');
 const c=await portal(ctx);
 if(BEFORE[n])await BEFORE[n](ctx);
 await ctx.begin();
 for(const q of cues){
  const dur=JSON.parse(await fs.readFile(ctx.audio+'/'+q.id+'.json','utf8')).duration_ms;
  const ops=q.ops||[];const lead=300;
  const fn=ops.length?async()=>{const start=Date.now()-lead;
   for(let i=0;i<ops.length;i++){const due=start+Math.round(dur*(frac(ops[i])??0))-Date.now();if(due>0)await ctx.sleep(due);
    ctx.commitAt=0;await op(c,ops[i]);}}:null;
  await ctx.say(q.id,fn,{pointFrac:0,pointDelay:lead});
 }
 return {pos:c.pos()};
}
