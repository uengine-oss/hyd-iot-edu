// 화면 위 그림 층(웹 VS Code 녹화) — 강조 · 펜 그림 · 글상자. 화살표(ui.mjs)처럼 페이지에 그려 화면과 함께 녹화한다.
// ctrl.mjs가 구간마다 drawLayer로 만들어 ctx.draw에 두고, ui.mjs의 c.emph · c.clearEmph · c.pen · c.note가 부른다(쓰는 법은 촬영준비 「길」 6).
// - 강조(영상 V-14 · V-11): 대상 재기 · 모양 · 시작과 끝 · 멈춤 규칙은 포털 hl.mjs 그대로다(highlighter). 포털 · Neo4j · ARROWS는 화살표와 강조를 합성 때 그리고,
//   이 도구는 화살표를 페이지에 그리므로 강조도 페이지에 그린다. 모양 값(STYLE)은 포털 encode.py의 HL · 이론 강조표시.py와 같은 값이고 프레임 px(1920×1080)이다.
//   기록은 timing.json의 highlights(hl.mjs와 같은 꼴)다. 이 층에서는 펜 그림의 동그라미 · 덧긋기가 시작할 때, 그림이나 글상자를 걷을 때에도 앞 강조를 지운다.
//   대상 꼴: {sel, text | starts | has | cell:[n, 글], pick:'last', child:n, tight:true} = 바깥 문서에서 보이는 요소 하나, {codex:[x0, y0, x1, y1]} = Codex 패널 안 비율 상자(웹뷰라 글을 잴 수 없다),
//   {pen:'이름'} = 떠 있는 펜 그림의 칸 글 · 획, {note:줄 번호 | '줄에 든 글'} = 글상자의 줄, {box:[x, y, w, h]} · {rects:[…]} = CSS px 상자.
// - 펜 그림: 그림 하나를 정의(판 · 칸 · 화살표 · 글)로 두고, 말에 맞춰 한 획씩 긋거나(draw) 긋는 움직임 없이 다시 띄우고(show) 걷는다(hide). 좌표는 프레임 px이다.
//   걷으면 페이지에 남는 것이 없으므로, 다른 구간 · 다른 편에서도 같은 정의로 다시 띄운다.
// - 글상자: 화면에 없는 짧은 목록을 띄운다(모양은 ARROWS 녹화기의 글상자와 같다). 줄은 강조 대상이 된다.
// - 멈춤: 없는 대상, 여럿 잡힌 대상, 칸 밖으로 굴러간 대상, 화면 밖에 그려질 것, 정의에 없는 이름은 큐 id를 대며 그 큐에서 멈춘다(리허설도 같다).
//   구간이 끝날 때 펜 그림이나 글상자가 떠 있으면 ctrl.mjs가 멈춘다 — 다음 구간은 빈 층에서 시작하므로 이음새에서 그림이 튄다.
import {highlighter} from '../../포털/촬영도구/hl.mjs';

export const STYLE={red:[229,57,53],yellow:[255,214,0],bandAlpha:0.42,line:5,under:2,underSide:[4,6],boxPad:6,radius:4,
 ink:[255,255,255],board:'rgba(17,24,39,.93)',font:"'Malgun Gothic','맑은 고딕',sans-serif",penLine:4,penText:28,ringPad:12,noteText:27};
const KINDS=['box','arrow','text'];

