// 강조 기록(영상 V-14 · V-11) — 포털 녹화기(take.mjs · segs/map.mjs), Neo4j 녹화기(record_graph_lesson.mjs), ARROWS 녹화기(arrows/촬영도구/ctrl.mjs · ui.mjs)가 함께 쓴다. 그리는 것은 합성기 encode.py다(화살표를 그리는 같은 자리).
// 짚기 조작의 대상이 강조 모양(hl)을 가지면, 녹화기는 화살표가 그 대상에 닿은 때 실제로 잰 화면 상자와 시각을 timing.json의 highlights에 남긴다:
//   {cue(큐 id), shape, rects([[x, y, w, h], …] CSS px · 뷰포트 기준, 줄마다 하나), start · end(녹화 시계 ms), endBy(끝난 까닭)}
// 모양(hl): underline = 글자 아래 선(낱말 · 값 하나), band = 반투명 노랑 띠(화면 글을 읽거나 「이 줄 · 이 행」), box = 둘레 선(칸 · 상자 하나), circle = 둥근 둘레 선(그림판의 원 하나 — 상자에 내접하는 원, 상자마다 하나). 고르는 기준은 영상 V-11.
// 잴 상자: 구절(phrase)이 있으면 그 구절의 글자 상자(대상 요소 안에 한 번만 나와야 한다, 줄이 꺾이면 줄마다), underline은 대상 요소의 글자 상자, band · box · circle은 대상 요소의 상자,
//   캔버스 항목은 녹화기가 잰 상자다. 대상 요소는 녹화기의 대상 찾기가 window.__hlTarget에 둔다(요소, {box:[x, y, w, h]}, 또는 녹화기가 여러 대상을 함께 잰 {rects:[[x, y, w, h], …]}).
// 시각: 150ms 간격으로 두 번 재어 같을 때의 상자를 쓴다(화살표가 출발하기 전에 잰 것과 닿은 뒤 잰 것이 같으면 닿은 때가 시작이다).
// 끝: 다음 강조가 시작할 때(다음 강조에 keep이 있으면 함께 둔다 — 말이 두 대상을 함께 가리켜 견주는 자리, 영상 V-11. keep: true는 떠 있는 강조를 모두, keep: N은 먼저 뜬 N개만 남긴다), 그 전에 화면을 바꾸는 조작(누르기 · 굴리기 · 입력 · 붙여넣기 · 탭 바꾸기)이 시작할 때, 강조 없는 다른 대상으로 화살표가 떠날 때, 구간이 끝날 때 가운데 가장 이른 때 —
//   녹화기가 그 자리에서 end(까닭)를 부른다.
// 멈춤: 모르는 모양, 잡히지 않는 대상, 크기 0, 그릴 자리가 화면 밖(모양마다 둘레 여백 MARGIN), 멈추지 않는 대상은 큐 id와 값을 대며 그 큐에서 멈춘다(리허설에서도 같다).
export const SHAPES=['underline','band','box','circle'];
// 그릴 때 대상 상자 밖으로 나가는 폭(CSS px). encode.py의 선 굵기 · 여백(프레임 px)을 배율 1.25에서 덮는 값이다 — 합성기는 실제로 그릴 자리가 프레임 안인지 다시 본다.
export const MARGIN={underline:6,band:0,box:8,circle:8};

