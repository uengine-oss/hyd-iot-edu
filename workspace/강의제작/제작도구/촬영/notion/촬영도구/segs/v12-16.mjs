// v12-16 · 16단계 두 상자 나란히 놓기 — 시작: 「Notion 익히기」, 회색 상자 「01 ·」 · 「02 ·」가 위아래. 끝: 두 칸(왼쪽 01 · 오른쪽 02), 칸마다 하위 페이지 하나.
// 끌기는 옛 seg-31과 같은 길(손잡이 누른 채 이동 → 놓기)이고, 손잡이를 잡기 전에 그 블록을 화면 안에 들인다.
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:16}];
export const ops=c=>{
 const noteRect=prefix=>c.serial(()=>c.raw.evaluate(prefix=>{const e=[...document.querySelectorAll('[role=note]')].find(e=>e.textContent.startsWith(prefix));if(!e)throw Error('Callout missing '+prefix);const r=e.getBoundingClientRect();if(r.top<0||r.bottom>innerHeight)throw Error('Drop target off screen: '+prefix);return{x0:r.x,x1:r.right,y0:r.top,y1:r.bottom};},prefix));
 const drop=async prefix=>{const r=await noteRect(prefix);await c.move(r.x0+70,r.y1-10);await c.sleep(300);await c.serial(()=>c.p.mouse.up());await c.sleep(500);};
 const inNote=title=>c.serial(()=>c.raw.waitForFunction(t=>[...document.querySelectorAll('a')].some(e=>e.textContent.trim()===t&&e.closest('[role=note]')),title,{timeout:6000})).catch(()=>{throw Error('Page not dropped into the box: '+title);});
 return{16:{
 둘째손잡이끌기:async()=>{await c.calloutHandleOf('02 ·');await c.serial(()=>c.p.mouse.down());const r=await noteRect('01 ·');await c.move(r.x1+12,r.y0+(r.y1-r.y0)*0.7);},
 놓기:async()=>{await c.sleep(300);await c.serial(()=>c.p.mouse.up());await c.sleep(500);await c.serial(()=>c.raw.waitForSelector('.notion-column-block',{state:'visible',timeout:6000}));},
 첫페이지넣기:async()=>{await c.handleOf(await c.pageBlock('첫 페이지 꾸미기'));await c.serial(()=>c.p.mouse.down());await drop('01 ·');await inNote('첫 페이지 꾸미기');},
 둘째페이지넣기:async()=>{await c.handleOf(await c.pageBlock('페이지 연결하기'));await c.serial(()=>c.p.mouse.down());await drop('02 ·');await inNote('페이지 연결하기');},
}};};
export async function after(c){const r=await c.serial(()=>c.raw.evaluate(()=>['첫 페이지 꾸미기','페이지 연결하기'].map(t=>{const a=[...document.querySelectorAll('a')].find(e=>e.textContent.trim()===t);return{title:t,box:a?.closest('[role=note]')?.textContent.slice(0,6)||null};})));
 await c.fs.writeFile(c.out+'/layout-result.json',JSON.stringify(r));if(r.some(x=>!x.box))throw Error('Child placement not complete '+JSON.stringify(r));}
