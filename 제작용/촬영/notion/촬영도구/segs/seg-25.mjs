// 구간25: 다운로드 페이지(누르지 않고 위치만) → 로그인된 작업 화면 → 새 촬영 페이지 → 제목·소개 → 안내 상자.
// 시작 상태: 다운로드 페이지. 종료 상태: 새 촬영 페이지, 안내 상자 두 번째 줄 입력 직후(상자 안 캐럿).
import {v10} from '../ui.mjs';
export default async ctx=>{
 const c=await v10(ctx);const FINAL=ctx.protect;
 const vp=()=>c.serial(()=>c.raw.evaluate(()=>({w:innerWidth,h:innerHeight})));
 // 녹화 전 준비
 await c.serial(()=>c.raw.goto('https://www.notion.com/ko/desktop'));
 await c.serial(()=>c.raw.waitForSelector('a[aria-label="Windows용 Notion 다운로드"]',{timeout:20000}));
 let v=await vp();const start={x:Math.round(v.w*.62),y:Math.round(v.h*.62)};
 await c.installPointer(start);await c.serial(()=>c.raw.mouse.move(start.x,start.y,{steps:1}));c.setPos(start);await c.sleep(800);
 await c.begin();
 await c.say('live-opening');
 await c.say('live-download',async()=>{const q=await c.locate('css','a[aria-label="Windows용 Notion 다운로드"]');await c.move(q.x,q.y);},{pointFrac:0.25});
 await c.say('live-web-choice');
 await c.say('live-workspace',async()=>{await c.navigate('https://app.notion.com/p/redmustard/'+FINAL);await c.waitFor(()=>!!document.querySelector('h1[contenteditable=true]'),20000);});
 // Notion은 상단 막대를 숨긴 채 열릴 수 있다. 사이드바가 이미 열려 있지 않으면, 왼쪽 위로 가서 버튼이 나타나면 누른다.
 const sidebarOpen=()=>c.serial(()=>c.raw.evaluate(()=>[...document.querySelectorAll('[aria-label="사이드바 닫기"]')].some(e=>e.checkVisibility({checkVisibilityCSS:true}))));
 if(!(await sidebarOpen()))await c.say('live-sidebar-open',async()=>{
  v=await vp();await c.move(Math.round(v.w*.03),Math.round(v.h*.05));
  await c.waitFor(()=>[...document.querySelectorAll('[aria-label="사이드바 열기"],[aria-label="사이드바 닫기"]')].some(e=>e.checkVisibility({checkVisibilityCSS:true})),6000);
  if(!(await sidebarOpen()))await c.click('aria','사이드바 열기');
 });
 for(const id of ['N02-v008','N02-v009','N02-v010'])await c.say(id);
 v=await vp();
 await c.say('N02-v011',()=>c.move(Math.round(v.w*.13),Math.round(v.h*.5)));
 await c.say('N02-v012',()=>c.move(Math.round(v.w*.62),Math.round(v.h*.5)));
 await c.say('N02-v013');
 // 클릭에 반응이 없던 실측(take-25c)이 있어, 2.5초 안에 메뉴나 새 페이지가 없으면 같은 자리를 한 번 더 누르고 기록한다.
 const opened=()=>c.serial(()=>c.raw.evaluate(f=>!location.href.includes(f)||[...document.querySelectorAll('[role=menuitem],[role=option]')].some(e=>e.textContent.trim().startsWith('페이지')&&e.checkVisibility({checkVisibilityCSS:true})),FINAL));
 await c.say('N03-v001',async()=>{
  await c.click('aria','새 페이지');
  for(let n=0;n<12&&!(await opened());n++)await c.sleep(200);
  if(!(await opened())){await c.fs.appendFile(c.out+'/reclicks.jsonl',JSON.stringify({target:'새 페이지',reason:'no menu or page within 2.5s'})+'\n');await c.click('aria','새 페이지');
   for(let n=0;n<12&&!(await opened());n++)await c.sleep(200);if(!(await opened()))throw Error('New page button did not respond to two clicks');}
 });
 const direct=await c.serial(()=>c.raw.evaluate(f=>!location.href.includes(f)&&!!document.querySelector('h1[contenteditable=true]'),FINAL));
 if(!direct)await c.say('live-create-option',async()=>{await c.click('menu','페이지');await c.waitFor(()=>!!document.querySelector('h1[contenteditable=true]'));});
 const url=await c.serial(()=>c.raw.url());if(url.includes(FINAL))throw Error('New page did not open');
 await c.fs.writeFile(c.out+'/new-page-url.txt',url);
 await c.say('N03-v003',()=>c.click('title',''));
 await c.say('N03-v004',()=>c.type('내 학습 노트'));
 await c.say('N03-v005',()=>c.key('Enter'));
 for(const id of ['N03-v006','N03-v007','N03-v008','N03-v009','N03-v010'])await c.say(id);
 await c.say('live-sidebar-close',()=>c.click('aria','사이드바 닫기'));
 for(const id of ['N04-v004','N04-v006','N04-v007'])await c.say(id);
 await c.say('N04-v008',()=>c.click('body',''));
 await c.say('N05-v001');
 await c.say('N05-v002',()=>c.type('관심 있는 주제를 모으고, 배운 내용을 나만의 방식으로 쌓아 갑니다.'),{async:true});
 await c.say('N05-v003',null,{overlap:true});
 await c.say('N05-v004',()=>c.key('Enter'));
 await c.say('N05-v005',async()=>{
  const q=await c.serial(()=>c.raw.evaluate(()=>{const e=[...document.querySelectorAll('[contenteditable=true][role=textbox]')].find(e=>e.textContent.startsWith('관심 있는 주제를 모으고'));if(!e)throw Error('Intro line missing');const r=e.getBoundingClientRect();return{x:r.x+5,y:r.y+r.height/2};}));await c.move(q.x,q.y);
 });
 for(const id of ['N05-v006','N05-v007','N05-v008'])await c.say(id);
 await c.say('N05-v009',()=>c.click('body',''));await c.say('N05-v010');
 await c.say('N06-v002',()=>c.type('/'));
 await c.say('live-callout-search',()=>c.type('콜아웃'));
 await c.say('N06-v003',()=>c.click('menu','콜아웃'));
 await c.waitFor(()=>!!document.querySelector('[role=note]'));
 await c.say('N06-v005');await c.say('live-bold-on',()=>c.key('Control+b'));
 await c.say('N06-v006',()=>c.type('하나의 주제에서, 나만의 지식으로'));
 await c.say('live-bold-off',()=>c.key('Control+b'));
 await c.say('N06-v007',()=>c.key('Shift+Enter'));await c.say('N06-v008');
 await c.say('N06-v009',()=>c.type('카드 하나에 주제 하나. 카드 안에는 글과 자료를 자유롭게 담고, 내용이 늘어나면 하위 페이지로 나누세요.'));
 return 'seg-25 done';
};
