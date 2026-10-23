// 녹화 밖 상태 맞춤(run.sh restore <종류>). 실행 취소(Ctrl+Z)는 쓰지 않는다 — 필요한 블록만 지우거나 만든다.
//   cut25      : 구간25 3:05(N06-v002 직전) — 안내 상자 블록 '삭제', 소개 아래 빈 줄 하나에 캐럿, 사이드바 닫힘
//   noteTail   : 안내 상자 안에 생긴 빈 줄을 Backspace로 지워 상자 글 끝에 캐럿(구간25 끝 상태)
//   cut27      : 구간27 57.0s(live-page-search 직전) — 「노션 익히기」 주제에서 하위 페이지 블록 「첫 페이지 꾸미기」 삭제(휴지통),
//                「나의 페이지」 제목 아래 빈 줄에 캐럿. 주제 페이지 주소는 take-26 end-state.json
//   trashPage  : 촬영 전용 페이지(config.page)를 하위 페이지째 Notion 휴지통으로 이동(영구 삭제 아님). 처음부터 다시 찍을 때만
//   state      : 읽기 전용 — 블록 목록 · 캐럿 · 사이드바 · 오류 문구
const fs=await import('node:fs/promises');
const HERE=decodeURIComponent(new URL('.',import.meta.url).pathname).replace(/^\/([A-Za-z]:)/,'$1');
const CFG=JSON.parse(await fs.readFile(HERE+'config.json','utf8'));

async function page(){
 const task=await taskSpace(CFG.space);const p=task.page('p1');
 await p.cdp('Emulation.setDeviceMetricsOverride',{width:CFG.viewport.width,height:CFG.viewport.height,deviceScaleFactor:1,mobile:false});
 return p;
}
const onShootingPage=async p=>{if(!(await p.url()).includes(CFG.page))throw Error('Not on the shooting page '+CFG.page+': '+(await p.url()));};
const WORK=decodeURIComponent(new URL(CFG.work+'/','file:///'+HERE).pathname).replace(/^\/([A-Za-z]:)/,'$1');
// 블록 손잡이 메뉴의 '삭제'(글 블록) 또는 '휴지통으로 이동'(하위 페이지 블록)으로 블록 하나를 지운다(role=option, 단축키 글자가 붙음). Notion은 블록을 다시 그려 임시 속성이
// 사라지므로(2026-10-23 실측) 매번 글자로 블록을 다시 찾는다. pageLink=true면 그 이름의 하위 페이지 블록.
const blockRect=(p,text,pageLink)=>p.evaluate(({text,pageLink})=>{
 const el=pageLink?[...document.querySelectorAll('.notion-page-content a')].find(a=>a.textContent.trim()===text):[...document.querySelectorAll('[contenteditable=true][role=textbox]')].find(e=>e.textContent===text);
 const b=el?.closest('[data-block-id]');if(!b)return null;const r=b.getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height};},{text,pageLink});