// 페이지 안에서 돈다. a.op마다 한 가지 일을 하고 {error}로 실패를 돌려준다.
export function drawInPage(a){
 try{
 const k=innerWidth/1920,S=a.style,NS='http://www.w3.org/2000/svg',rgb=c=>'rgb('+c.join(',')+')';
 const root=make=>{let r=document.getElementById('recording-draw');if(!r&&make){r=document.createElement('div');r.id='recording-draw';r.setAttribute('aria-hidden','true');
  r.style.cssText='position:fixed;left:0;top:0;width:100vw;height:100vh;pointer-events:none;z-index:2147483646;overflow:hidden';document.documentElement.append(r);}return r;};
 const norm=s=>s.replace(/ /g,' ');
 const vis=e=>{const b=e.getBoundingClientRect();return b.width>0&&b.height>0&&e.checkVisibility({checkVisibilityCSS:true});};
 const inside=(x,y,w,h)=>x>=0&&y>=0&&x+w<=innerWidth&&y+h<=innerHeight;
 const R=v=>Math.round(v*10)/10;
 const el=(tag,css,parent)=>{const e=document.createElement(tag);e.style.cssText=css;parent?.append(e);return e;};
 const fig=()=>root()?.querySelector(`[data-fig="${CSS.escape(a.fig)}"]`);
 const part=(f,id)=>f.querySelector(`[data-pen="${CSS.escape(id)}"]`)||f.querySelector(`[data-stroke="${CSS.escape(id)}"]`);

 if(a.op==='reset'){root()?.remove();window.__hlTarget=null;return {};}

 // 강조 대상 잡기 → window.__hlTarget(hl.mjs의 measureInPage가 읽는다). 구절은 화면 글의 줄바꿈 없는 빈칸(편집기)을 보통 빈칸과 같게 본다.
 if(a.op==='target'){
  const s=a.spec;let t;
  if(Array.isArray(s.box)||Array.isArray(s.rects))t=s;
  else if(s.codex){const b=document.querySelector('.part.auxiliarybar')?.getBoundingClientRect();if(!b||!b.width)return {error:'Codex 패널이 열려 있지 않음'};
   const [x0,y0,x1,y1]=s.codex;if(!(x0>=0&&y0>=0&&x1<=1&&y1<=1&&x1>x0&&y1>y0))return {error:'codex 비율 상자 [x0, y0, x1, y1]이 0~1 안이 아님 — '+JSON.stringify(s.codex)};
   t={box:[b.x+b.width*x0,b.y+b.height*y0,b.width*(x1-x0),b.height*(y1-y0)]};}
  else if(s.pen!=null){const f=root()?.querySelector('[data-fig]'),e=f&&part(f,s.pen);if(!e)return {error:`떠 있는 펜 그림에 「${s.pen}」이 없음`};
   const b=e.getBoundingClientRect();t=e.querySelector?.('.pen-text')||{box:[b.x,b.y,b.width,b.height]};}
  else if(s.note!=null){const n=root()?.querySelector('[data-note]');if(!n)return {error:'떠 있는 글상자가 없음'};
   const ls=[...n.querySelectorAll('[data-line]')].filter(l=>typeof s.note==='number'?Number(l.dataset.line)===s.note:l.textContent.includes(s.note));
   if(ls.length!==1)return {error:`글상자 줄 「${s.note}」이 ${ls.length}개`};t=ls[0].querySelector('.note-text');}
  else if(s.sel){
   const txt=e=>norm(e.textContent||'');
   let es=[...document.querySelectorAll(s.sel)].filter(vis);
   if(s.text!=null)es=es.filter(e=>norm(e.getAttribute('aria-label')||e.textContent||'').trim()===s.text);
   if(s.starts!=null)es=es.filter(e=>txt(e).trimStart().startsWith(s.starts));
   if(s.has!=null)es=es.filter(e=>txt(e).includes(s.has));
   if(s.cell)es=es.filter(e=>norm(e.cells?.[s.cell[0]]?.textContent||'').trim()===s.cell[1]);
   if(s.pick==='last'&&es.length)es=[es.at(-1)];
   if(es.length!==1)return {error:`보이는 대상이 ${es.length}개 — ${JSON.stringify(s)}`};
   t=es[0];
   if(s.child!=null){t=t.children[s.child];if(!t)return {error:`대상의 ${s.child}번째 칸이 없음 — ${JSON.stringify(s)}`};}
   const e0=t;
   if(s.tight&&a.phrase==null){   // 요소 상자가 아니라 그 안 글자가 차지한 자리만(줄마다 하나) — 칸 너비만큼 긴 줄 요소에 띠를 칠 때. 구절을 주면 구절의 글자 자리를 잰다
    const g=document.createRange();g.selectNodeContents(t);const ls=[];
    for(const r of g.getClientRects()){if(r.width<=0||r.height<=0)continue;const c=r.top+r.height/2,l=ls.find(l=>c>l[1]&&c<l[3]);if(l){l[0]=Math.min(l[0],r.left);l[1]=Math.min(l[1],r.top);l[2]=Math.max(l[2],r.right);l[3]=Math.max(l[3],r.bottom);}else ls.push([r.left,r.top,r.right,r.bottom]);}
    if(!ls.length)return {error:`대상에 글자가 없음 — ${JSON.stringify(s)}`};t={rects:ls.map(l=>[l[0],l[1],l[2]-l[0],l[3]-l[1]])};}
   const area=e0.closest('.editor-scrollable, .terminal-wrapper, .explorer-folders-view');
   if(area){const A=area.getBoundingClientRect(),b=e0.getBoundingClientRect();
    if(b.top<A.top-1||b.bottom>A.bottom+1)return {error:`대상이 그 칸(편집기 · 터미널 · 탐색기) 밖으로 굴러가 있음 — 먼저 화면 안으로 들인다 ${JSON.stringify(s)}`};}
  }else return {error:'모르는 대상 꼴 — '+JSON.stringify(s)+' ({sel, text | starts | has | cell, pick, child, tight} | {codex} | {pen} | {note} | {box} | {rects})'};
  let phrase=a.phrase??null;
  if(phrase!=null){if(!t.nodeType)return {error:'구절은 글자를 잴 수 있는 대상(sel · pen의 글 · note)에만 준다'};
   const raw=t.textContent;if(!raw.includes(phrase)){const i=norm(raw).indexOf(norm(phrase));if(i>=0)phrase=raw.slice(i,i+phrase.length);}}
  window.__hlTarget=t;return {phrase};
 }

 // 강조 그리기: rects = hl.mjs가 잰 상자(CSS px). 자리 계산은 포털 encode.py mark_boxes와 같다.
 if(a.op==='mark'){
  const L=S.line*k,p=(S.boxPad+S.line/2)*k,out=[];
  const g=el('div','position:absolute;left:0;top:0',root(true));g.dataset.mark=a.id;
  const add=(x,y,w,h,css)=>{out.push([x,y,w,h].map(R));return el('div',`position:absolute;left:${x}px;top:${y}px;width:${w}px;height:${h}px;box-sizing:border-box;${css}`,g);};
  const wipe=e=>e.animate([{clipPath:'inset(0 100% 0 0)'},{clipPath:'inset(0 0 0 0)'}],{duration:220,easing:'ease-out'});
  if(a.shape==='band')for(const [x,y,w,h] of a.rects)wipe(add(x,y,w,h,`background:rgba(${S.yellow.join(',')},${S.bandAlpha});border-radius:${S.radius*k}px`));
  else if(a.shape==='underline')for(const [x,y,w,h] of a.rects)wipe(add(x-S.underSide[0]*k,y+h+S.under*k-L/2,w+(S.underSide[0]+S.underSide[1])*k,L,`background:${rgb(S.red)};border-radius:${L/2}px`));
  else if(a.shape==='circle')for(const [x,y,w,h] of a.rects)add(x-p,y-p,w+2*p,h+2*p,`border:${L}px solid ${rgb(S.red)};border-radius:50%`).animate([{opacity:0},{opacity:1}],{duration:180});
  else if(a.shape==='box'){const x1=Math.min(...a.rects.map(r=>r[0])),y1=Math.min(...a.rects.map(r=>r[1])),x2=Math.max(...a.rects.map(r=>r[0]+r[2])),y2=Math.max(...a.rects.map(r=>r[1]+r[3]));
   add(x1-p,y1-p,x2-x1+2*p,y2-y1+2*p,`border:${L}px solid ${rgb(S.red)};border-radius:${S.radius*k}px`).animate([{opacity:0},{opacity:1}],{duration:180});}
  else{g.remove();return {error:'모르는 모양 '+a.shape};}
  const bad=out.find(b=>!inside(...b));if(bad){g.remove();return {error:`그릴 자리가 화면 ${innerWidth}×${innerHeight} 밖 — ${JSON.stringify(bad)}`};}
  return {boxes:out};
 }
 if(a.op==='unmark'){for(const id of a.ids){const g=root()?.querySelector(`[data-mark="${id}"]`);if(!g)return {error:'지울 강조가 화면에 없음 — '+id};
   g.removeAttribute('data-mark');g.animate([{opacity:1},{opacity:0}],{duration:150,fill:'forwards'}).onfinish=()=>g.remove();}return {};}

 // 펜 그림: 정의(a.items)에서 a.ids를 차례로 그린다. animate면 한 획씩 긋고(앞 획이 끝난 뒤 다음 획), 아니면 한꺼번에 나타난다. 돌려주는 dur = 다 그려질 때까지 ms.
 if(a.op==='pen'){
  const X=v=>v*k;let f=fig(),t=0;
  if(!f){const other=root()?.querySelector('[data-fig]');if(other)return {error:`다른 펜 그림 「${other.dataset.fig}」이 떠 있음 — 먼저 걷는다`};
   const [bx,by,bw,bh]=a.board.map(X);if(!inside(bx,by,bw,bh))return {error:`판이 화면 밖 — 프레임 px ${JSON.stringify(a.board)}`};
   f=el('div','position:absolute;left:0;top:0;width:100%;height:100%');f.dataset.fig=a.fig;
   el('div',`position:absolute;left:${bx}px;top:${by}px;width:${bw}px;height:${bh}px;background:${S.board};border-radius:${14*k}px;box-shadow:0 ${8*k}px ${40*k}px rgba(0,0,0,.45)`,f);
   const svg=document.createElementNS(NS,'svg');svg.setAttribute('width',innerWidth);svg.setAttribute('height',innerHeight);svg.style.cssText='position:absolute;left:0;top:0;overflow:visible';f.append(svg);
   root(true).append(f);f.animate([{opacity:0},{opacity:1}],{duration:200});t=220;}
  const svg=f.querySelector('svg'),defs=Object.fromEntries(a.items.map(i=>[i.id,i]));
  const stroke=(g,d,color)=>{const q=document.createElementNS(NS,'path');q.setAttribute('d',d);q.setAttribute('fill','none');q.setAttribute('stroke',color);q.setAttribute('stroke-width',S.penLine*k);
   q.setAttribute('stroke-linecap','round');q.setAttribute('stroke-linejoin','round');g.append(q);
   if(a.animate){const len=q.getTotalLength(),ms=Math.round(Math.max(220,Math.min(900,len/(1.1*k))));q.style.strokeDasharray=len;q.style.strokeDashoffset=len;
    q.animate([{strokeDashoffset:len},{strokeDashoffset:0}],{duration:ms,delay:t,fill:'forwards',easing:'ease-in-out'});t+=ms+70;}};
  const write=(e,chars)=>{if(a.animate){const ms=Math.max(260,Math.min(700,chars*45));e.animate([{clipPath:'inset(0 100% 0 0)'},{clipPath:'inset(0 0 0 0)'}],{duration:ms,delay:t,fill:'backwards',easing:'linear'});t+=ms+70;}};
  const group=id=>{const g=document.createElementNS(NS,'g');g.dataset.stroke=id;svg.append(g);return g;};
  const boxOf=id=>{const d=defs[id];if(!d||d.kind!=='box')throw Error(`화살표 끝 「${id}」은 정의에 있는 칸이어야 함`);return d.at.map(X);};
  for(const id of a.ids){
   const it=defs[id];if(!it)return {error:`그림 「${a.fig}」의 정의에 없는 것: ${id}`};
   if(part(f,id))continue;
   let seed=[...id].reduce((h,c)=>(h*31+c.charCodeAt(0))>>>0,7);const j=()=>((seed=(seed*1664525+1013904223)>>>0)/4294967296-0.5)*3*k;
   const ink=it.color==='red'?rgb(S.red):rgb(S.ink),size=S.penText*k*(it.size||1);
   if(it.kind==='box'){
    const [x,y,w,h]=it.at.map(X),c=10*k;if(!inside(x,y,w,h))return {error:`칸 「${id}」이 화면 밖 — 프레임 px ${JSON.stringify(it.at)}`};
    stroke(group(id),`M ${x+c} ${y} Q ${x+w/2} ${y+j()} ${x+w-c} ${y} Q ${x+w} ${y} ${x+w} ${y+c} Q ${x+w+j()} ${y+h/2} ${x+w} ${y+h-c} Q ${x+w} ${y+h} ${x+w-c} ${y+h} Q ${x+w/2} ${y+h+j()} ${x+c} ${y+h} Q ${x} ${y+h} ${x} ${y+h-c} Q ${x+j()} ${y+h/2} ${x} ${y+c} Q ${x} ${y} ${x+c+4*k} ${y-k}`,ink);
    const e=el('div',`position:absolute;left:${x}px;top:${y}px;width:${w}px;height:${h}px;box-sizing:border-box;padding:0 ${12*k}px;display:flex;align-items:center;justify-content:center;text-align:center;white-space:pre-line;color:${ink};font:600 ${size}px/1.35 ${S.font}`,f);
    if(it.fill!=null){if(it.fill!=='black')return {error:`칸 「${id}」의 fill은 'black'만 — ${it.fill}`};e.style.background='#000';}   // 속이 안 보이는 상자(06-1 블랙박스)
    e.dataset.pen=id;const sp=el('span','',e);sp.className='pen-text';sp.textContent=it.text||'';write(e,(it.text||'').length);
   }else if(it.kind==='text'){
    const [x,y]=it.at.map(X);const e=el('div',`position:absolute;left:${x}px;top:${y}px;white-space:pre;color:${ink};font:600 ${size}px/1.35 ${S.font}`,f);
    e.dataset.pen=id;const sp=el('span','',e);sp.className='pen-text';sp.textContent=it.text;const b=e.getBoundingClientRect();
    if(!inside(b.x,b.y,b.width,b.height)){e.remove();return {error:`글 「${id}」이 화면 밖`};}write(e,it.text.length);
   }else if(it.kind==='arrow'){
    const A=boxOf(it.from),B=boxOf(it.to),gap=8*k,g=group(id);let tip,ang;
    if(it.route==='under'||it.route==='over'){   // 칸 아래(위)로 돌아가는 화살표
     const dn=it.route==='under'?1:-1,ax=A[0]+A[2]/2,bx=B[0]+B[2]/2,ay=dn>0?A[1]+A[3]:A[1],by=dn>0?B[1]+B[3]:B[1];
     const yy=(dn>0?Math.max(ay,by):Math.min(ay,by))+dn*X(it.drop||70),c=18*k,sx=Math.sign(bx-ax)||1;
     if(!inside(Math.min(ax,bx),Math.min(yy,ay),Math.abs(bx-ax)||1,Math.abs(yy-ay)))return {error:`화살표 「${id}」이 화면 밖으로 돎`};
     stroke(g,`M ${ax} ${ay+dn*gap} L ${ax} ${yy-dn*c} Q ${ax} ${yy} ${ax+sx*c} ${yy+j()} L ${bx-sx*c} ${yy+j()} Q ${bx} ${yy} ${bx} ${yy-dn*c} L ${bx} ${by+dn*gap}`,ink);tip=[bx,by+dn*gap];ang=dn>0?-Math.PI/2:Math.PI/2;
    }else{   // 두 칸의 가운데를 잇는 곧은 선을 칸 가장자리에서 끊는다
     const ca=[A[0]+A[2]/2,A[1]+A[3]/2],cb=[B[0]+B[2]/2,B[1]+B[3]/2],dx=cb[0]-ca[0],dy=cb[1]-ca[1],len=Math.hypot(dx,dy);if(!len)return {error:`화살표 「${id}」의 두 칸이 같은 자리`};
     const edge=(r,ux,uy)=>Math.min(ux?r[2]/2/Math.abs(ux):Infinity,uy?r[3]/2/Math.abs(uy):Infinity)+gap,ux=dx/len,uy=dy/len,s=edge(A,ux,uy),e=len-edge(B,ux,uy);
     if(e-s<20*k)return {error:`화살표 「${id}」을 그을 틈이 없음(두 칸 사이 ${R((e-s)/k)}px)`};
     stroke(g,`M ${ca[0]+ux*s} ${ca[1]+uy*s} Q ${ca[0]+ux*(s+e)/2+j()} ${ca[1]+uy*(s+e)/2+j()} ${ca[0]+ux*e} ${ca[1]+uy*e}`,ink);tip=[ca[0]+ux*e,ca[1]+uy*e];ang=Math.atan2(uy,ux);
    }
    const hd=16*k;stroke(g,`M ${tip[0]-hd*Math.cos(ang-0.5)} ${tip[1]-hd*Math.sin(ang-0.5)} L ${tip[0]} ${tip[1]} L ${tip[0]-hd*Math.cos(ang+0.5)} ${tip[1]-hd*Math.sin(ang+0.5)}`,ink);
   }else return {error:`모르는 종류 ${it.kind} — ${id}`};
  }
  return {dur:t};
 }
 // 펜 그림 위에 덧긋기: ring = 칸 둘레에 「지금 여기」 동그라미, trace = 이미 그은 획을 빨갛게 덧긋는다. keep이 없으면 앞의 덧그은 것을 지운다.
 if(a.op==='pen-mark'){
  const f=fig();if(!f)return {error:`펜 그림 「${a.fig}」이 떠 있지 않음`};
  const e=part(f,a.id);if(!e)return {error:`펜 그림 「${a.fig}」에 그려져 있지 않음: ${a.id}`};
  if(!a.keep)f.querySelectorAll('[data-penmark]').forEach(m=>m.remove());
  const svg=f.querySelector('svg'),g=document.createElementNS(NS,'g');g.dataset.penmark=a.id;let t=0;
  const stroke=(d,w)=>{const q=document.createElementNS(NS,'path');q.setAttribute('d',d);q.setAttribute('fill','none');q.setAttribute('stroke',rgb(S.red));q.setAttribute('stroke-width',w);
   q.setAttribute('stroke-linecap','round');q.setAttribute('stroke-linejoin','round');g.append(q);svg.append(g);const len=q.getTotalLength(),ms=Math.round(Math.max(260,Math.min(900,len/(1.3*k))));
   q.style.strokeDasharray=len;q.style.strokeDashoffset=len;q.animate([{strokeDashoffset:len},{strokeDashoffset:0}],{duration:ms,delay:t,fill:'forwards',easing:'ease-in-out'});t+=ms+60;};
  if(a.kind==='trace'){const ps=[...f.querySelectorAll(`[data-stroke="${CSS.escape(a.id)}"] path`)];if(!ps.length)return {error:`덧그을 획이 없음: ${a.id}`};for(const q of ps)stroke(q.getAttribute('d'),S.penLine*k*1.5);}
  else{   // 칸을 두르는 둥근 고리. 왼쪽 위에서 시작해 한 바퀴를 조금 넘겨 돈다(손으로 친 동그라미)
   const b=(f.querySelector(`[data-stroke="${CSS.escape(a.id)}"]`)||e).getBoundingClientRect(),p=S.ringPad*k,x=b.x-p,y=b.y-p,w=b.width+2*p,h=b.height+2*p,r=Math.min(h/2,w/2,34*k);
   if(!inside(x-4*k,y-4*k,w+8*k,h+8*k))return {error:`동그라미가 화면 밖 — ${a.id}`};
   const tmp=document.createElementNS(NS,'path');tmp.setAttribute('d',`M ${x+r} ${y} L ${x+w-r} ${y} A ${r} ${r} 0 0 1 ${x+w} ${y+r} L ${x+w} ${y+h-r} A ${r} ${r} 0 0 1 ${x+w-r} ${y+h} L ${x+r} ${y+h} A ${r} ${r} 0 0 1 ${x} ${y+h-r} L ${x} ${y+r} A ${r} ${r} 0 0 1 ${x+r} ${y} Z`);svg.append(tmp);
   const len=tmp.getTotalLength(),n=80,cx=x+w/2,cy=y+h/2,pts=[];
   for(let i=0;i<=n;i++){const u=i/n*1.07,q=tmp.getPointAtLength((u*len)%len),grow=1+0.035*u,wob=Math.sin(u*9+a.id.length)*1.2*k;pts.push([cx+(q.x-cx)*grow+wob,cy+(q.y-cy)*grow-wob]);}
   tmp.remove();stroke('M '+pts.map(q=>R(q[0])+' '+R(q[1])).join(' L '),S.line*k);}
  return {dur:t};
 }
 if(a.op==='pen-where'){const f=fig();if(!f)return {error:`펜 그림 「${a.fig}」이 떠 있지 않음`};const e=f.querySelector(`[data-stroke="${CSS.escape(a.id)}"]`)||part(f,a.id);if(!e)return {error:`펜 그림 「${a.fig}」에 그려져 있지 않음: ${a.id}`};
  const b=e.getBoundingClientRect();return {box:[b.x,b.y,b.width,b.height]};}
 if(a.op==='pen-erase'){const f=fig();if(!f)return {error:`펜 그림 「${a.fig}」이 떠 있지 않음`};
  if(a.marks){f.querySelectorAll('[data-penmark]').forEach(m=>m.remove());return {};}
  for(const id of a.ids){const es=[...f.querySelectorAll(`[data-pen="${CSS.escape(id)}"],[data-stroke="${CSS.escape(id)}"],[data-penmark="${CSS.escape(id)}"]`)];if(!es.length)return {error:`지울 것이 그려져 있지 않음: ${id}`};es.forEach(e=>e.remove());}return {};}
 if(a.op==='pen-hide'){const f=fig();if(!f)return {error:`펜 그림 「${a.fig}」이 떠 있지 않음`};f.removeAttribute('data-fig');f.animate([{opacity:1},{opacity:0}],{duration:200,fill:'forwards'}).onfinish=()=>f.remove();return {dur:200};}

 // 글상자: lines = 줄 글 목록(없으면 걷는다), title = 머리 줄, at = 두 글자 자리(t 위 · b 아래 + l 왼쪽 · c 가운데 · r 오른쪽) 또는 왼쪽 위 [x, y] 프레임 px.
 if(a.op==='note'){
  const old=root()?.querySelector('[data-note]');
  if(a.lines==null){if(!old)return {error:'떠 있는 글상자가 없음'};old.removeAttribute('data-note');old.animate([{opacity:1},{opacity:0}],{duration:200,fill:'forwards'}).onfinish=()=>old.remove();return {dur:200};}
  old?.remove();
  const n=el('div',`position:absolute;padding:${14*k}px ${26*k}px;border-radius:${12*k}px;background:${S.board};color:${rgb(S.ink)};font:600 ${S.noteText*k}px/1.55 ${S.font};white-space:pre;box-shadow:0 ${8*k}px ${40*k}px rgba(0,0,0,.45)`);n.dataset.note='1';
  if(a.title){const h=el('div',`font-weight:700;opacity:.82;margin-bottom:${6*k}px`,n);h.textContent=a.title;}
  a.lines.forEach((s,i)=>{const l=el('div','',n);l.dataset.line=i+1;const sp=el('span','',l);sp.className='note-text';sp.textContent=s;});
  root(true).append(n);const m=28*k;
  if(Array.isArray(a.at)){n.style.left=a.at[0]*k+'px';n.style.top=a.at[1]*k+'px';}
  else{const at=a.at||'tr';if(!/^[tb][lcr]$/.test(at)){n.remove();return {error:'글상자 자리는 t|b + l|c|r 두 글자거나 [x, y] — '+at};}
   n.style[at[0]==='t'?'top':'bottom']=m+'px';if(at[1]==='c'){n.style.left='50%';n.style.transform='translateX(-50%)';}else n.style[at[1]==='l'?'left':'right']=m+'px';}
  const b=n.getBoundingClientRect();if(!inside(b.x,b.y,b.width,b.height)){n.remove();return {error:`글상자가 화면 밖 — ${JSON.stringify([b.x,b.y,b.width,b.height].map(R))}`};}
  n.animate([{opacity:0},{opacity:1}],{duration:200});return {dur:220};
 }
 return {error:'모르는 일 '+a.op};
 }catch(e){return {error:String(e?.message||e)};}
}

