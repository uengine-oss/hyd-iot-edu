// Neo4j Browser · 안내 문서에서 짚을 대상을 찾는다 — record_graph_lesson.mjs의 mark · press · runCard 조작이 페이지에서 돌린다(길뚫기: 2026-11-20 이 PC, Neo4j 5.26 Browser).
// 대상 하나(q)는 아래 가운데 한 가지 열쇠로 정하고, 찾지 못하면 그 대상을 대며 멈춘다. 결과 카드는 위에서부터 센다(card, 0 = 맨 위 새 카드 — 이 판 Browser는 앞 카드를 접지 않는다).
//   입력칸     ed: '글 조각'(그 조각이 든 줄. 여러 줄에 있으면 line: 줄 번호) · edLine: 줄 번호(그 줄 전체) · edAll: true(입력칸 전체)
//   카드       head: '머리 줄 쿼리의 조각'(''면 머리 줄 쿼리 전체) · foot: '결과 아래 글의 조각' · tab: 'Graph' | 'Table' | 'Raw' · tabs: true(탭 묶음) · cardRun: true(카드 머리의 Run)
//   표         row: 행 번호 · rowHas: '칸 글'(그 글이 든 행) · col: '열 이름'(머리부터 끝 행까지) · colHead: '열 이름'(머리 글자) · headRow: true(머리 줄) · cell: [행 번호, '열 이름']
//   정보 칸    det: '속성 이름'(그 행. '<id>'도 같다) · detChip: true(레이블 이름표)
//   그림       node: '원의 이름' · edge: ['시작 원', '끝 원'](두 원 사이 화살표) · edgeLabel: '선 위 글' · mid: ['원', '원'](두 원 사이 빈 곳 — 강조 없이 화살표만)
//   그 밖      css: 선택자(+ text: 정확한 글 · contains: 든 글 · nth: 몇 번째 · inner: '그 안에서 이 글이 든 가장 작은 요소')
// 덧붙이는 값: phrase(대상 안의 구절만 — 한 번만 나와야 한다, occ를 주면 그 번째) · sub: [시작, 길이](구절 안의 그 글자들만) · match: 정규식(대상 글에서 맞은 부분만 — 포트처럼 PC마다 다른 글)
//   also: [대상, …](함께 짚는 대상 — 상자를 따로따로 그린다) · union: true(모두를 한 상자로) · clip: true(화면 밖으로 나간 큰 상자를 화면 안으로 자른다) · under: true(화살표를 대상 바로 밑에 — 누르지 않는 단추) · dx · dy
// 돌려주는 값: {rects: [[x, y, w, h], …](CSS px), anchor: 화살표 끝 자리, click: 누를 자리}. rects는 window.__hlTarget에도 둔다(hl.mjs가 강조 상자로 읽는다).
export function resolveInPage({q,shape,gsrc}){
 const graphTarget=gsrc?(0,eval)('('+gsrc+')'):null;
 const vis=e=>{if(!e)return false;const r=e.getBoundingClientRect();return r.width>0&&r.height>0;};
 const strip=s=>(s||'').replace(/\s+/g,'');
 const fail=(m,t)=>{throw Error('대상 없음 — '+m+' '+JSON.stringify(t??q));};
 const frames=()=>[...document.querySelectorAll('[data-testid="frame"]')].filter(f=>vis(f)&&strip(f.querySelector('[data-testid="frame-command"]')?.textContent).startsWith('neo4j$'));
 const merge=rs=>{const lines=[];
  for(const r of rs){if(r.width<=0||r.height<=0)continue;const c=r.top+r.height/2,l=lines.find(l=>c>l.t&&c<l.b);
   if(l){l.l=Math.min(l.l,r.left);l.r=Math.max(l.r,r.right);l.t=Math.min(l.t,r.top);l.b=Math.max(l.b,r.bottom);}else lines.push({l:r.left,t:r.top,r:r.right,b:r.bottom});}
  return lines.map(l=>[l.l,l.t,l.r-l.l,l.b-l.t]);};
 const phraseRects=(el,phrase,sub,occ,t)=>{
  const nodes=[],w=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);let all='';
  for(let n;(n=w.nextNode());){nodes.push([n,all.length]);all+=n.data;}
  const hits=[];for(let i=all.indexOf(phrase);i>=0;i=all.indexOf(phrase,i+1))hits.push(i);
  if(occ===undefined?hits.length!==1:!(occ<hits.length))fail(`구절 「${phrase}」이 대상 안에 ${hits.length}번`,t);
  const s=hits[occ??0]+(sub?sub[0]:0),n=sub?sub[1]:phrase.length;
  const at=k=>{const [nd,o]=[...nodes].reverse().find(([,o])=>o<=k)||nodes[0];return [nd,Math.min(k-o,nd.data.length)];};
  const g=document.createRange(),a=at(s),b=at(s+n-1);g.setStart(a[0],a[1]);g.setEnd(b[0],b[1]+1);
  return merge([...g.getClientRects()]);};
 const table=t=>{const f=frames()[t.card??0]||fail('결과 카드',t),tb=[...f.querySelectorAll('[role="table"]')].find(vis)||fail('표',t);
  const heads=[...tb.querySelectorAll('[role="columnheader"]')],rows=[...tb.querySelectorAll('[role="row"]')].filter(r=>r.querySelector('[role="cell"]'));
  const ci=name=>{const i=heads.findIndex(h=>h.textContent.trim()===name);if(i<0)fail('열 '+name,t);return i;};
  return {heads,rows,ci};};
 const one=t=>{
  let el=null,phrase=t.phrase,rects=null,anchor=null,click=null;
  if(t.node!==undefined||t.edge||t.mid||t.edgeLabel!==undefined){
   if(!graphTarget)fail('그림 대상 찾기 없음',t);
   if(t.node!==undefined){const c=graphTarget({label:t.node});rects=[[c.x-c.r,c.y-c.r,2*c.r,2*c.r]];click={x:c.x,y:c.y};anchor={x:c.x+c.r*.5,y:c.y+c.r*.55};}
   else if(t.mid){const a=graphTarget({label:t.mid[0]}),b=graphTarget({label:t.mid[1]}),x=(a.x+b.x)/2,y=(a.y+b.y)/2;rects=[[x-4,y-4,8,8]];click=anchor={x,y};}
   else if(t.edge){const a=graphTarget({label:t.edge[0]}),b=graphTarget({label:t.edge[1]}),d=Math.hypot(b.x-a.x,b.y-a.y),ux=(b.x-a.x)/d,uy=(b.y-a.y)/d;
    const x0=a.x+ux*a.r,y0=a.y+uy*a.r,x1=b.x-ux*b.r,y1=b.y-uy*b.r,pad=t.pad??16,L=Math.min(x0,x1)-pad*Math.abs(uy),T=Math.min(y0,y1)-pad*Math.abs(ux),R=Math.max(x0,x1)+pad*Math.abs(uy),B=Math.max(y0,y1)+pad*Math.abs(ux);
    rects=[[L,T,R-L,B-T]];click={x:a.x+(b.x-a.x)*.35,y:a.y+(b.y-a.y)*.35};anchor={x:(x0+x1)/2+6-uy*10,y:(y0+y1)/2+ux*10+4};}
   else{const cv=[...document.querySelectorAll('[data-testid="nvl-c2d-canvas"]')].find(vis)||fail('그림',t),tx=window.__forestRead?.texts.filter(x=>x.canvas===cv&&x.text===t.edgeLabel&&x.bx).at(-1)||fail('선 위 글',t);
    const r=cv.getBoundingClientRect(),[a,b,c,d]=tx.bx,pad=4;rects=[[r.x+a*r.width-pad,r.y+b*r.height-pad,(c-a)*r.width+2*pad,(d-b)*r.height+2*pad]];
    click={x:rects[0][0]+rects[0][2]/2,y:rects[0][1]+rects[0][3]/2};anchor={x:rects[0][0]+rects[0][2]+6,y:click.y+6};}
   return {rects,anchor,click};
  }
  if(t.ed!==undefined||t.edLine||t.edAll){
   const ed=[...document.querySelectorAll('[aria-label="Cypher Editor"]')].find(vis)||fail('입력칸',t),lines=[...ed.querySelectorAll('.cm-line')];
   if(t.edAll)el=ed;
   else if(t.edLine){el=lines[t.edLine-1]||fail('입력칸 줄',t);phrase=el.textContent.trim();}
   else{const has=lines.filter(l=>l.textContent.includes(t.ed));el=t.line?lines[t.line-1]:has[0];if(!el||!el.textContent.includes(t.ed))fail('입력칸 글',t);if(!t.line&&has.length>1)fail('입력칸 글이 여러 줄에 있다(line을 준다)',t);phrase=t.ed;}
  }
  else if(t.head!==undefined){el=(frames()[t.card??0]||fail('결과 카드',t)).querySelector('[data-testid="frame-command"] pre');phrase=t.head||undefined;}
  else if(t.foot!==undefined){const f=frames()[t.card??0]||fail('결과 카드',t);el=[...f.querySelectorAll('span,div,p')].find(e=>vis(e)&&e.textContent.includes(t.foot)&&![...e.children].some(k=>k.textContent.includes(t.foot)))||fail('결과 아래 글',t);phrase=t.foot;}
  else if(t.tab){el=[...(frames()[t.card??0]||fail('결과 카드',t)).querySelectorAll('[role="tab"]')].find(e=>vis(e)&&e.textContent.trim()===t.tab);}
  else if(t.tabs){el=[...(frames()[t.card??0]||fail('결과 카드',t)).querySelectorAll('[role="tablist"]')].find(vis);}
  else if(t.cardRun){el=[...(frames()[t.card??0]||fail('결과 카드',t)).querySelectorAll('button')].find(b=>vis(b)&&b.textContent.trim()==='Run');}
  else if(t.cell){const {rows,ci}=table(t),c=rows[t.cell[0]-1]?.querySelectorAll('[role="cell"]')[ci(t.cell[1])]||fail('표의 칸',t);el=t.phrase?c:(c.firstElementChild||c);}
  else if(t.colHead){const {heads,ci}=table(t),h=heads[ci(t.colHead)];el=h.querySelector('span[title]')||h;}
  else if(t.headRow){const {heads}=table(t);el=heads[0]?.parentElement;}
  else if(t.rowHas!==undefined){const {rows}=table(t),want=strip(t.rowHas),has=rows.filter(r=>[...r.querySelectorAll('[role="cell"]')].some(c=>strip(c.textContent).includes(want)));if(has.length>1&&t.nth===undefined)fail('그 글이 든 행이 여럿(nth를 준다)',t);el=has[t.nth??0];}
  else if(t.row){const {rows}=table(t);el=rows[t.row-1];}
  else if(t.col){const {heads,rows,ci}=table(t),i=ci(t.col),h=heads[i].getBoundingClientRect(),last=rows.at(-1).querySelectorAll('[role="cell"]')[i].getBoundingClientRect();
   rects=[[h.x,h.y,h.width,last.bottom-h.y]];click={x:h.x+h.width/2,y:h.y+h.height/2};anchor={x:h.x+110,y:h.y+h.height/2+6};return {rects,anchor,click};}
  else if(t.det!==undefined||t.detChip){const pane=[...document.querySelectorAll('[data-testid="nvl-paginated-details-pane"]')].find(vis)||fail('정보 칸',t);
   if(t.detChip)el=pane.querySelector('section button[title]');
   else el=[...(pane.querySelector('[data-testid="viz-details-pane-properties-table"]')?.children||[])].find(r=>r.children.length>1&&r.firstElementChild.textContent.trim()===t.det);}
  else if(t.css){let all=[...document.querySelectorAll(t.css)].filter(vis);if(t.text!==undefined)all=all.filter(e=>e.textContent.trim()===t.text);if(t.contains)all=all.filter(e=>e.textContent.includes(t.contains));el=all[t.nth??0];
   if(el&&t.inner){const want=strip(t.inner);el=[...el.querySelectorAll('*')].find(e=>vis(e)&&strip(e.textContent).includes(want)&&![...e.children].some(k=>strip(k.textContent).includes(want)))||fail('그 글이 든 요소',t);}}
  else fail('모르는 대상 꼴',t);
  if(!vis(el))fail('화면에 보이지 않음',t);
  if(t.match){const m=el.textContent.match(new RegExp(t.match));if(!m)fail('정규식에 맞는 글',t);phrase=m[0];}
  if(phrase)rects=phraseRects(el,phrase,t.sub,t.occ,t);
  else if(shape==='underline'){const g=document.createRange();g.selectNodeContents(el);rects=merge([...g.getClientRects()]);}
  else rects=merge([...el.getClientRects()]);
  if(!rects.length)fail('잴 상자가 없음',t);
  const b=el.getBoundingClientRect(),R=rects[0],wide=el.matches('[role="row"]');
  click={x:b.x+b.width/2,y:b.y+b.height/2};
  anchor=wide?{x:R[0]+R[2]*.3,y:R[1]+R[3]/2+8}:R[3]<=64?{x:R[0]+Math.min(R[2]/2,90)+14,y:R[1]+R[3]/2+8}:{x:R[0]+Math.min(R[2]*.5,160),y:R[1]+Math.min(R[3]*.5,120)};
  return {rects,anchor,click};
 };
 const first=one(q);let rects=[...first.rects];
 for(const t of q.also||[])rects.push(...one(t).rects);
 if(q.union){const L=Math.min(...rects.map(r=>r[0])),T=Math.min(...rects.map(r=>r[1])),R=Math.max(...rects.map(r=>r[0]+r[2])),B=Math.max(...rects.map(r=>r[1]+r[3]));rects=[[L,T,R-L,B-T]];}
 if(q.clip){const m=10;rects=rects.map(([x,y,w,h])=>{const L=Math.max(x,m),T=Math.max(y,m),R=Math.min(x+w,innerWidth-m),B=Math.min(y+h,innerHeight-m);return [L,T,R-L,B-T];});}
 let anchor=first.anchor;
 if(q.union||q.clip){const R=rects[0];anchor=R[3]<=64?{x:R[0]+Math.min(R[2]/2,90)+14,y:R[1]+R[3]/2+8}:{x:R[0]+Math.min(R[2]*.5,160),y:R[1]+Math.min(R[3]*.5,120)};}
 if(q.under){const R=rects[0];anchor={x:R[0]+R[2]/2,y:R[1]+R[3]+6};}
 anchor={x:anchor.x+(q.dx||0),y:anchor.y+(q.dy||0)};
 if(anchor.x<2||anchor.y<2||anchor.x>innerWidth-2||anchor.y>innerHeight-2)fail('화살표 자리가 화면 밖 '+JSON.stringify(anchor));
 window.__hlTarget={rects};
 return {rects,anchor,click:first.click};
}

