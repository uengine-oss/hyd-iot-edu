import {reveal} from './reveal.mjs';
export async function blockHandle(c,selector){
 await reveal(c,selector);
 const r=await c.serial(()=>c.p.evaluate(s=>{const r=document.querySelector(s).getBoundingClientRect();return {x:r.x+10,y:r.y+14};},selector));
 await c.move(r.x,r.y);
 await c.serial(()=>c.p.waitForFunction(s=>{const r=document.querySelector(s)?.getBoundingClientRect();return r&&[...document.querySelectorAll('[aria-label="드래그하여 이동하고 클릭하여 메뉴를 여세요"]')].some(e=>{const h=e.getBoundingClientRect(),hit=document.elementFromPoint(h.x+h.width/2,h.y+h.height/2);return h.width&&hit&&(hit===e||e.contains(hit))&&h.x<r.x&&Math.abs(h.y+12-(r.y+20))<25;});},selector,{timeout:6000}));
 const q=await c.serial(()=>c.p.evaluate(s=>{const r=document.querySelector(s).getBoundingClientRect();const e=[...document.querySelectorAll('[aria-label="드래그하여 이동하고 클릭하여 메뉴를 여세요"]')].find(e=>{const h=e.getBoundingClientRect(),hit=document.elementFromPoint(h.x+h.width/2,h.y+h.height/2);return h.width&&hit&&(hit===e||e.contains(hit))&&h.x<r.x&&Math.abs(h.y+12-(r.y+20))<25;});const h=e.getBoundingClientRect();return{x:h.x+h.width/2,y:h.y+h.height/2};},selector));await c.move(q.x,q.y);return q;
}
export async function calloutHandle(c,prefix){const s=await c.serial(()=>c.p.evaluate(prefix=>{const n=[...document.querySelectorAll('[role=note]')].find(e=>e.textContent.startsWith(prefix));return '.notion-callout-block[data-block-id="'+n.closest('.notion-callout-block').getAttribute('data-block-id')+'"]:has(>[role=note])';},prefix));return blockHandle(c,s);}
