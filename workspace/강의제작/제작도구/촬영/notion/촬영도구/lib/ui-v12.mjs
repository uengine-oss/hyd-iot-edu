// v12 조작 층(새 대본 다시 찍기). ui.mjs의 v10(검증된 포인터 · gate · 클릭 · 손잡이 · 색 메뉴 · 파일 창 · 속성 · 보기 설정 · 재클릭 기록) 위에
//  ① 화면 안에 들인 뒤 조작(영상 V-14): 누르기 · 짚기 · 손잡이 · 메뉴 조작 직전에 대상 사각형이 보이는 영역(뷰포트와 실제로 스크롤되는 조상의
//     교집합)의 위아래 여유 안에 온전히 있는지 재고, 아니면 그 스크롤 영역 위에서 휠로 가운데쯤 들인다. c.locate · 링크 · 글 끝 · 글 고르기 ·
//     역할 · 대화상자 이름 줄 · 손잡이 · 눈 단추와 새 조작이 모두 inView를 거친다.
//  ② 큐 안 시점 c.at(비율 | 'point'), ③ 새 동선(단축키 블록 · 아이콘 · 커버 · 가이드 복사 · 탭 오가기 · 내보내기 · 파일 다시 열기)을 더한다.
// 구간 모듈은 parts(덮는 단계)와 ops(c)(조작 이름 → 손잡이)를 내보내고, playSegment가 큐 파일(source-cues-v12.json)의 차례대로 말하며 손잡이를 부른다.
import {v10, installPointerInPage, labelTargetInPage} from '../ui.mjs';
import {hideProperty, state as eyeState} from './property-visibility.mjs';

export const BLUE='rgb(229, 242, 252)', GRAY='rgb(249, 248, 247)';
export const EMOJI_KEYS=['홈','Notion 익히기','첫 페이지 꾸미기','페이지 연결하기','지식 자산화','새 주제','나만의 독서 기록','다음에 읽을 책'];

// 큐 파일에서 한 part({step, from?, until?})가 덮는 큐. from · until은 조작 이름(until은 그 조작의 큐 앞에서 끊는다).
export function partCues(cues,part){
 let xs=cues.filter(c=>c.step===part.step);
 if(!xs.length)throw Error('No cues for step '+part.step);
 if(part.from){const i=xs.findIndex(c=>c.op===part.from);if(i<0)throw Error('Step '+part.step+' has no op '+part.from);xs=xs.slice(i);}
 if(part.until){const i=xs.findIndex(c=>c.op===part.until);if(i<0)throw Error('Step '+part.step+' has no op '+part.until);xs=xs.slice(0,i);}
 return xs;
}

// 대상의 보이는 정도(페이지에서 실행). 실제로 스크롤되는 조상만 영역으로 친다(overflow:hidden 감싸개는 대상에 딱 붙어 있어 기준이 못 된다).
function viewBox({sel,margin}){
 const e=document.querySelector(sel);if(!e)return{missing:true};
 const b=e.getBoundingClientRect();
 let top=0,bottom=innerHeight,left=0,right=innerWidth,sy=null,sx=null,syEl=null;
 for(let a=e.parentElement;a&&a!==document.body&&a!==document.documentElement;a=a.parentElement){
  const s=getComputedStyle(a),q=a.getBoundingClientRect();
  if(/(auto|scroll)/.test(s.overflowY)&&a.scrollHeight>a.clientHeight+2){top=Math.max(top,q.top);bottom=Math.min(bottom,q.bottom);if(!sy){sy={x0:q.left,x1:q.right,y0:q.top,y1:q.bottom};syEl=a;}}
  if(/(auto|scroll)/.test(s.overflowX)&&a.scrollWidth>a.clientWidth+2){left=Math.max(left,q.left);right=Math.min(right,q.right);sx??={x0:q.left,x1:q.right,y0:q.top,y1:q.bottom};}
 }
 const se=document.scrollingElement;
 if(!sy&&se&&se.scrollHeight>innerHeight+2){sy={x0:0,x1:innerWidth,y0:0,y1:innerHeight};syEl=se;}
 if(syEl){sy.at=syEl.scrollTop;sy.max=syEl.scrollHeight-syEl.clientHeight;}
 if(!sx&&se&&se.scrollWidth>innerWidth+2)sx={x0:0,x1:innerWidth,y0:0,y1:innerHeight};
 const my=sy?Math.max(4,Math.min(margin,(bottom-top-b.height)/2)):0,mx=sx?Math.max(4,Math.min(24,(right-left-b.width)/2)):0;
 return{b:{top:b.top,bottom:b.bottom,left:b.left,right:b.right,h:b.height,w:b.width},area:{top,bottom,left,right},sy,sx,margin,
  okY:b.height>0&&b.top>=top+my-0.5&&b.bottom<=bottom-my+0.5,okX:b.left>=left+mx-0.5&&b.right<=right-mx+0.5,
  inside:b.height>0&&b.top>=top-0.5&&b.bottom<=bottom+0.5&&b.left>=left-0.5&&b.right<=right+0.5};
}

// 휠 굴리기: 브라우저는 휠 한 번을 몇 프레임에 걸쳐 부드럽게 움직이므로, 한 번에 TICK px 이하로 나눠 쉼 없이 잇달아 굴린다.
// 2026-11-12 측정(같은 쪽 · 같은 받기 고리): 휠 한 번 300px = 약 130ms · 녹화 프레임 간격 83ms 이하. 틱 사이에 40ms 쉼과 커서 흔들기를 넣으면
// ego 호출 하나가 약 200ms라 77px씩 끊겨 움직였고(찔끔찔끔 — V-14 금지), 일정 속도 제스처(Input.synthesizeScrollGesture)는 그동안 녹화 프레임이
// 0.4~0.6초 멈췄다. 그래서 둘 다 쓰지 않는다. 커서는 사람 손처럼 굴리는 동안 그 자리에 둔다.
const TICK=250;
export async function wheelSmooth(c,dx,dy){
 const n=Math.max(1,Math.ceil(Math.max(Math.abs(dx),Math.abs(dy))/TICK));
 for(let k=0;k<n;k++)await c.serial(()=>c.raw.mouse.wheel(Math.round(dx/n),Math.round(dy/n)));
}

