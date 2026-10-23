import {hideProperty} from './property-visibility.mjs';
export async function finishTable(c){
 await c.say('live-table-return',()=>c.click('text','전체 주제'));
 await c.say('fix-visible-properties',()=>c.click('css','.notion-collection-edit-view'));
 await c.say('live-table-visible',()=>c.click('menu','속성 표시 여부'));
 for(const [name,id] of [['생성일','live-hide-created'],['태그','live-hide-tags'],['카드 이미지','live-hide-image']])await c.say(id,()=>hideProperty(c,name));
 await c.say('fix-close-settings',()=>c.click('aria','닫기'));
 await c.say('live-table-result');
 await c.say('live-search-start',async()=>{await c.click('aria','검색');await c.serial(()=>c.p.waitForFunction(()=>[...document.querySelectorAll('input')].some(e=>e.placeholder==='검색어를 입력하세요…'&&e.checkVisibility({checkVisibilityCSS:true})),undefined,{timeout:6000}));});
 await c.say('live-search-query',async()=>{await c.click('css','input[placeholder="검색어를 입력하세요…"]');await c.type('지식');await c.serial(()=>c.p.waitForFunction(()=>{const t=document.querySelector('.notion-table-view')?.innerText;return t?.includes('지식 자산화')&&!t.includes('Notion 익히기');},undefined,{timeout:6000}));});
 await c.say('live-search-result');
 await c.say('live-search-clear',async()=>{await c.click('css','input[placeholder="검색어를 입력하세요…"]');await c.key('Control+a');await c.key('Backspace');await c.serial(()=>c.p.waitForFunction(()=>document.querySelector('.notion-table-view')?.innerText.includes('Notion 익히기'),undefined,{timeout:6000}));});
 await c.say('fix-search-close',()=>c.key('Escape'));
 await c.say('live-gallery-return',()=>c.click('text','주제 카드'));
}