// clock() = 녹화 시계 ms, cue() = 지금 큐 id. p · serial · sleep은 ctrl.mjs의 것.
export function drawLayer({p,serial,sleep,clock,cue}){
 const who=()=>cue()??'(큐 밖)';
 const run=(fn,arg)=>serial(()=>p.evaluate(fn,arg));
 const page=async(what,arg)=>{const r=await run(drawInPage,{...arg,style:STYLE});if(r?.error)throw Error(`${who()}: ${what} — ${r.error}`);return r;};
 const hl=highlighter({clock,cue:who}),gone=new Set(),log=[];let figure=null,note=false;
 const note_=(o)=>log.push({cue:who(),time:clock(),...o});
 // 끝난 강조를 화면에서 지운다
 const sync=async()=>{const ids=hl.list.map((h,i)=>h.end!=null&&!gone.has(i)?i:-1).filter(i=>i>=0);if(!ids.length)return;ids.forEach(i=>gone.add(i));await page('강조 지우기',{op:'unmark',ids});};
 const d={marks:hl.list,log};
 d.reset=async()=>{await run(drawInPage,{op:'reset'});figure=null;note=false;};
 d.end=async why=>{if(!hl.list.some(h=>h.end==null))return false;hl.end(why);await sync();return true;};
 d.left=()=>[figure&&`펜 그림 「${figure}」`,note&&'글상자'].filter(Boolean);
 // 강조: target = 대상(머리말의 꼴), o = {shape(기본 band), phrase, keep, at({x, y} 화살표를 둘 자리), point(false면 화살표를 옮기지 않는다)}. move = 화살표 옮기기(강조를 끝내지 않는 것).
 d.emph=async(target,o={},move)=>{
  const shape=o.shape||'band';
  const t=await page('강조 대상',{op:'target',spec:target,phrase:o.phrase});
  const q={shape,phrase:t.phrase??undefined,keep:o.keep};
  const before=await hl.read(run,q);
  if(o.point!==false){   // 화살표는 글을 덮지 않는 자리에 둔다: 구절은 그 아래, 테두리 · 동그라미는 오른쪽 아래 바깥, 줄은 왼쪽 바깥
   const [x,y,w,h]=before[0];const at=o.at||(o.phrase?{x:x+w/2,y:y+h+6}:shape==='box'||shape==='circle'?{x:x+w+9,y:y+h+9}:{x:Math.max(4,x-26),y:y+h/2-6});await move(at.x,at.y);}
  await hl.mark(run,sleep,q,before);
  const i=hl.list.length-1;
  try{await page(`강조(${shape})`,{op:'mark',id:i,shape,rects:hl.list[i].rects});}catch(e){hl.list[i].end=clock();hl.list[i].endBy='그리지 못함';gone.add(i);await sync();throw e;}
  await sync();return hl.list[i];
 };
 // 펜 그림: def = {id, board:[x, y, w, h], items:[{id, kind:'box', at:[x, y, w, h], text, fill:'black'(속을 까맣게 — 생략 가능)} | {id, kind:'arrow', from, to, route:'under'|'over', drop} | {id, kind:'text', at:[x, y], text, size, color:'red'}]} — 프레임 px.
 d.pen=(def,move)=>{
  const bad=m=>{throw Error(`${who()}: 펜 그림 정의 — ${m}`);};
  if(!def?.id||!Array.isArray(def.board)||def.board.length!==4||!Array.isArray(def.items))bad('{id, board:[x, y, w, h], items:[…]} 꼴이 아님');
  const ids=def.items.map(i=>i.id);if(new Set(ids).size!==ids.length||ids.some(i=>!i))bad('items의 id가 비었거나 겹침');
  for(const it of def.items)if(!KINDS.includes(it.kind))bad(`「${it.id}」의 종류 ${it.kind} — ${KINDS.join(' | ')}`);
  const known=list=>{for(const id of list)if(!ids.includes(id))throw Error(`${who()}: 펜 그림 「${def.id}」의 정의에 없는 것: ${id}`);return list;};
  const put=async(what,list,animate)=>{const r=await page('펜 그림',{op:'pen',fig:def.id,board:def.board,items:def.items,ids:list.length?known(list):ids,animate});figure=def.id;note_({pen:def.id,op:what,ids:list.length?list:ids});await sleep(r.dur+60);};
  const mark=async(kind,id,o={})=>{await d.end('다음 대상');const r=await page('펜 그림',{op:'pen-mark',fig:def.id,kind,id:known([id])[0],keep:o.keep});note_({pen:def.id,op:kind,ids:[id]});await sleep(r.dur+60);};
  return {
   draw:(...list)=>put('draw',list,true),          // 한 획씩 긋는다(준 차례대로, 없으면 전부)
   show:(...list)=>put('show',list,false),         // 긋는 움직임 없이 띄운다(없으면 전부) — 「다시 띄우기」
   ring:(id,o)=>mark('ring',id,o),                 // 칸에 「지금 여기」 동그라미. 앞의 덧그은 것은 지운다({keep:true}면 둔다)
   trace:(id,o)=>mark('trace',id,o),               // 이미 그은 획(화살표)을 빨갛게 덧긋는다
   unmark:async()=>{await page('펜 그림',{op:'pen-erase',fig:def.id,marks:true});note_({pen:def.id,op:'unmark'});},
   erase:async(...list)=>{await page('펜 그림',{op:'pen-erase',fig:def.id,ids:known(list)});note_({pen:def.id,op:'erase',ids:list});},
   point:async id=>{const r=await page('펜 그림',{op:'pen-where',fig:def.id,id:known([id])[0]});const [x,y,w,h]=r.box;await move(x+Math.min(w*0.2,40),y+h+8);},   // 화살표를 그 칸 아래 왼쪽에 둔다(글을 덮지 않는다)
   hide:async()=>{await d.end('그림 걷기');const r=await page('펜 그림',{op:'pen-hide',fig:def.id});figure=null;note_({pen:def.id,op:'hide'});await sleep(r.dur+60);},
  };
 };
 // 글상자: note(['줄', …], {title, at}) 띄우기 · note(null) 걷기
 d.note=async(lines,o={})=>{
  if(lines!=null&&(!Array.isArray(lines)||!lines.length||lines.some(s=>typeof s!=='string'||!s)))throw Error(`${who()}: 글상자 — 줄 글 목록이 비었거나 글이 아님`);
  if(lines==null)await d.end('글상자 걷기');
  const r=await page('글상자',{op:'note',lines,title:o.title,at:o.at});note=lines!=null;note_({note:lines?lines.length:0});await sleep(r.dur+60);
 };
 return d;
}
