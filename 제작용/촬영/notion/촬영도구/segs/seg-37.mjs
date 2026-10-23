// v10 이식: film-commands/37.mjs 
import {v10} from '../ui.mjs';
export default async ctx=>{
 const c=await v10(ctx);await c.begin();
 await c.say('live-template-apply',async()=>{await c.click('aria','추가 옵션 더 보기');await c.click('text','새 주제');});await c.say('live-template-result');
 await c.say('live-peek-full-r5',()=>c.click('css','[role=region] a[aria-label="전체 페이지로 열기"]'));
 await c.say('live-reading-title',()=>c.replaceTitle('나만의 독서 기록'));
 await c.say('live-reading-scroll',()=>c.scroll(350));await c.say('live-reading-select-description',()=>c.selectText('이 주제에서 알고 싶은 것, 기억하고 싶은 것을 한 줄로 적어 보세요.'));
 await c.say('live-reading-replace-description',()=>c.type('읽으면서 남기고 싶은 생각과 자료를 모읍니다.'));
 await c.say('live-template-independent');
 await c.say('live-reading-position',async()=>{await c.endText('나의 기록');await c.key('Enter');});
 await c.say('live-page-search-r3',()=>c.type('/페이지'));await c.source('N16-03',()=>c.click('menu','페이지'));await c.say('live-reading-page-title',async()=>{await c.click('title','');await c.type('다음에 읽을 책');});
 await c.say('live-page-enter-r5',()=>c.key('Enter'));await c.say('live-reading-body',()=>c.type('읽고 싶은 책과 그 이유를 짧게 남깁니다.'));
 await c.say('live-home-list-r5',()=>c.home());
 return 'Template applied and customized with a child page';
};