export function measureInPage({shape,phrase}){
 const t=window.__hlTarget;
 if(!t)return {error:'강조 대상이 잡히지 않음'};
 const round=v=>Math.round(v*100)/100;
 const merge=rs=>{const lines=[];
  for(const r of rs){if(r.width<=0||r.height<=0)continue;const c=r.top+r.height/2,l=lines.find(l=>c>l.t&&c<l.b);
   if(l){l.l=Math.min(l.l,r.left);l.r=Math.max(l.r,r.right);l.t=Math.min(l.t,r.top);l.b=Math.max(l.b,r.bottom);}else lines.push({l:r.left,t:r.top,r:r.right,b:r.bottom});}
  return lines.map(l=>[l.l,l.t,l.r-l.l,l.b-l.t].map(round));};
 let rects;
 if(Array.isArray(t.box))rects=[t.box.map(round)];
 else if(Array.isArray(t.rects))rects=t.rects.map(r=>r.map(round));
 else if(!t.isConnected)return {error:'강조 대상이 화면에서 사라짐'};
 else if(phrase){
  // 구절이 글자 조각 여럿(쿼리 입력칸의 낱말 조각 등)에 걸쳐도 찾는다
  const nodes=[],w=document.createTreeWalker(t,NodeFilter.SHOW_TEXT);let all='';
  for(let n;(n=w.nextNode());){nodes.push([n,all.length]);all+=n.data;}
  const hits=[];for(let i=all.indexOf(phrase);i>=0;i=all.indexOf(phrase,i+1))hits.push(i);
  if(hits.length!==1)return {error:`구절 「${phrase}」이 대상 안에 ${hits.length}번`};
  const at=k=>{const [n,o]=[...nodes].reverse().find(([,o])=>o<=k)||nodes[0];return [n,Math.min(k-o,n.data.length)];};
  const g=document.createRange(),a=at(hits[0]),b=at(hits[0]+phrase.length-1);g.setStart(a[0],a[1]);g.setEnd(b[0],b[1]+1);
  rects=merge([...g.getClientRects()]);
 }else if(shape==='underline'){const g=document.createRange();g.selectNodeContents(t);rects=merge([...g.getClientRects()]);
  if(!rects.length)return {error:'밑줄을 그을 글자가 대상에 없음(band나 box를 쓴다)'};}
 else rects=merge([...t.getClientRects()]);
 return {rects,vw:innerWidth,vh:innerHeight};
}

// clock() = 녹화 시계 ms, cue() = 지금 큐 id. read · mark의 run(fn, arg)는 그 녹화기의 직렬 큐로 페이지에서 fn을 돌린다.
export function highlighter({clock,cue}){
 const list=[];let open=[];
 const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
 const end=why=>{for(const h of open){h.end=clock();h.endBy=why;}open=[];};
 async function read(run,{shape,phrase}){
  if(!SHAPES.includes(shape))throw Error(`${cue()}: 모르는 강조 모양 「${shape}」 — ${SHAPES.join(' | ')}`);
  const r=await run(measureInPage,{shape,phrase});
  if(r.error)throw Error(`${cue()}: 강조(${shape}) — ${r.error}`);
  const m=MARGIN[shape];
  if(!r.rects.length)throw Error(`${cue()}: 강조(${shape}) 상자가 없음(크기 0)`);
  for(const [x,y,w,h] of r.rects){
   if(!(w>0&&h>0))throw Error(`${cue()}: 강조(${shape}) 상자 크기 0 — ${JSON.stringify([x,y,w,h])}`);
   if(x-m<0||y-(shape==='box'||shape==='circle'?m:0)<0||x+w+m>r.vw||y+h+m>r.vh)throw Error(`${cue()}: 강조(${shape})를 그릴 자리가 화면 ${r.vw}×${r.vh} 밖 — 상자 ${JSON.stringify([x,y,w,h])}, 둘레 여백 ${m}`);}
  return r.rects;
 }
 // before = 화살표가 출발하기 전에 read로 잰 상자. 닿은 뒤 다시 재어 같으면 지금이 시작이고, 다르면 150ms 간격으로 두 번 같을 때까지 잰다.
 async function mark(run,sleep,o,before){
  let m=await read(run,o);
  if(!same(m,before)){let ok=false;for(let i=0;i<10&&!ok;i++){await sleep(150);const n=await read(run,o);ok=same(m,n);m=n;}
   if(!ok)throw Error(`${cue()}: 강조 대상이 멈추지 않음`);}
  if(o.keep!==true){const stay=open.slice(0,o.keep||0);for(const h of open.slice(stay.length)){h.end=clock();h.endBy='다음 강조';}open=stay;}
  const h={cue:cue(),shape:o.shape,...(o.phrase?{phrase:o.phrase}:{}),rects:m,start:clock(),end:null,endBy:null};open.push(h);list.push(h);
 }
 return {list,end,read,mark};
}