// 화면 안에 들이기. 들였으면 true(다시 재야 할 때), 처음부터 안에 있었으면 false. 휠을 굴려도 대상이 움직이지 않으면(이미 끝까지 굴렸거나
// 위 막대처럼 고정된 대상) 온전히 보일 때는 그대로 두고, 잘려 있으면 대상을 대고 멈춘다.
// 사용자 2026-11-13 「강박을 가지지 마 … 유연하게」: 대상 일부라도 누르기에 넉넉히(가로 24px · 세로 14px 넘게) 보이면 들이지 못해도 멈추지 않고
// 그 보이는 부분을 쓴다(inview.jsonl에 남긴다). 대상이 화면에 아예 없을 때만 멈춘다.
const enough=r=>{const w=Math.min(r.b.right,r.area.right)-Math.max(r.b.left,r.area.left),h=Math.min(r.b.bottom,r.area.bottom)-Math.max(r.b.top,r.area.top);return w>24&&h>14;};
async function soft(c,sel,r,why){if(!enough(r))return false;await c.fs.appendFile(c.out+'/inview.jsonl',JSON.stringify({cue:c.ctx?.cue?.id,sel,why,box:r.b})+String.fromCharCode(10));return true;}
export async function inView(c,sel,margin=56,tries=14,maxStep=700){
 let last=null,lastR=null;const trace=[];   // 못 들이면 반복마다 [대상 top, 스크롤 위치, 굴린 양]을 오류에 담는다
 for(let i=0;i<tries;i++){
  const r=await c.serial(()=>c.raw.evaluate(viewBox,{sel,margin}));
  if(r.missing)throw Error('inView: target missing '+sel);
  if(r.okY&&r.okX)return i>0;lastR=r;
  if(last&&Math.abs(last.top-r.b.top)<1&&Math.abs(last.left-r.b.left)<1){if(r.inside||await soft(c,sel,r,'scroll does not move it'))return i>1;throw Error('inView: '+sel+' is cut off and scrolling does not move it '+JSON.stringify(r.b));}
  last=r.b;
  let dx=0,dy=0,box;
  if(!r.okY){
   if(!r.sy){if(await soft(c,sel,r,'cut off vertically, nothing scrolls'))return i>0;throw Error('inView: '+sel+' is cut off vertically and nothing scrolls '+JSON.stringify(r.b));}
   const span=r.area.bottom-r.area.top;box=r.sy;
   dy=r.b.h>span-2*r.margin?r.b.top-(r.area.top+r.margin):(r.b.top+r.b.bottom)/2-(r.area.top+r.area.bottom)/2;
   if((dy<0&&r.sy.at<=0)||(dy>0&&r.sy.at>=r.sy.max-1)){if(r.inside||await soft(c,sel,r,'end of scroll area'))return i>0;throw Error('inView: '+sel+' is cut off at the end of its scroll area '+JSON.stringify(r.b));}
  }else{
   if(!r.sx){if(await soft(c,sel,r,'cut off horizontally, nothing scrolls'))return i>0;throw Error('inView: '+sel+' is cut off horizontally and nothing scrolls '+JSON.stringify(r.b));}
   box=r.sx;dx=(r.b.left+r.b.right)/2-(r.area.left+r.area.right)/2;
  }
  const cl=v=>Math.max(-maxStep,Math.min(maxStep,Math.round(v)))||(v<0?-1:1);
  const px=Math.max(box.x0+24,Math.min(box.x1-24,r.b.left+Math.min(60,r.b.w/2)));
  const py=Math.max(box.y0+24,Math.min(box.y1-24,dy?(box.y0+box.y1)/2:(r.b.top+r.b.bottom)/2));
  trace.push([Math.round(r.b.top),r.sy?Math.round(r.sy.at):null,dy?cl(dy):cl(dx)]);
  await c.glide(px,py);
  await wheelSmooth(c,dx?cl(dx):0,dy?cl(dy):0);
  await c.sleep(260);
 }
 if(lastR&&await soft(c,sel,lastR,'could not center after '+tries+' tries'))return true;
 throw Error('inView: could not bring '+sel+' into view — '+JSON.stringify(trace).slice(0,900));
}

// 요소 하나에 표시를 달고 선택자를 돌려준다(페이지에서 실행). Notion은 편집 영역([contenteditable=true]) 안 요소의 낯선 속성을 바로 지우므로(리허설 r4~r6 실측),
// 그 안의 요소는 표시 대신 Notion 자신의 id · data-block-id에 붙인 구조 선택자를 돌려준다. spec: css · text(같음) · has(글이 들어 있음, 배열이면 모두) · name(aria-label 또는 글) ·
// scope('region' | 'dialog' | css) · notIn(css) · top(위 막대만) · first · last · nth. 화면 밖 요소도 찾는다(들이는 일은 inView). 0개나 여럿이면 멈춘다.
function markInPage(spec){
 const {css,text,has,name,scope,notIn,top,first,last,nth}=spec;
 const vis=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&e.checkVisibility({checkVisibilityCSS:true});};
 const root=scope==='region'?[...document.querySelectorAll('[role=region]')].filter(vis).at(-1):scope==='dialog'?[...document.querySelectorAll('[role=dialog]')].filter(vis).at(-1):scope?document.querySelector(scope):document;
 if(!root)throw Error('mark: scope missing '+scope);
 const norm=s=>(s||'').replace(/\s+/g,' ').trim();
 let es=[...root.querySelectorAll(css||'*')].filter(vis);
 if(notIn)es=es.filter(e=>!e.closest(notIn));
 if(top)es=es.filter(e=>e.getBoundingClientRect().top<65);   // 위 막대(경로 줄)만
 if(text!=null)es=es.filter(e=>norm(e.textContent)===text);
 if(name!=null)es=es.filter(e=>e.getAttribute('aria-label')===name||norm(e.textContent)===name);
 for(const h of has==null?[]:[].concat(has))es=es.filter(e=>norm(e.textContent).includes(h));
 if(text!=null||has!=null||name!=null)es=es.filter(e=>!es.some(o=>o!==e&&e.contains(o)));
 if(first)es=es.slice(0,1);if(last)es=es.slice(-1);if(nth!=null)es=es.slice(nth,nth+1);
 if(es.length!==1)throw Error('mark: '+JSON.stringify(spec)+' matched '+es.length);
 const pathOf=e=>{if(!e.closest('[contenteditable=true]'))return null;const parts=[];let a=e;while(a&&a!==document.documentElement){const bid=a.getAttribute('data-block-id');const own=a.id?'#'+CSS.escape(a.id):bid?a.tagName.toLowerCase()+'[data-block-id="'+bid+'"]':null;if(own&&document.querySelectorAll(own).length===1){parts.unshift(own);break;}parts.unshift(a.tagName.toLowerCase()+':nth-child('+([...a.parentElement.children].indexOf(a)+1)+')');a=a.parentElement;}const sel=parts.join(' > ');if(document.querySelector(sel)!==e)throw Error('Structural selector does not resolve back: '+sel);return sel;};
 const path=pathOf(es[0]);if(path)return path;
 // 이미 표시가 있으면 그 표시를 쓴다: 덮어쓰면 그 표시로 찾던 쪽(labelSel → c.click('css', …) 앞의 preView)이 대상을 잃는다(리허설 r26 s21-05).
 const had=es[0].getAttribute('data-v12');if(had)return '[data-v12="'+had+'"]';
 const t='m'+Math.random().toString(36).slice(2,10);es[0].setAttribute('data-v12',t);return '[data-v12="'+t+'"]';
}

function pointOf(sel){const e=document.querySelector(sel);if(!e)throw Error('Point target missing '+sel);const r=e.getBoundingClientRect();return{x:r.x+Math.min(45,r.width/2),y:r.y+r.height/2,cx:r.x+r.width/2};}

