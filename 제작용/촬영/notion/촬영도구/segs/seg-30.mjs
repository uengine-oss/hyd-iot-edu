// v10 이식: film-commands/30.mjs 
import {v10} from '../ui.mjs';
export default async ctx=>{
 const c=await v10(ctx);await c.begin();
 await c.say('live-layout-intro');await c.source('N18-01',()=>c.endText('나의 페이지'));await c.source('N18-02',()=>c.key('Enter'));
 await c.say('live-filter-callout-r3',()=>c.type('/콜아웃'));await c.source('N18-04',()=>c.click('menu','콜아웃'));
 await c.say('live-bold-short-r2',()=>c.key('Control+b'));await c.source('N18-05',()=>c.type('01 · 글 정리하기'));await c.say('live-normal-short-r2',()=>c.key('Control+b'));
 await c.source('N18-06',()=>c.key('Shift+Enter'));await c.source('N18-07',()=>c.type('제목·목록·토글로'));await c.source('N18-08',()=>c.key('Shift+Enter'));await c.source('N18-09',()=>c.type('읽기 편하게 정리합니다.'));
 await c.source('N18-13',()=>c.noteHandle());await c.source('N18-14',async()=>{const q=await c.locate('menu','색');await c.move(q.x,q.y);});await c.source('N18-15',async()=>{await c.hoverColor('회색 배경');await c.click('menu','회색 배경');});
 await c.say('live-callout-exit-first-v2-r4',async()=>{await c.endOf('[role=note] [contenteditable=true][role=textbox]');await c.key('Enter');});await c.say('live-callout-exit-second-r4',()=>c.exitCallout());
 await c.say('live-filter-callout-r4',()=>c.type('/콜아웃'));await c.source('N18-20',()=>c.click('menu','콜아웃'));
 await c.say('live-bold-short-r3',()=>c.key('Control+b'));await c.source('N18-21',()=>c.type('02 · 내용 연결하기'));await c.say('live-normal-short-r3',()=>c.key('Control+b'));
 await c.source('N18-22',()=>c.key('Shift+Enter'));await c.source('N18-23',()=>c.type('하위 페이지와 링크로'));await c.source('N18-24',()=>c.key('Shift+Enter'));await c.source('N18-25',()=>c.type('내용을 이어 갑니다.'));
 await c.source('N18-28',()=>c.noteHandle());await c.source('N18-29',async()=>{const q=await c.locate('menu','색');await c.move(q.x,q.y);});await c.source('N18-30',async()=>{await c.hoverColor('회색 배경');await c.click('menu','회색 배경');});
 await c.fs.writeFile(c.out+'/layout-dom.json',JSON.stringify(await c.serial(()=>c.p.evaluate(()=>[...document.querySelectorAll('[role=note],a,[role=link]')].filter(e=>/01 ·|02 ·|첫 페이지 꾸미기|페이지 연결하기/.test(e.textContent)).map(e=>({html:e.outerHTML.slice(0,3500),parent:e.parentElement.outerHTML.slice(0,4500)})))),null,2));
 return 'Two layout callouts created; drag targets observed';
};
