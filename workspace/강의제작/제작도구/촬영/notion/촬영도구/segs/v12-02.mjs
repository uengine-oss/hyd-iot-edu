// v12-02 · 2단계 새 페이지 만들기 — 시작: 1단계에서 「Notion 열기」로 연 웹 작업 화면(이 구간부터 다시 찍으면 준비가 v12.home을 연다), 사이드바 열림.
// 끝: 「내 학습 노트」(아이콘 · 커버) 페이지, 제목 아래 본문 캐럿, 사이드바 닫힘.
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:2}];
export async function prepare(c){
 const {raw,serial}=c;
 if(!(await serial(()=>raw.url())).includes('app.notion')){await serial(()=>raw.goto(c.ctx.v12.home,{timeout:150000,waitUntil:'domcontentloaded'}));}
 await c.ensureKorean();
 await serial(()=>raw.waitForFunction(()=>document.querySelectorAll('[aria-label="새 페이지"]').length>0||!!document.querySelector('[aria-label="사이드바 열기"]'),undefined,{timeout:30000}));
 if(!(await serial(()=>raw.evaluate(()=>[...document.querySelectorAll('[aria-label="사이드바 닫기"]')].some(e=>e.checkVisibility({checkVisibilityCSS:true}))))))
  {await serial(()=>raw.mouse.move(30,30,{steps:2}));await serial(()=>raw.waitForSelector('[aria-label="사이드바 열기"]',{state:'visible',timeout:6000}));await serial(()=>raw.click('[aria-label="사이드바 열기"]'));}
 await serial(()=>raw.waitForFunction(()=>[...document.querySelectorAll('[aria-label="새 페이지"]')].some(e=>e.checkVisibility({checkVisibilityCSS:true})),undefined,{timeout:10000}));
 if(!(await c.pointerAt()))await c.place({x:760,y:430});
}
export const ops=c=>{const {at,K}=kit(c);
 const menuOpen=()=>c.serial(()=>c.raw.evaluate(()=>[...document.querySelectorAll('[role=menuitem],[role=option]')].some(e=>e.textContent.trim().startsWith('페이지')&&e.checkVisibility({checkVisibilityCSS:true}))));
 return{2:{
 // 왼쪽 위 「새 페이지」(같은 이름이 여럿이면 첫째). 2.4초 안에 메뉴가 없으면 한 번 더 누르고 기록한다.
 새페이지:async()=>{await c.click('css',await c.mark({css:'[aria-label="새 페이지"]',first:true}));for(let n=0;n<12&&!(await menuOpen());n++)await c.sleep(200);
  if(!(await menuOpen())){await c.fs.appendFile(c.out+'/reclicks.jsonl',JSON.stringify({target:'새 페이지',reason:'menu not shown within 2.4s'})+String.fromCharCode(10));await c.click('css',await c.mark({css:'[aria-label="새 페이지"]',first:true}));
   for(let n=0;n<12&&!(await menuOpen());n++)await c.sleep(200);if(!(await menuOpen()))throw Error('새 페이지 menu did not open after two clicks');}
  // 다음 큐(「메뉴에서 페이지를 고르시면」 2.1초)에 옮기기까지 하면 말 뒤로 넘친다(k6 s02-03 2.6초) — 메뉴가 뜨면 「페이지」 항목 위로 미리 옮겨 둔다.
  const q=await c.locate('menu','페이지');await c.glide(q.x,q.y);},
 페이지고르기:{pointFrac:0,fn:async()=>{c.at(0.75);await c.click('menu','페이지');await c.serial(()=>c.raw.waitForSelector('h1[contenteditable=true]',{timeout:10000}));await c.fs.writeFile(c.out+'/new-page-url.txt',await c.serial(()=>c.raw.url()));}},
 제목입력:at(0,async()=>{c.at(0.5);await c.titleType(c.ctx.homeTitle);}),
 제목위올리기:()=>c.titleHover(),
 아이콘공책:at(0,()=>c.emoji('홈',{times:{open:0.12,type:0.3,pick:1}})),
 아이콘짚기:()=>c.hoverIcon(),
 커버추가:()=>c.coverAdd(),
 // 커버에 올리기는 말 가운데쯤, 「변경하기」로 옮기기는 그다음에 하고 누르기만 큐 끝에 한다 — 옮기기를 큐 끝까지 미루면 말이 끝난 뒤 옮기기 · 창 열기로
 // 화면만 5.7초 굴러갔다(k1 s02-09).
 커버변경:at(0.3,async()=>{c.at(0.55);await c.coverHover();c.at(1);await c.coverChange();await c.coverAim();}),
 커버고르기:()=>c.coverPick(),
 제목끝엔터:at(0,async()=>{c.at(0.3);await c.titleEnter();}),
 목록이름짚기:async()=>{const id=(await c.serial(()=>c.raw.url())).match(/[0-9a-f]{32}/g)?.at(-1);if(!id)throw Error('No page id in URL');await c.hoverAt(await c.mark({css:`.notion-sidebar a[href*="${id}"]`,first:true}));},
 목록접기:at(0.3,()=>c.click('aria','사이드바 닫기')),
}};};