async function deleteBlock(p,text,pageLink){
 await p.keyboard.press('Escape');await p.waitForTimeout(300);
 let b=await blockRect(p,text,pageLink);if(!b)throw Error('Block not found: '+text);
 // 화면 밖 블록은 손잡이가 안 나온다(2026-10-23 실측): 휠로 화면 가운데쯤에 들인다.
 for(let i=0;i<6;i++){const vh=await p.evaluate(()=>innerHeight);if(b.y>=80&&b.y+b.h<=vh-40)break;await p.mouse.move(b.x+60,Math.min(vh-60,Math.max(120,vh/2)),{steps:2});await p.mouse.wheel(0,Math.max(-500,Math.min(500,b.y-vh/2)));await p.waitForTimeout(350);b=await blockRect(p,text,pageLink);}
 await p.mouse.move(b.x+Math.min(60,b.w/2),b.y+Math.min(b.h,40)/2,{steps:4});await p.waitForTimeout(400);
 const h=await p.evaluate(b=>{const hs=[...document.querySelectorAll('[aria-label="드래그하여 이동하고 클릭하여 메뉴를 여세요"]')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&r.x<b.x+60&&Math.abs(r.y+r.height/2-(b.y+Math.min(b.h,40)/2))<30;});if(hs.length!==1)throw Error("Block handle "+hs.length+" near "+JSON.stringify(b));const r=hs[0].getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};},b);
 await p.mouse.move(h.x,h.y,{steps:3});await p.mouse.click(h.x,h.y);
 await p.waitForFunction(()=>[...document.querySelectorAll('[role=option],[role=menuitem]')].some(e=>e.checkVisibility({checkVisibilityCSS:true})&&/^(삭제|휴지통으로 이동)/.test(e.textContent.trim())),undefined,{timeout:6000});
 const d=await p.evaluate(()=>{const e=[...document.querySelectorAll('[role=option],[role=menuitem]')].find(e=>e.checkVisibility({checkVisibilityCSS:true})&&/^(삭제|휴지통으로 이동)/.test(e.textContent.trim()));const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};});
 await p.mouse.move(d.x,d.y,{steps:3});await p.mouse.click(d.x,d.y);
}
async function cut27(p){
 const topic=JSON.parse(await fs.readFile(WORK+'/take-26/end-state.json','utf8')).url;
 if(!(await p.url()).startsWith(topic.split('?')[0]))await p.goto(topic);
 await p.waitForFunction(()=>[...document.querySelectorAll('[contenteditable=true][role=textbox]')].some(e=>e.textContent==='나의 페이지'),undefined,{timeout:20000});
 const has=()=>p.evaluate(()=>[...document.querySelectorAll('.notion-page-content a')].some(a=>a.textContent.trim()==='첫 페이지 꾸미기'));
 if(await has()){
  await deleteBlock(p,'첫 페이지 꾸미기',true);
  await p.waitForFunction(()=>![...document.querySelectorAll('.notion-page-content a')].some(a=>a.textContent.trim()==='첫 페이지 꾸미기'),undefined,{timeout:6000});
 }
 // 「나의 페이지」 바로 다음이 빈 줄이면 그 줄, 아니면 제목 끝에서 Enter. 제목이 화면 밖이면 먼저 휠로 들인다.
 for(let i=0;i<6;i++){const r=await p.evaluate(()=>{const h=[...document.querySelectorAll('[contenteditable=true][role=textbox]')].find(e=>e.textContent==='나의 페이지').getBoundingClientRect();return{y:h.y,vh:innerHeight};});if(r.y>=80&&r.y<=r.vh-120)break;await p.mouse.move(300,r.vh/2,{steps:2});await p.mouse.wheel(0,Math.max(-500,Math.min(500,r.y-r.vh/2)));await p.waitForTimeout(350);}
 const next=await p.evaluate(()=>{const h=[...document.querySelectorAll('[contenteditable=true][role=textbox]')].find(e=>e.textContent==='나의 페이지');const hb=h.closest('[data-block-id]');const nb=hb.nextElementSibling;const ne=nb?.querySelector('[contenteditable=true]');
  if(ne&&!ne.textContent){const r=ne.getBoundingClientRect();return{empty:true,x:r.x+8,y:r.y+r.height/2};}
  const w=document.createTreeWalker(h,NodeFilter.SHOW_TEXT);let n,l;while(n=w.nextNode())l=n;const r=document.createRange();r.setStart(l,l.length-1);r.setEnd(l,l.length);const b=r.getBoundingClientRect();return{empty:false,x:b.right+1,y:b.top+b.height/2};});
 await p.mouse.click(next.x,next.y);await p.waitForTimeout(400);
 if(!next.empty){await p.keyboard.press('End');await p.keyboard.press('Enter');await p.waitForTimeout(600);}
 const s=await state(p);
 if(!s.caret?.empty||s.caret.inNote||s.banner)throw Error('cut27 incomplete '+JSON.stringify(s));
 return {...s,url:await p.url()};
}
const state=p=>p.evaluate(()=>{
 const a=getSelection().anchorNode;const el=a?.nodeType===1?a:a?.parentElement;const ce=el?.closest('[contenteditable=true]');
 return{blocks:[...document.querySelectorAll('[contenteditable=true][role=textbox]')].filter(e=>e.tagName!=='H1').map(e=>(e.closest('[role=note]')?'in:':'out:')+e.textContent.slice(0,20)),
  caret:ce?{inNote:!!el.closest('[role=note]'),empty:!ce.textContent,title:ce.tagName==='H1'}:null,
  sidebarOpen:[...document.querySelectorAll('[aria-label="사이드바 닫기"]')].some(e=>e.checkVisibility({checkVisibilityCSS:true})),
  banner:/문제가 발생했습니다/.test(document.body.innerText)};});