export async function v12(ctx){
 const c=await v10(ctx);
 const {sleep}=ctx;
 c.ctx=ctx;c.state=ctx.sess.state;c.out=ctx.out;
 c.mark=async(spec,timeout=4000)=>{const t0=Date.now();for(;;){try{return await c.serial(()=>c.raw.evaluate(markInPage,spec));}catch(e){if(Date.now()-t0>timeout||!/matched 0|scope missing/.test(String(e)))throw e;await sleep(200);}}};
 c.inView=(sel,m,t)=>inView(c,sel,m,t);
 // 대본이 말하는 화면이 없을 때(대본과 화면이 다름): 녹화에서는 멈추고, 리허설에서는 <구간>/script-gap.jsonl에 적고 다음 조작으로 간다(메인이 사용자에게 물을 목록).
 c.scriptGap=async(what,detail={})=>{const row={cue:ctx.cue?.id,what,...detail};if(!ctx.rehearsal)throw Error('Script and screen differ at '+row.cue+': '+what);await c.fs.appendFile(c.out+'/script-gap.jsonl',JSON.stringify(row)+String.fromCharCode(10));};
 // Notion 화면 말: 같은 계정 · 같은 쿠키(ko-KR)인데도 앱을 새로 불러올 때마다 영어(lang=en)로 그려지는 일이 섞인다(길뚫기 2026-11-12: 새로고침 열한 번 중
 // 일곱 번이 영어, 「Notion 열기」 여섯 번 중 두 번이 영어 — 언어 재정의 CDP로도 그대로). 녹화 밖(구간 준비)에서는 한국어로 그려질 때까지 다시 불러오고,
 // 녹화 안에서 새로 불러온 화면이 영어면 그 take는 쓸 수 없으니 멈춘다.
 // 문서 언어가 ko여도 글 일부만 영어로 섞여 나올 때가 있다(리허설 r17: 속성 칸 아래 「Add a property」) — 노션의 영어 UI 글이 보이면 en으로 친다.
 // 영어 낱말 판정은 그 글을 가진 가장 안쪽 요소로 한다(단추는 그림 + 글이라 자식이 있다). 데이터베이스 쪽의 「Add a property」는 한국어 화면에서도 늘 영어라(Notion 미번역 —
 // 리허설 r32에서 여덟 번 다시 불러도 같고, 「속성 추가」로 나온 적이 없다) 판정에 넣지 않는다.
 c.lang=()=>c.serial(()=>c.raw.evaluate(()=>{if(document.documentElement.lang!=='ko')return document.documentElement.lang||'?';const en=['New page','Share','Add icon','Add cover'];return [...document.querySelectorAll('[aria-label],div,span')].some(e=>(en.includes(e.getAttribute('aria-label'))||(en.includes(e.textContent.trim())&&![...e.children].some(k=>k.textContent.trim()===e.textContent.trim())))&&e.checkVisibility({checkVisibilityCSS:true}))?'en(mixed)':'ko';}));
 c.ensureKorean=async(tries=8)=>{for(let i=0;i<tries;i++){if((await c.lang())==='ko')return i;const u=await c.serial(()=>c.raw.url());
   await c.serial(()=>c.raw.goto(u,{timeout:150000,waitUntil:'domcontentloaded'})).catch(()=>{});await c.serial(()=>c.raw.waitForFunction(()=>!!document.querySelector('h1[contenteditable=true]'),undefined,{timeout:40000})).catch(()=>{});await sleep(2500);}
  if((await c.lang())!=='ko')throw Error('Notion stays English after '+tries+' reloads');return tries;};
 // 큐 안 시점: 다음 누르기 · 입력이 그 큐 말의 f 비율(또는 마지막 문장 시작 'point')에서 일어나게 한다(약 250ms 앞).
 c.at=f=>{const cue=ctx.cue;if(!cue||!ctx.cueT0)throw Error('c.at outside a cue');const frac=f==='point'?cue.point:f;ctx.commitAt=ctx.cueT0+Math.round(ctx.cueDur*frac)-250;};

 // ① 화면 안에 들인 뒤 조작 — v10의 찾기 · 글 · 링크 · 역할 · 손잡이 경로를 감싼다.
 const baseLocate=c.locate;
 // Notion이 찾은 요소를 그 사이 다시 그리면(새 페이지 제목 등) 표시가 사라진다 — 그때는 다시 찾는다(네 번까지, 그래도 없으면 멈춘다).
 // 먼저 v12 방식으로 화면 안에 들인다: 옛 찾기(ui-robust → ui.mjs targetPoint)는 화면 밖 대상을 굴려 들이다가 편집 영역 안 대상의 표시가 지워지거나
 // 붙은 목차처럼 안 움직이는 대상에서 멈춘다(리허설 r23 · r24). 하나로 정해지지 않으면(0개 · 여럿) 여기서는 건너뛰고 옛 찾기에 맡긴다.
 const preSpec={text:v=>({css:'div,span,a,button',text:v}),aria:v=>({css:'[role=button],button',name:v}),css:v=>({css:v}),title:()=>({css:'h1[contenteditable=true]',last:true})};
 const preView=async(kind,value)=>{const f=preSpec[kind];if(!f)return;let sel=null;try{sel=await c.serial(()=>c.raw.evaluate(markInPage,f(value)));}catch(e){return;}await inView(c,sel);};
 const locateOnce=async(kind,value)=>{await preView(kind,value);for(let i=0;i<4;i++){let q=await baseLocate(kind,value);
   // 메뉴 · 선택지는 쪽을 굴리지 않는다(쪽을 굴리는 사이 슬래시 메뉴가 닫혔다 — k12). 다만 메뉴 안의 자기 스크롤(색 목록처럼 길게 잘린 메뉴) 안에서는 들인다
   // (k14 s17-10: 들이지 않고 잘린 「파란색 배경」 좌표로 가다 메뉴 밖으로 나가 하위 메뉴가 닫혔다).
   const ownScroll=kind!=='menu'||await c.serial(()=>c.raw.evaluate(s=>{const e=document.querySelector(s);for(let p=e?.parentElement;p&&p!==document.body;p=p.parentElement){const st=getComputedStyle(p);if(/(auto|scroll)/.test(st.overflowY)&&p.scrollHeight>p.clientHeight+2)return true;if(p.matches('[role=dialog],[role=menu],[role=listbox]'))return false;}return false;},q.selector));
   try{if(ownScroll&&await inView(c,q.path||q.selector))q=await baseLocate(kind,value);return q;}catch(e){if(!/target missing/.test(String(e))||i===3)throw e;await sleep(250);}}};
 // 대상을 못 찾으면 사람처럼 한 번 더 찾아 누른다(사용자 2026-11-13 「잘못 클릭했으면 다시 클릭하면 되는 거고요」) — 다시 찾은 일은 reclicks.jsonl에 남기고,
 // 그래도 못 찾으면 멈춘다.
 c.locate=async(kind,value)=>{try{return await locateOnce(kind,value);}catch(e){if(!/not visible|missing|Ambiguous|Cannot bring/i.test(String(e)))throw e;
   // 대상을 가리는 뜻밖의 창 · 패널(대상 글이 없는 맨 위 창)이 있으면 사람처럼 그 창의 닫기(✕)를 누르거나 Esc로 없앤 뒤 다시 찾는다(사용자 2026-11-13 「그냥 땅 클릭해서 없애고」).
   const cover=await c.serial(()=>c.raw.evaluate(v=>{const ds=[...document.querySelectorAll('[role=dialog]')].filter(d=>d.checkVisibility({checkVisibilityCSS:true}));const d=ds.at(-1);if(!d||(v&&d.textContent.includes(v)))return null;
     const x=[...d.querySelectorAll('[role=button],button')].find(b=>b.getAttribute('aria-label')==='닫기'&&b.checkVisibility());const r=x?.getBoundingClientRect();return{text:d.textContent.trim().slice(0,40),x:r?r.x+r.width/2:null,y:r?r.y+r.height/2:null};},typeof value==='string'?value:''));
   if(cover){if(cover.x!=null){await c.move(cover.x,cover.y);await c.serial(()=>c.p.mouse.click(cover.x,cover.y));}else await c.key('Escape');await sleep(400);}
   await c.fs.appendFile(c.out+'/reclicks.jsonl',JSON.stringify({cue:ctx.cue?.id,kind,value,closed:cover?.text||null,reason:String(e).slice(0,160)})+String.fromCharCode(10));await sleep(800);return locateOnce(kind,value);}};
 c.revealText=async text=>{const sel=await c.serial(()=>c.raw.evaluate(text=>{const e=[...document.querySelectorAll('[contenteditable=true][role=textbox]')].find(e=>e.textContent.trim()===text&&e.getBoundingClientRect().height);if(!e)throw Error('Text missing '+text);return '#'+CSS.escape(e.id);},text));await inView(c,sel);};
 const baseEndOf=c.endOf;c.endOf=async selector=>{await inView(c,await c.mark({css:selector,last:true}));await baseEndOf(selector);};
 // 위 막대(경로 줄)는 쪽을 새로 열면 숨은 채 나온다(함정) — 막대 링크가 안 보이면 커서를 위 막대 자리로 올려 나타나게 한 뒤 누른다(리허설 r31: 실패 구간부터 다시 연 첫 구간).
 const topVisible=text=>c.serial(()=>c.raw.evaluate(t=>[...document.querySelectorAll('a,[role=link]')].some(e=>e.textContent.trim()===t&&e.getBoundingClientRect().top<65&&e.checkVisibility({checkVisibilityCSS:true})),text));
 const baseLink=c.link;c.link=async(text,top=false)=>{if(!top)await inView(c,await c.mark({css:'a,[role=link]',text,notIn:'.notion-topbar',first:true}));
  else if(!(await topVisible(text))){await c.move(700,22);for(let i=0;i<15&&!(await topVisible(text));i++)await sleep(200);}
  await baseLink(text,top);};
 const baseRole=c.role;c.role=async(role,name)=>{await inView(c,await c.mark({css:`[role="${role}"]`,name,first:role!=='option'}));await baseRole(role,name);};

 c.hoverLabel=async(label,button=false)=>c.hoverAt(await c.labelSel(label,button));
 c.labelSel=async(label,button=false)=>{const t='l'+Math.random().toString(36).slice(2,10);await c.serial(()=>c.raw.evaluate(labelTargetInPage,{label,button,mark:t}));return '[data-v12="'+t+'"]';};
 c.clickLabel=async(label,button=false)=>c.click('css',await c.labelSel(label,button));
 c.hideProp=async name=>{await c.serial(()=>c.raw.evaluate(eyeState,name));await inView(c,`[data-tutorial-eye="${name}"]`);await hideProperty(c,name);};
 c.hoverAt=async sel=>{await inView(c,sel);const q=await c.serial(()=>c.raw.evaluate(pointOf,sel));await c.move(q.x,q.y);};
 c.clickAt=async sel=>{await inView(c,sel);await c.click('css',sel);};
 c.hover=async(kind,value)=>{const q=await c.locate(kind,value);await c.move(q.x,q.y);};
 c.hoverText=async(text,spec={})=>c.hoverAt(await c.mark({css:'[contenteditable=true][role=textbox]',text,...spec}));
 // 블록 손잡이: 블록 왼쪽에 올리고 손잡이가 나올 때까지 기다린다. Notion은 입력 직후에는 손잡이를 숨기고 다음 마우스 움직임에서 보이므로(리허설 r9),
 // 0.5초마다 2px씩 움직여 깨운다(6초 안에 안 나오면 멈춘다). 손잡이 판정은 lib/block-handle.mjs와 같다.
 const handleNear=s=>{const r=document.querySelector(s)?.getBoundingClientRect();if(!r)return null;const e=[...document.querySelectorAll('[aria-label="드래그하여 이동하고 클릭하여 메뉴를 여세요"]')].find(e=>{const h=e.getBoundingClientRect(),hit=document.elementFromPoint(h.x+h.width/2,h.y+h.height/2);return h.width&&hit&&(hit===e||e.contains(hit))&&h.x<r.x&&Math.abs(h.y+12-(r.y+20))<25;});if(!e)return null;const h=e.getBoundingClientRect();return{x:h.x+h.width/2,y:h.y+h.height/2};};
 c.handleOf=async selector=>{await inView(c,selector);const r=await c.serial(()=>c.raw.evaluate(s=>{const r=document.querySelector(s).getBoundingClientRect();return{x:r.x+10,y:r.y+14};},selector));
  await c.move(r.x,r.y);let q=null;for(let i=0;i<12&&!(q=await c.serial(()=>c.raw.evaluate(handleNear,selector)));i++){await sleep(500);await c.glide(r.x+(i%2?0:2),r.y);}
  if(!q)throw Error('Block handle did not appear next to '+selector);await c.move(q.x,q.y);return q;};
 // 콜아웃 손잡이(옛 calloutHandle과 같은 블록 선택자) — 손잡이 기다리기는 위 handleOf.
 const noteBlock=prefix=>c.serial(()=>c.raw.evaluate(prefix=>{const ns=[...document.querySelectorAll('[role=note]')];const n=prefix==null?ns.at(-1):ns.find(e=>e.textContent.startsWith(prefix));if(!n)throw Error('Callout missing '+prefix);
   return{sel:'.notion-callout-block[data-block-id="'+n.closest('.notion-callout-block').getAttribute('data-block-id')+'"]:has(>[role=note])',text:n.textContent};},prefix));
 c.calloutHandleOf=async prefix=>{const b=await noteBlock(prefix);return c.handleOf(b.sel);};
 // 마지막 콜아웃의 손잡이를 눌러 블록 메뉴를 연다(색 바꾸기 확인에 쓰는 activeCalloutPrefix도 단다).
 c.noteHandle=async()=>{const b=await noteBlock(null);c.activeCalloutPrefix=b.text;const q=await c.handleOf(b.sel);await c.serial(()=>c.p.mouse.click(q.x,q.y));await c.serial(()=>c.raw.waitForSelector('[role=dialog]',{state:'visible'}));};

 // ② 블록 만들기
 c.slash=async(query,item)=>{await c.type('/'+query);await c.click('menu',item);};
 const notes=()=>c.serial(()=>c.raw.evaluate(()=>document.querySelectorAll('[role=note]').length));
 // 상자를 만드는 조작마다 새 상자의 색을 대본과 맞춘다(기대 색 · 대본 말을 반드시 준다). Notion은 마지막에 쓴 콜아웃 색을 새 상자에 이어 주는데,
 // 리허설이 남긴 파란색이 4단계 첫 상자에 찍혀 「기본 회색」이라는 말과 어긋났다(take-k9-v12-04 프레임 414). 다르면 멈춘다.
 c.callout=async(expect,why)=>{if(!expect||!why)throw Error('c.callout(기대 색, 대본 말)이 필요하다');await c.type('/콜아웃');await c.calloutPick(expect,why);};
 c.calloutPick=async(expect,why)=>{if(!expect||!why)throw Error('c.calloutPick(기대 색, 대본 말)이 필요하다');const n=await notes();await c.click('menu','콜아웃');await c.serial(()=>c.raw.waitForFunction(n=>document.querySelectorAll('[role=note]').length>n,n,{timeout:8000})).catch(()=>{throw Error('Callout did not appear');});await c.expectNote(expect,why);};
 c.noteColor=()=>c.serial(()=>c.raw.evaluate(()=>{const e=[...document.querySelectorAll('[role=note]')].at(-1);return e?getComputedStyle(e.firstElementChild).backgroundColor:null;}));
 c.expectNote=async(color,why)=>{const got=await c.noteColor();if(got!==color)throw Error('New callout color '+got+' — 대본은 「'+why+'」(기대 '+color+')');};
 // 마크다운 단축(「## 」 · 「- 」 · 「1. 」 · 「[] 」 · 「> 」 · 「---」): 입력하고 캐럿 블록(구분선은 구분선 수)이 그 블록으로 바뀐 것을 확인한다.
 const MD={'## ':'.notion-sub_header-block','- ':'.notion-bulleted_list-block','1. ':'.notion-numbered_list-block','[] ':'.notion-to_do-block','> ':'.notion-toggle-block'};
 c.md=async prefix=>{
  if(prefix==='---'){const n=await c.serial(()=>c.raw.evaluate(()=>document.querySelectorAll('.notion-divider-block').length));await c.type('---');
   await c.serial(()=>c.raw.waitForFunction(n=>document.querySelectorAll('.notion-divider-block').length>n,n,{timeout:4000})).catch(()=>{throw Error('「---」 did not become a divider');});return;}
  const cls=MD[prefix];if(!cls)throw Error('Unknown markdown shortcut '+prefix);await c.type(prefix);
  await c.serial(()=>c.raw.waitForFunction(cls=>{const n=getSelection()?.anchorNode,e=n?.nodeType===1?n:n?.parentElement;return !!e?.closest(cls);},cls,{timeout:4000})).catch(()=>{throw Error('「'+prefix+'」 did not turn the caret block into '+cls);});
 };
 // 토글 펼치기: 단축키(「> 」)로 만든 토글은 처음부터 펼쳐져 있다(리허설 r13) — 닫혀 있으면 삼각형(aria 「열기」)을 누르고, 이미 펼쳐져 있으면 대본과 다름(scriptGap).
 // 토글은 만들 때부터 펼쳐져 있다(리허설 r12 · r27). 대본은 삼각형을 짚기만 하고(누르면 접힌다), 안쪽에는 바로 적는다.
 c.toggleTriangle=async()=>{const t='g'+Math.random().toString(36).slice(2,10);const open=await c.serial(()=>c.raw.evaluate(t=>{const e=[...document.querySelectorAll('.notion-toggle-block [role=button][aria-expanded]')].filter(e=>e.checkVisibility({checkVisibilityCSS:true})).at(-1);if(!e)throw Error('Toggle triangle missing');e.setAttribute('data-v12',t);return e.getAttribute('aria-expanded');},t));
  if(open!=='true')await c.scriptGap('토글이 접힌 채 만들어짐 — 대본은 「토글은 처음부터 펼쳐져 있어요」');await c.hoverAt('[data-v12="'+t+'"]');};
 c.toggleInside=async()=>{const open=await c.serial(()=>c.raw.evaluate(()=>[...document.querySelectorAll('.notion-toggle-block [role=button][aria-expanded]')].filter(e=>e.checkVisibility({checkVisibilityCSS:true})).at(-1)?.getAttribute('aria-expanded')));
  if(open!=='true')await c.scriptGap('토글이 접힌 채 만들어짐 — 대본은 펼쳐진 토글 안쪽에 바로 적는다');await c.click('text','빈 토글입니다. 클릭하거나 블록을 내부로 드래그하세요.');};
 c.exitBox=async()=>{await c.endOf('[role=note] [contenteditable=true][role=textbox]');await c.key('Enter');await c.exitCallout();};
 c.boxText=async(bold,body)=>{await c.key('Control+b');await c.type(bold);await c.key('Control+b');await c.key('Enter');await c.type(body);};
 // 제목: scope 'region'이면 가운데 창(템플릿 · 미리 보기)의 제목.
 // 새 페이지의 제목은 처음 몇 초 사이 다시 그려져 표시가 떨어진다(리허설 r4) — 그래서 제목은 표시를 달지 않고 그때그때 다시 찾는다.
 const h1sel=scope=>scope==='region'?'[role=region] h1[contenteditable=true]':'h1[contenteditable=true]';
 c.titleHover=async scope=>{const q=scope==='region'?await c.locate('css',h1sel(scope)):await c.locate('title','');await c.move(q.x,q.y);};
 c.titleType=async(text,scope)=>{if(scope==='region')await c.click('css',h1sel(scope));else await c.click('title','');await c.type(text);};
 c.titleEnter=async scope=>{await c.endOf((scope==='region'?'[role=region] ':'')+'h1[contenteditable=true]');await c.key('Enter');};
 // 본문 첫 줄로: 캐럿(포커스)이 제목 아래 빈 줄에 있지 않으면(아이콘 · 커버 창을 닫았거나 사이드바를 접어 포커스가 빠진 뒤) 빈 본문 줄이 있으면 그 줄을,
 // 없으면 제목 끝을 누르고 Enter로 내려간다.
 c.toBody=async scope=>{const st=await c.serial(()=>c.raw.evaluate(()=>{const a=document.activeElement,n=getSelection()?.anchorNode,e=n?.nodeType===1?n:n?.parentElement,t=e?.closest('[contenteditable=true]');
   const empty=[...document.querySelectorAll('[contenteditable=true][role=textbox]')].some(x=>x.tagName!=='H1'&&!x.getAttribute('aria-label')&&!x.textContent.trim()&&x.checkVisibility({checkVisibilityCSS:true}));
   return{ok:!!a?.isContentEditable&&!!t&&t.tagName!=='H1'&&!t.textContent,empty};}));
  if(st.ok)return;if(st.empty&&scope!=='region')await c.click('body','');else await c.titleEnter(scope);};

 // ③ 아이콘(이모지): 제목 위 「아이콘 추가」 → 검색 칸에 이름 → Enter. change=true면 지금 아이콘을 눌러 바꾼다. 검색어는 config.json v12.emoji[key].
 const iconInPage=({scope,mark})=>{
  const pathOf=e=>{if(!e.closest('[contenteditable=true]'))return null;const parts=[];let a=e;while(a&&a!==document.documentElement){const bid=a.getAttribute('data-block-id');const own=a.id?'#'+CSS.escape(a.id):bid?a.tagName.toLowerCase()+'[data-block-id="'+bid+'"]':null;if(own&&document.querySelectorAll(own).length===1){parts.unshift(own);break;}parts.unshift(a.tagName.toLowerCase()+':nth-child('+([...a.parentElement.children].indexOf(a)+1)+')');a=a.parentElement;}const sel=parts.join(' > ');if(document.querySelector(sel)!==e)throw Error('Structural selector does not resolve back: '+sel);return sel;};
  const vis=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&e.checkVisibility({checkVisibilityCSS:true});};
  const root=scope==='region'?[...document.querySelectorAll('[role=region]')].filter(vis).at(-1):document;
  const es=[...root.querySelectorAll('[role=button]')].filter(e=>vis(e)&&/페이지 아이콘 변경$/.test(e.getAttribute('aria-label')||'')&&e.getBoundingClientRect().height>=40);
  if(es.length<1)throw Error('Page icon button (…페이지 아이콘 변경) missing');
  const path=pathOf(es.at(-1));if(path)return path;es.at(-1).setAttribute('data-v12',mark);return '[data-v12="'+mark+'"]';
 };
 c.emoji=async(key,{scope=null,change=false,times={}}={})=>{
  const q=ctx.v12?.emoji?.[key];if(!q)throw Error('config.json v12.emoji["'+key+'"] 비어 있음');
  if(times.open!=null)c.at(times.open);
  if(change){const t='i'+Math.random().toString(36).slice(2,10);await c.clickAt(await c.serial(()=>c.raw.evaluate(iconInPage,{scope,mark:t})));}
  else{await c.titleHover(scope);await c.click('css',await c.mark({css:'[role=button]',text:'아이콘 추가',scope:scope==='region'?'region':null}));}
  // 고르는 창은 검색 칸에 캐럿을 둔 채 열린다(길뚫기). 3초 안에 캐럿이 입력칸에 없으면 멈춘다.
  await c.serial(()=>c.raw.waitForFunction(()=>document.activeElement?.matches('input'),undefined,{timeout:3000})).catch(()=>{throw Error('Emoji picker search box not focused: '+key);});
  if(times.type!=null)c.at(times.type);
  await c.type(q);await sleep(600);
  if(times.pick!=null)c.at(times.pick);
  await c.key('Enter');
  await c.serial(()=>c.raw.waitForFunction(()=>!document.activeElement?.matches('input'),undefined,{timeout:5000})).catch(()=>{throw Error('Emoji picker still open after Enter (검색어 「'+q+'」 결과 없음?)');});
  if(!change&&await c.serial(()=>c.raw.evaluate(sc=>{const root=sc==='region'?document.querySelector('[role=region]'):document;return [...root.querySelectorAll('[role=button]')].some(e=>e.textContent.trim()==='아이콘 추가'&&e.checkVisibility({checkVisibilityCSS:true}));},scope)))throw Error('「아이콘 추가」 still shown — icon not set: '+key);
 };
 c.hoverIcon=async scope=>{const t='i'+Math.random().toString(36).slice(2,10);await c.hoverAt(await c.serial(()=>c.raw.evaluate(iconInPage,{scope,mark:t})));};

 // 커버: 「커버 추가」(무작위 그림) → 커버 그림(img.notion-page-cover) 위에 올리면 오른쪽 위에 「변경하기」(aria-label 「페이지 커버 이미지 업데이트」) →
 // 「페이지 커버」 창의 갤러리에서 config.json v12.cover 이름(aria-label)의 그림. 이름은 길뚫기에서 읽었다(2026-11-12).
 const coverOpen=()=>c.serial(()=>c.raw.evaluate(()=>[...document.querySelectorAll('[role=dialog]')].some(d=>d.getAttribute('aria-label')==='페이지 커버'&&d.checkVisibility({checkVisibilityCSS:true}))));
 c.coverAdd=async()=>{await c.titleHover();await c.click('css',await c.mark({css:'[role=button]',text:'커버 추가'}));
  await c.serial(()=>c.raw.waitForSelector('img.notion-page-cover',{timeout:8000})).catch(()=>{throw Error('Cover did not appear (img.notion-page-cover)');});};
 c.coverHover=async()=>{await inView(c,'img.notion-page-cover',0);const q=await c.serial(()=>c.raw.evaluate(()=>{const r=document.querySelector('img.notion-page-cover').getBoundingClientRect();return{x:r.x+r.width*0.7,y:r.y+r.height*0.6};}));await c.move(q.x,q.y);};
 c.coverChange=async()=>{await c.click('css',await c.mark({css:'[role=button][aria-label="페이지 커버 이미지 업데이트"]'}));
  for(let n=0;n<30&&!(await coverOpen());n++)await sleep(200);if(!(await coverOpen()))throw Error('「페이지 커버」 picker did not open');};
 c.coverPick=async()=>{const name=ctx.v12?.cover;if(!name)throw Error('config.json v12.cover 비어 있음 — 커버 갤러리에서 고를 그림 이름(aria-label)');
  // 갤러리를 굴리지 않는다: 그 칸이 창 안에 온전히 보이면(여유 4px) 그 자리에서 누른다 — 여유 56px 규칙이 굴리기를 부르고 말 없이 8.6초가 흘렀다(k3 s02-10).
  // 커서는 앞 큐(창 열기) 끝에서 이미 그 칸 위에 가 있다(coverAim) — 「저는 이걸로 할게요」(1.5초)는 이동 · 누르기 · 확인을 다 담기에 짧아
  // 세 번 연달아 말 뒤로 넘쳤다(k1 · k3 · k4 s02-10). 여기서는 누르고, 창이 닫히는지만 짧게 본다.
  const q=await coverTile();await c.move(q.x,q.y);await c.serial(()=>c.p.mouse.click(q.x,q.y));
  for(let n=0;n<6&&await coverOpen();n++)await sleep(100);if(await coverOpen())await c.key('Escape');};
 const coverTile=async()=>{const name=ctx.v12?.cover;const sel=await c.mark({css:'[role=dialog][aria-label="페이지 커버"] [role=button]',name,first:true});await inView(c,sel,4);return c.serial(()=>c.raw.evaluate(pointOf,sel));};
 c.coverAim=async()=>{const q=await coverTile();await c.glide(q.x,q.y);};

 // 탭: 'notion'(p1) · 'guide' · 'downloads' · 'export'. 다른 탭을 앞에 놓으면 녹화도 그 탭으로 옮기고, 화살표를 같은 자리에 둔다.
 c._pages=new Map();
 c.forPage=async name=>{
  if(name==='notion')return c;if(c._pages.has(name))return c._pages.get(name);
  const pg=ctx.pageNamed(name);if(!pg)throw Error('Page not open: '+name+' (그 구간의 prepare가 c.openTab으로 연다)');
  const pctx=new Proxy(ctx,{get:(t,k)=>k==='p'?pg:t[k],set:(t,k,v)=>{t[k]=v;return true;}});
  const g=await v12(pctx);g.pageName=name;c._pages.set(name,g);return g;
 };
 c.pointerAt=()=>c.serial(()=>c.raw.evaluate(()=>{const r=document.getElementById('recording-pointer')?.getBoundingClientRect();return r?{x:r.x,y:r.y}:null;}));
 c.place=async pos=>{await c.serial(()=>c.raw.evaluate(installPointerInPage,pos));
  await c.serial(()=>c.raw.evaluate(q=>{const e=document.getElementById('recording-pointer');if(window.__glide?.cancel)window.__glide.cancel();window.__glide=null;e.style.transform=`translate(${q.x}px,${q.y}px)`;},pos));
  await c.serial(()=>c.raw.mouse.move(pos.x,pos.y,{steps:1}));c.setPos(pos);};
 const frontName=()=>{if(ctx.sess.cur===ctx.sess.p)return 'notion';for(const [k,v] of ctx.sess.pages)if(v===ctx.sess.cur)return k;throw Error('Unknown front page');};
 c.front=async name=>{const from=await c.forPage(frontName()),to=await c.forPage(name);if(from===to)return to;
  const pos=await from.pointerAt();if(pos)await to.place(pos);await ctx.front(to.raw);return to;};
 // 녹화 밖(prepare)에서 탭을 열어 둔다: 열고 화살표를 지금 자리에 그린 뒤 원래 탭을 다시 앞에 둔다.
 c.openTab=async(name,url)=>{const back=frontName();const pos=await (await c.forPage(back)).pointerAt();await ctx.openPage(name,url);const g=await c.forPage(name);
  await g.serial(()=>g.raw.waitForFunction(()=>document.readyState==='complete',undefined,{timeout:30000}));if(pos)await g.place(pos);await ctx.front((await c.forPage(back)).raw);return g;};

 // 가이드 복사: 가이드 탭을 앞에 놓고 → 왼쪽 「진행 순서」의 그 절(part) → 복사 단추(copyId)를 화면 안에 들여 누른다.
 // 가이드의 복사는 navigator.clipboard.writeText다. 성공한 글만 window.__copied에 남기게 감싸 확인하고, 그 글을 c.state.clip에 둔다.
 c.guideUrl=()=>{if(!ctx.v12?.guide)throw Error('config.json v12.guide 비어 있음');return 'file:///'+encodeURI(ctx.abs(ctx.v12.guide));};
 c.ensureGuide=async()=>{if(!ctx.pageNamed('guide'))await c.openTab('guide',c.guideUrl());};
 c.guideCopy=async(part,copyId,{navAt,copyAt}={})=>{
  const g=await c.front('guide');
  await g.serial(()=>g.raw.evaluate(()=>{if(!window.__copyWrapped){const w=navigator.clipboard.writeText.bind(navigator.clipboard);navigator.clipboard.writeText=async t=>{const r=await w(t);window.__copied=t;return r;};window.__copyWrapped=true;}window.__copied=null;}));
  // 「진행 순서」는 화면에 붙은 목차라 1536×864에서 아래 항목(#part11~)이 화면 밖에 잘린다(리허설 r15). 목표 절과 같거나 앞이면서 온전히 보이는
  // 가장 뒤 항목을 누르고, 복사 단추까지는 아래의 화면 안에 들이기로 내려간다(사람이 가까운 장을 누르고 조금 내려 찾듯).
  // 가이드를 새로 열면 맨 위라 머리글이 목차를 화면 아래로 민다(#part04까지만 보임 — 리허설 r22 진단). 목차가 화면 위(top 30px)에 붙도록 그만큼만 먼저 내린다.
  // 목차 항목은 온전히 보이는 것만 고른다. 잘린 항목은 공용 찾기가 굴려 들이려다 멈춘다(화면에 붙은 목차는 굴려도 안 움직임 — 리허설 r23).
  if(part){const navTop=await g.serial(()=>g.raw.evaluate(()=>document.querySelector('nav')?.getBoundingClientRect().top??null));
   if(navTop==null)throw Error('Guide nav missing');
   if(navTop>40){await g.glide(700,400);await wheelSmooth(g,0,Math.round(navTop-30));let y0=-1;for(let i=0;i<20;i++){const y=await g.serial(()=>g.raw.evaluate(()=>scrollY));if(Math.abs(y-y0)<1)break;y0=y;await sleep(150);}}}
  if(part){const href=await g.serial(()=>g.raw.evaluate(part=>{const ls=[...document.querySelectorAll('nav a[href^="#part"]')];const ti=ls.findIndex(a=>a.getAttribute('href')==='#'+part);if(ti<0)throw Error('Guide nav has no #'+part);
    for(let i=ti;i>=0;i--){const r=ls[i].getBoundingClientRect();if(r.top>=0&&r.bottom<=innerHeight-8)return ls[i].getAttribute('href');}throw Error('No guide nav link visible up to #'+part);},part));
   if(navAt!=null)c.at(navAt);await g.click('css',`nav a[href="${href}"]`);
   // 가이드는 scroll-behavior:smooth라 목차를 누르면 부드러운 이동이 한동안 이어진다. 그 사이 휠을 굴리면 서로 상쇄돼 단추에 못 닿았다(리허설 r16 · r19 · r20) — 멈출 때까지 기다린다.
   let y0=-1;for(let i=0;i<40;i++){const y=await g.serial(()=>g.raw.evaluate(()=>scrollY));if(Math.abs(y-y0)<1)break;y0=y;await sleep(150);}}
  // 가이드는 길어서(끝까지 약 81,000px) 864px 화면에서 보이는 가장 뒤 목차 항목(#part10)에서도 첫 카드 그림 단추까지 약 7,000px가 남는다 — 한 번에
  // 1,400px까지 굴리고 20번까지 들인다(약 3~4초). 목차가 화면 높이 안에서 스크롤되면(가이드 CSS) 이 스크롤은 없어진다 — 결정 목록.
  const bsel=`button[data-copy="${copyId}"]`;const sy0=await g.serial(()=>g.raw.evaluate(()=>scrollY)),ts=Date.now();await inView(g,bsel,56,20,1400);
  const sy1=await g.serial(()=>g.raw.evaluate(()=>scrollY));await c.fs.appendFile(c.out+'/guide-scroll.jsonl',JSON.stringify({copyId,nav:part||null,from:Math.round(sy0),to:Math.round(sy1),px:Math.round(sy1-sy0),ms:Date.now()-ts})+String.fromCharCode(10));
  if(copyAt!=null)c.at(copyAt);await g.click('css',bsel);
  const want=await g.serial(()=>g.raw.evaluate(id=>document.getElementById(id)?.textContent,copyId));if(!want)throw Error('Guide copy source missing: '+copyId);
  await g.serial(()=>g.raw.waitForFunction(w=>window.__copied===w,want,{timeout:4000})).catch(()=>{throw Error('Guide copy did not reach the clipboard: '+copyId);});
  c.state.clip=want;return want;
 };
 // 붙여넣기(Ctrl+V)와 확인: 캐럿이 있는 칸에 가이드에서 복사한 글이 들어갔는지 본다.
 c.paste=async()=>{const want=c.state.clip;if(!want)throw Error('Nothing copied from the guide yet');await c.key('Control+v');
  await c.serial(()=>c.raw.waitForFunction(w=>{const e=document.activeElement;const v=e?.matches?.('input,textarea')?e.value:e?.textContent;return !!v&&v.includes(w);},want,{timeout:4000})).catch(()=>{throw Error('Paste did not put the copied guide text into the focused field');});};

 // 데이터베이스 보기 설정 · 속성
 c.dbSettings=()=>c.click('css','.notion-collection-edit-view');
 c.propEdit=async()=>{await c.hoverSel('loc=role:menuitem[name="속성 편집"]');await c.click('menu','속성 편집');};
 c.newProp=async()=>{await c.dbSettings();await c.propEdit();await c.click('menu','새 속성');};
 c.option=async text=>{if(!(await c.serial(()=>c.raw.evaluate(()=>!!document.querySelector('input[placeholder="새 옵션을 입력하세요"]')))))await c.click('text','옵션 추가');await c.click('css','input[placeholder="새 옵션을 입력하세요"]');await c.type(text);await c.key('Enter');};
 c.propRow=name=>c.serial(()=>c.raw.evaluate(name=>{const rows=[...document.querySelectorAll('[role=row]')].filter(e=>e.textContent.trim().startsWith(name));const row=rows.find(e=>e.closest('[aria-label="페이지 속성"]'))||rows[0];if(!row)throw Error('Property row missing: '+name);const t='r'+Math.random().toString(36).slice(2,10);const el=(row.querySelector('[role=cell]')||row);const pathOf=e=>{if(!e.closest('[contenteditable=true]'))return null;const parts=[];let a=e;while(a&&a!==document.documentElement){const bid=a.getAttribute('data-block-id');const own=a.id?'#'+CSS.escape(a.id):bid?a.tagName.toLowerCase()+'[data-block-id="'+bid+'"]':null;if(own&&document.querySelectorAll(own).length===1){parts.unshift(own);break;}parts.unshift(a.tagName.toLowerCase()+':nth-child('+([...a.parentElement.children].indexOf(a)+1)+')');a=a.parentElement;}const sel=parts.join(' > ');if(document.querySelector(sel)!==e)throw Error('Structural selector does not resolve back: '+sel);return sel;};const path=pathOf(el);if(path)return path;el.setAttribute('data-v12',t);return '[data-v12="'+t+'"]';},name));
 c.propValue=name=>c.serial(()=>c.raw.evaluate(name=>{const rows=[...document.querySelectorAll('[role=row]')].filter(e=>e.textContent.trim().startsWith(name));const row=rows.find(e=>e.closest('[aria-label="페이지 속성"]'))||rows[0];if(!row)throw Error('Property row missing: '+name);const t='r'+Math.random().toString(36).slice(2,10);const el=([...row.querySelectorAll('[role=cell]')].at(-1)||row);const pathOf=e=>{if(!e.closest('[contenteditable=true]'))return null;const parts=[];let a=e;while(a&&a!==document.documentElement){const bid=a.getAttribute('data-block-id');const own=a.id?'#'+CSS.escape(a.id):bid?a.tagName.toLowerCase()+'[data-block-id="'+bid+'"]':null;if(own&&document.querySelectorAll(own).length===1){parts.unshift(own);break;}parts.unshift(a.tagName.toLowerCase()+':nth-child('+([...a.parentElement.children].indexOf(a)+1)+')');a=a.parentElement;}const sel=parts.join(' > ');if(document.querySelector(sel)!==e)throw Error('Structural selector does not resolve back: '+sel);return sel;};const path=pathOf(el);if(path)return path;el.setAttribute('data-v12',t);return '[data-v12="'+t+'"]';},name));
 // 카드 이미지 칸 → 「파일 또는 이미지를 추가하세요」에 올려 창을 연다(안 열리면 누르고 reclicks.jsonl에 남긴다) → 링크 탭이 보일 때까지.
 c.imagePopup=async()=>{await c.slot('카드 이미지');
  const ready=()=>c.serial(()=>c.raw.evaluate(()=>[...document.querySelectorAll('[role=tab]')].some(e=>e.textContent.trim()==='링크'&&e.checkVisibility({checkVisibilityCSS:true}))));
  await c.hover('text','파일 또는 이미지를 추가하세요');for(let n=0;n<8&&!(await ready());n++)await sleep(200);
  if(!(await ready())){await c.fs.appendFile(c.out+'/reclicks.jsonl',JSON.stringify({target:'파일 또는 이미지를 추가하세요',reason:'popup not opened by hover within 1.6s'})+'\n');await c.click('text','파일 또는 이미지를 추가하세요');}
  await c.serial(()=>c.raw.waitForSelector('loc=role:tab[name="링크"]',{state:'visible',timeout:8000}));};
 c.card=nth=>c.mark({css:'.notion-gallery-view .notion-collection-item',nth});
 c.topicOpen=async title=>{await c.click('text',title);await c.click('css','[role=region] a[aria-label="전체 페이지로 열기"]');};
 c.pageLink=title=>c.mark({css:'.notion-page-content a',text:title,first:true});
 c.crumb=title=>c.mark({css:'a,[role=link],[role=button],div,span',text:title,top:true,first:true});
 // 블록 선택자: 그 글이 든 블록, 그 이름의 하위 페이지 블록(손잡이 잡기용 — 옛 seg-31과 같은 꼴).
 c.blockOf=text=>c.serial(()=>c.raw.evaluate(text=>{const e=[...document.querySelectorAll('[contenteditable=true][role=textbox]')].find(e=>e.textContent.trim()===text);const b=e?.closest('[data-block-id]');if(!b)throw Error('Block missing: '+text);
   // 손잡이가 보일 때 그 감싸개가 블록과 같은 클래스 · data-block-id를 달고 먼저 나온다(리허설 r10 · r11) — 옛 pageBlock의 :has(a)처럼 블록 자신의 글 칸으로 가린다.
   const sel='[data-block-id="'+b.getAttribute('data-block-id')+'"]:has([contenteditable=true][role=textbox])';if(document.querySelector(sel)!==b)throw Error('Block selector ambiguous: '+sel);return sel;},text));
 c.pageBlock=title=>c.serial(()=>c.raw.evaluate(title=>{const a=[...document.querySelectorAll('.notion-page-content a')].find(e=>e.textContent.trim()===title);const b=a?.closest('.notion-page-block');if(!b)throw Error('Page block missing: '+title);return '.notion-page-block[data-block-id="'+b.getAttribute('data-block-id')+'"]:has(a)';},title));
 return c;
}

