import {navigation} from './ui-navigation.mjs';
export async function properties(ctx){
 const c=await navigation(ctx);
 c.slot=async name=>{
  const selector=await c.serial(()=>c.p.evaluate(name=>{
   const rows=[...document.querySelectorAll('[role=row]')].filter(e=>e.textContent.trim().startsWith(name));
   const row=rows.find(e=>e.closest('[aria-label="페이지 속성"]'))||rows[0];if(!row)throw Error('Property row missing: '+name);
   const cells=[...row.querySelectorAll('[role=cell]')];const target=cells.at(-1);if(!target)throw Error('Property value missing');
   target.setAttribute('data-tutorial-property','selected');return '[data-tutorial-property="selected"]';
  },name));await c.click('css',selector);await c.serial(()=>c.p.evaluate(()=>document.querySelector('[data-tutorial-property="selected"]')?.removeAttribute('data-tutorial-property')));
 };
 c.popupInput=async()=>{
  const selector=await c.serial(()=>c.p.evaluate(()=>{
   const es=[...document.querySelectorAll('input')].filter(e=>{const r=e.getBoundingClientRect();return e.checkVisibility({checkVisibilityCSS:true})&&r.top>=0&&r.bottom<=innerHeight;});
   if(es.length!==1)throw Error('Expected one popup input, got '+es.length);es[0].setAttribute('data-tutorial-input','active');return '[data-tutorial-input="active"]';
  }));await c.click('css',selector);
 };
 c.applyLink=async()=>{
  const selector=await c.serial(()=>c.p.evaluate(()=>{
   const es=[...document.querySelectorAll('[role=button],button')].filter(e=>['링크 임베드','링크 삽입','추가'].includes(e.textContent.trim())&&e.checkVisibility({checkVisibilityCSS:true}));
   if(es.length!==1)throw Error('Link apply button ambiguous '+es.length);es[0].setAttribute('data-tutorial-apply','link');return '[data-tutorial-apply="link"]';
  }));await c.click('css',selector);
 };
 return c;
}