async function cut25(p){
 await onShootingPage(p);
 const notes=await p.evaluate(()=>document.querySelectorAll('[role=note]').length);
 for(let i=0;i<notes;i++){
  await p.hover('[role=note] >> nth=0');await p.waitForTimeout(400);
  const h=await p.evaluate(()=>{const n=document.querySelector('[role=note]').getBoundingClientRect();const hs=[...document.querySelectorAll('[aria-label="드래그하여 이동하고 클릭하여 메뉴를 여세요"]')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&r.x<n.x&&Math.abs(r.y-n.y)<40;});if(hs.length!==1)throw Error('Callout handle '+hs.length);const r=hs[0].getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};});
  await p.mouse.click(h.x,h.y);
  // 블록 메뉴 항목은 role=option(또는 menuitem). '삭제Del' 처럼 단축키가 붙는다.
  await p.waitForFunction(()=>[...document.querySelectorAll('[role=option],[role=menuitem]')].some(e=>e.checkVisibility({checkVisibilityCSS:true})&&/^(삭제|휴지통으로 이동)/.test(e.textContent.trim())),undefined,{timeout:6000});
  await p.evaluate(()=>[...document.querySelectorAll('[role=option],[role=menuitem]')].find(e=>e.checkVisibility({checkVisibilityCSS:true})&&/^(삭제|휴지통으로 이동)/.test(e.textContent.trim())).setAttribute('data-restore','del'));
  await p.click('[data-restore="del"]');
  await p.waitForFunction(n=>document.querySelectorAll('[role=note]').length===n,notes-i-1,{timeout:6000});
 }
 if(await p.evaluate(()=>[...document.querySelectorAll('[aria-label="사이드바 닫기"]')].some(e=>e.checkVisibility({checkVisibilityCSS:true}))))await p.click('[aria-label="사이드바 닫기"]');
 const empty=await p.evaluate(()=>{const e=[...document.querySelectorAll('[contenteditable=true][role=textbox]')].find(e=>e.tagName!=='H1'&&!e.textContent);if(!e)return null;const r=e.getBoundingClientRect();return{x:r.x+8,y:r.y+r.height/2};});
 if(empty)await p.mouse.click(empty.x,empty.y);
 else{
  const q=await p.evaluate(()=>{const e=[...document.querySelectorAll('[contenteditable=true][role=textbox]')].find(e=>e.textContent.startsWith('관심 있는 주제를 모으고'));if(!e)throw Error('Intro missing');const w=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);let n,l;while(n=w.nextNode())l=n;const r=document.createRange();r.setStart(l,l.length-1);r.setEnd(l,l.length);const b=r.getBoundingClientRect();return{x:b.right+1,y:b.top+b.height/2};});
  await p.mouse.click(q.x,q.y);await p.waitForTimeout(400);await p.keyboard.press('End');await p.keyboard.press('Enter');
 }
 await p.waitForTimeout(600);
 const s=await state(p);
 // 캐럿 판정은 화면 상태로 한다(블록 경계 판정이 엄격하면 맞는 상태도 실패로 본다 — 2026-10-23 실측).
 if(s.blocks.some(b=>b.startsWith('in:'))||s.sidebarOpen||s.banner||!s.caret?.empty||s.caret.inNote)throw Error('cut25 incomplete '+JSON.stringify(s));
 return s;
}
async function noteTail(p){
 await onShootingPage(p);
 for(let i=0;i<3;i++){const s=await state(p);if(s.caret?.inNote&&!s.caret.empty)break;if(!s.caret?.empty)throw Error('Caret not in an empty line '+JSON.stringify(s));await p.keyboard.press('Backspace');await p.waitForTimeout(500);}
 const s=await state(p);if(!s.caret?.inNote||s.caret.empty)throw Error('noteTail incomplete '+JSON.stringify(s));
 return s;
}
async function trashPage(p){
 if(CFG.page===CFG.protect)throw Error('config.page is the protected original');
 await p.goto('https://app.notion.com/p/'+CFG.page);
 await p.waitForFunction(()=>!!document.querySelector('h1[contenteditable=true]'),undefined,{timeout:20000});
 if((await p.url()).includes(CFG.protect))throw Error('Refusing: protected original');
 await p.click('[role=button][aria-label="작업"]');
 await p.waitForSelector('text=휴지통으로 이동',{state:'visible',timeout:6000});
 await p.click('text=휴지통으로 이동');
 await p.goto('https://app.notion.com/p/'+CFG.page);await p.waitForTimeout(3000);
 const trashed=await p.evaluate(()=>/휴지통으로 이동했습니다/.test(document.body.innerText));
 if(!trashed)throw Error('Trash banner not seen for '+CFG.page);
 return {trashed:CFG.page};
}
export async function restore(kind){
 const p=await page();
 if(kind==='trashPage')return trashPage(p);
 if(kind==='state')return state(p);
 if(kind==='cut25')return cut25(p);
 if(kind==='noteTail')return noteTail(p);
 if(kind==='cut27')return cut27(p);
 throw Error('Unknown restore kind '+kind);
}