// 모듈의 손잡이를 쓰는 짧은 꼴. c는 손잡이가 불릴 때만 읽는다(preflight가 ops(null)로 이름만 셀 수 있게).
export const kit=c=>({
 at:(pointFrac,fn)=>({pointFrac,fn}),                                                          // 출발 시점만 바꾼 손잡이
 T:text=>({pointFrac:0,fn:async()=>{c.at('point');await c.type(text);}}),                      // 마지막 문장(따옴표 글)을 읽기 시작할 때 입력
 ET:text=>({pointFrac:0,fn:async()=>{c.at(0.03);await c.key('Enter');c.at('point');await c.type(text);}}),  // 엔터 뒤 입력
 K:(...keys)=>async()=>{for(const k of keys)await c.key(k);},                                  // 끝에서 키
 H2:text=>({pointFrac:0,fn:async()=>{c.at(0.03);await c.md('## ');await c.type(text);c.at(1);await c.key('Enter');}}),  // 제목 2 단축 → 글 → 엔터
 OUT:()=>async()=>{await c.exitBox();await c.key('Enter');},                                  // 상자 밖으로 나와 한 줄 띄움
});

// 구간 하나: prepare(녹화 밖) → 녹화 시작 → parts의 큐를 차례대로 말하며 손잡이를 부른다 → after(녹화 안 확인).
export async function playSegment(ctx,mod){
 const c=await v12(ctx);
 if(mod.prepare)await mod.prepare(c);
 if(ctx.sess.cur===ctx.sess.p&&await c.serial(()=>c.raw.evaluate(()=>/최신 버전으로 업데이트|문제가 발생했습니다/.test(document.body.innerText))))throw Error('Notion banner on screen before recording: ./run.sh restore reload');
 // 녹화 시작 전(화면에 남지 않음) 노션이 영어로 그려져 있으면 한국어가 될 때까지 다시 불러온다(그래도 영어면 멈춘다).
 if(ctx.sess.cur===ctx.sess.p&&(await c.serial(()=>c.raw.url())).includes('app.notion')&&(await c.lang())!=='ko'){const n=await c.ensureKorean();await c.fs.appendFile(c.out+'/reloads.jsonl',JSON.stringify({why:'Notion UI English before recording',reloads:n})+String.fromCharCode(10));if(!(await c.pointerAt()))await c.place({x:760,y:430});}
 await ctx.begin();
 const H=mod.ops(c);
 for(const part of mod.parts){
  const h=H[part.step]||{};
  for(const cue of partCues(ctx.cues,part)){
   let fn=null;const opt={gap:cue.pause_before,pointFrac:cue.point,commitFrac:1};
   if(cue.op){const x=h[cue.op];if(!x)throw Error(ctx.segName+' step '+part.step+': no handler for op '+cue.op+' ('+cue.id+')');
    if(typeof x==='function')fn=x;else{fn=x.fn;if(x.pointFrac!=null)opt.pointFrac=x.pointFrac==='point'?cue.point:x.pointFrac;}}
   ctx.cue=cue;await ctx.say(cue.id,fn,opt);
  }
 }
 if(mod.after)await mod.after(c);
 return ctx.segName+' done';
}