// 맨 위 결과 카드의 상태. 인자가 없으면 카드 수만 돌려주고, 있으면 Run 뒤에 새 카드가 생겨 기대한 결과(summary: 결과 글 · graph: 원 nodes개와 선 edges개 · rows: 표의 행 수)를 담았는지 본다.
export function cardState(want){
 const vis=e=>{if(!e)return false;const r=e.getBoundingClientRect();return r.width>0&&r.height>0;};
 const fs=[...document.querySelectorAll('[data-testid="frame"]')].filter(f=>vis(f)&&(f.querySelector('[data-testid="frame-command"]')?.textContent||'').replace(/\s+/g,'').startsWith('neo4j$'));
 if(!want)return {count:fs.length};
 if(fs.length<=want.n0)return false;
 const f=fs[0];
 if(want.summary&&!f.innerText.includes(want.summary))return false;
 if(want.graph){const s=[...f.querySelectorAll('[role="status"]')].find(e=>e.textContent.startsWith('A graph visualization'));
  if(!s||!s.textContent.includes(`with ${want.nodes} ${want.nodes===1?'node':'nodes'} and ${want.edges} ${want.edges===1?'relationship':'relationships'}`))return false;}
 if(want.rows!==undefined&&want.rows!==null){const tb=[...f.querySelectorAll('[role="table"]')].find(vis);if(!tb||[...tb.querySelectorAll('[role="row"]')].filter(r=>r.querySelector('[role="cell"]')).length!==want.rows)return false;}
 return true;
}

