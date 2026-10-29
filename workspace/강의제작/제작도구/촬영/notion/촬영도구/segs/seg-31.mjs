// v10 이식: film-commands/31.mjs 
import {v10} from '../ui.mjs';
import {blockHandle,calloutHandle} from '../lib/block-handle.mjs';
export default async ctx=>{
 const c=await v10(ctx);await c.begin();
 await c.say('live-layout-down',()=>c.scroll(280));
 const handle=async selector=>{const q=await blockHandle(c,selector);await c.serial(()=>c.p.mouse.down());};
 const childHandle=async title=>{const selector=await c.serial(()=>c.p.evaluate(title=>{const a=[...document.querySelectorAll('a')].find(e=>e.textContent.trim()===title);return '.notion-page-block[data-block-id="'+a.closest('.notion-page-block').getAttribute('data-block-id')+'"]:has(a)';},title));await handle(selector);};
 await c.line('두 번째 상자를 옆으로 옮겨 나란히 놓아 볼게요.');
 await c.source('N18-33',async()=>{await calloutHandle(c,'02 ·');await c.serial(()=>c.p.mouse.down());const q=await c.serial(()=>c.p.evaluate(()=>{const r=[...document.querySelectorAll('[role=note]')].find(e=>e.textContent.startsWith('01 ·')).getBoundingClientRect();return{x:r.right+12,y:r.top+r.height*.7};}));await c.move(q.x,q.y);});
 await c.source('N18-34',async()=>{await c.sleep(300);await c.serial(()=>c.p.mouse.up());await c.sleep(500);await c.serial(()=>c.p.waitForSelector('.notion-column-block',{state:'visible',timeout:6000}));});
 await c.line('두 상자가 좌우로 나뉘면 된 겁니다.');
 await c.source('N18-35',()=>childHandle('첫 페이지 꾸미기'));
 const drop=async prefix=>{const q=await c.serial(()=>c.p.evaluate(prefix=>{const r=[...document.querySelectorAll('[role=note]')].find(e=>e.textContent.startsWith(prefix)).getBoundingClientRect();return{x:r.x+70,y:r.bottom-10};},prefix));await c.move(q.x,q.y);await c.sleep(300);await c.serial(()=>c.p.mouse.up());await c.sleep(500);};
 await c.source('N18-36',async()=>{await drop('01 ·');await c.serial(()=>c.p.waitForFunction(()=>[...document.querySelectorAll('a')].some(e=>e.textContent.trim()==='첫 페이지 꾸미기'&&e.closest('[role=note]')),undefined,{timeout:6000}));});
 await c.source('N18-37',async()=>{await childHandle('페이지 연결하기');await drop('02 ·');});
 await c.line('페이지 이름을 클릭하는 대신 손잡이를 잡아야 옮길 수 있습니다.');
 await c.line('왼쪽에는 글을 정리하는 페이지, 오른쪽에는 내용을 연결하는 페이지가 들어갔는지 보겠습니다.');
 const result=await c.serial(()=>c.p.evaluate(()=>['첫 페이지 꾸미기','페이지 연결하기'].map(t=>{const a=[...document.querySelectorAll('a')].find(e=>e.textContent.trim()===t);return {title:t,inside:!!a?.closest('[role=note]')};})));if(result.some(x=>!x.inside))throw Error('Child placement not complete');
 await c.fs.writeFile(c.out+'/layout-result.json',JSON.stringify({twoColumns:true,children:result}));
 await c.say('live-home-list',()=>c.home());return 'Columns and child pages placed';
};
