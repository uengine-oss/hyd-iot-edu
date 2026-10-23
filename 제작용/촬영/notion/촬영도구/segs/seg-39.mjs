// v10 이식: film-commands/39.mjs
import {v10} from '../ui.mjs';
export default async ctx=>{
 const c=await v10(ctx);await c.begin();
 await c.say('live-export-subpages',async()=>{
  const q=await c.serial(()=>c.p.evaluate(()=>{
   const es=[...document.querySelectorAll('[role=switch],[role=checkbox],input[type=checkbox]')].filter(e=>e.checkVisibility({checkVisibilityCSS:true}));
   for(const e of es){let parent=e;for(let i=0;i<4&&parent;i++,parent=parent.parentElement){const text=parent.textContent.trim();if(text.includes('하위 페이지 포함')&&!text.includes('하위 페이지용 폴더')){
    const v=e.getAttribute('aria-checked')??(e.tagName==='INPUT'?String(e.checked):null)??e.getAttribute('data-state');const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2,value:v};
   }}}throw Error('Subpage option not identified');
  }));
  if(q.value==='false'||q.value==='unchecked'){await c.move(q.x,q.y);await c.serial(()=>c.p.mouse.click(q.x,q.y));}
  else if(q.value!=='true'&&q.value!=='checked')throw Error('Subpage option state unknown: '+q.value);
 });
 await c.say('live-export-download',async()=>{
  const url=await c.serial(()=>c.p.url());if(url.includes(ctx.protect))throw Error('Original workspace export forbidden');
  const downloadPromise=c.p.waitForEvent('download',{timeout:60000});await c.click('text','내보내기');const download=await downloadPromise;await download.saveAs(c.out+'/학습노트_내보내기.zip');
 });
 await c.say('live-export-saved');await c.say('live-export-copy-explain');await c.say('live-wrap-home');await c.say('live-layout-down',()=>c.scroll(400));
 await c.source('N29-01',()=>c.click('text','Notion 익히기'));await c.say('live-peek-full',()=>c.click('css','[role=region] a[aria-label="전체 페이지로 열기"]'));await c.say('live-layout-down',()=>c.scroll(550));
 await c.source('N29-02',()=>c.link('첫 페이지 꾸미기'));await c.line('제목과 목록, 토글, 목차가 한 페이지에 들어 있습니다.');await c.source('N29-03',()=>c.link('Notion 익히기',true));await c.say('live-layout-down',()=>c.scroll(550));await c.source('N29-04',()=>c.link('페이지 연결하기'));await c.line('순서와 도움말 링크가 남아 있죠.');await c.source('N29-05',()=>c.home());
 await c.say('live-wrap-end');
 return 'DONE';
};