// press 뒤에 기다릴 화면: css(보이는 요소가 있다) · gone(보이는 요소가 없다) · button(그 글의 단추가 보인다) · details(정보 칸에 그 글이 있다) · tab(맨 위 카드에서 그 탭이 골라졌다) · rows(맨 위 카드 표의 행 수)
export function expectInPage(e){
 const vis=x=>{if(!x)return false;const r=x.getBoundingClientRect();return r.width>0&&r.height>0;};
 if(e.css&&![...document.querySelectorAll(e.css)].some(vis))return false;
 if(e.gone&&[...document.querySelectorAll(e.gone)].some(vis))return false;
 if(e.button&&![...document.querySelectorAll('button')].some(b=>vis(b)&&b.textContent.trim()===e.button))return false;
 if(e.details){const p=[...document.querySelectorAll('[data-testid="nvl-paginated-details-pane"]')].find(vis);if(!p||!p.innerText.includes(e.details))return false;}
 const f=[...document.querySelectorAll('[data-testid="frame"]')].find(f=>vis(f)&&(f.querySelector('[data-testid="frame-command"]')?.textContent||'').replace(/\s+/g,'').startsWith('neo4j$'));
 if(e.tab&&![...(f?.querySelectorAll('[role="tab"]')||[])].some(t=>vis(t)&&t.textContent.trim()===e.tab&&t.getAttribute('aria-selected')==='true'))return false;
 if(e.rows!==undefined){const tb=[...(f?.querySelectorAll('[role="table"]')||[])].find(vis);if(!tb||[...tb.querySelectorAll('[role="row"]')].filter(r=>r.querySelector('[role="cell"]')).length!==e.rows)return false;}
 return true;
}
