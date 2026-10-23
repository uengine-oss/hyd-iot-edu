export function extend(c){
 c.locate=async(kind,value)=>{
  for(let attempt=0;attempt<20;attempt++){
   const q=await c.serial(()=>c.p.evaluate(({kind,value})=>{
    const visible=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&e.checkVisibility({checkVisibilityCSS:true});};
    let es=[];
    if(kind==='aria')es=[...document.querySelectorAll('[role=button],button')].filter(e=>e.getAttribute('aria-label')===value);
    if(kind==='css')es=[...document.querySelectorAll(value)];
    if(kind==='title')es=[...document.querySelectorAll('h1[contenteditable=true]')];
    if(kind==='body')es=[...document.querySelectorAll('[contenteditable=true][role=textbox]')].filter(e=>e.tagName!=='H1'&&!e.getAttribute('aria-label')&&!e.textContent.trim());
    if(kind==='menu')es=[...document.querySelectorAll('[role=menuitem],[role=option],[role=gridcell]')].filter(e=>['파란색 배경','회색 배경'].includes(value)?e.textContent.trim()===value:e.textContent.trim().replace(/\s/g,'').startsWith(value.replace(/\s/g,''))&&!e.textContent.includes('전환'));
    if(kind==='text'){
     const all=[...document.querySelectorAll('div,span,a,button')].filter(e=>e.textContent.trim()===value&&visible(e));
     es=all.filter(e=>!all.some(other=>other!==e&&e.contains(other)));
    }
    es=es.filter(visible);if(kind==='body')es=es.slice(-1);if(kind==='menu')es=es.slice(0,1);
    if(!es.length)return {missing:true};
    const hit=es.filter(e=>{const r=e.getBoundingClientRect();const h=document.elementFromPoint(r.x+Math.min(45,r.width/2),r.y+r.height/2);return h&&(e===h||e.contains(h));});
    if(hit.length===1)es=hit;
    if(es.length!==1)throw Error('Ambiguous '+kind+' '+value+': '+es.length);
    const e=es[0],r=e.getBoundingClientRect(),token='target-'+Date.now();e.setAttribute('data-tutorial-locate',token);
    return{x:r.x+Math.min(45,r.width/2),y:r.y+r.height/2,scroll:r.top<0||r.bottom>innerHeight-5,selector:'[data-tutorial-locate="'+token+'"]'};
   },{kind,value}));
   if(q.missing){await c.sleep(200);continue;}
   if(q.scroll){try{await c.serial(()=>c.p.hover(q.selector));}catch(e){if(!/matched 0|not connected/.test(String(e)))throw e;}await c.sleep(250);continue;}
   return q;
  }
  throw Error('Target not visible after waiting: '+kind+' '+value);
 };
 c.click=async(kind,value)=>{
  const before=kind==='menu'&&value==='페이지'?await c.serial(()=>c.p.url()):null;
  for(let i=0;i<5;i++){
   const q=await c.locate(kind,value);await c.move(q.x,q.y);const now=await c.locate(kind,value);
   if(Math.hypot(now.x-q.x,now.y-q.y)>2)continue;
   await c.serial(()=>c.p.mouse.click(now.x,now.y));await c.sleep(450);
   if(kind==='menu'&&['콜아웃','제목2','글머리 기호 목록','번호 매기기 목록','토글 목록','구분선','할 일 목록','목차'].includes(value))await c.serial(()=>c.p.waitForFunction(s=>{const e=document.querySelector(s);return !e||!e.checkVisibility({checkVisibilityCSS:true});},now.selector,{timeout:7000}));
   if(before)await c.serial(()=>c.p.waitForFunction(url=>location.href!==url, before,{timeout:10000}));
   if(kind==='text'&&value==='새로 만들기')await c.serial(()=>c.p.waitForSelector('[role=region] a[aria-label="전체 페이지로 열기"]'));
   if(kind==='css'&&value==='[role=region] a[aria-label="전체 페이지로 열기"]')await c.serial(()=>c.p.waitForFunction(()=>!document.querySelector('[role=region] a[aria-label="전체 페이지로 열기"]')));
   if(kind==='title'||(kind==='css'&&value.includes('contenteditable'))){
    const focusSelector=kind==='title'?'h1[contenteditable=true]':value;
    const focused=await c.serial(()=>c.p.evaluate(s=>document.activeElement?.matches(s),focusSelector));
    if(!focused){await c.serial(()=>c.p.click(focusSelector));await c.sleep(200);}
   }
   return;
  }
  throw Error('Target layout did not settle: '+kind+' '+value);
 };
 return c;
}
