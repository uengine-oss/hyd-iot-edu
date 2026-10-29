// 구간37 뒷부분(take-37이 제목 선택 확인에서 멈춤 — 키보드 선택이 '새'만 잡음). 같은 화면(새 주제 페이지, 제목 '새 주제')에서 제목 바꾸기부터 잇는다.
import {v10} from '../ui.mjs';
export default async ctx=>{
 const c=await v10(ctx);await c.begin();
 await c.say('live-reading-title',()=>c.replaceTitle('나만의 독서 기록'));
 await c.say('live-reading-scroll',()=>c.scroll(350));await c.say('live-reading-select-description',()=>c.selectText('이 주제에서 알고 싶은 것, 기억하고 싶은 것을 한 줄로 적어 보세요.'));
 await c.say('live-reading-replace-description',()=>c.type('읽으면서 남기고 싶은 생각과 자료를 모읍니다.'));
 await c.say('live-template-independent');
 await c.say('live-reading-position',async()=>{await c.endText('나의 기록');await c.key('Enter');});
 await c.say('live-page-search',()=>c.type('/페이지'));await c.source('N16-03',()=>c.click('menu','페이지'));await c.say('live-reading-page-title',async()=>{await c.click('title','');await c.type('다음에 읽을 책');});
 await c.say('live-page-enter',()=>c.key('Enter'));await c.say('live-reading-body',()=>c.type('읽고 싶은 책과 그 이유를 짧게 남깁니다.'));
 await c.say('live-home-list',()=>c.home());
 return 'Template applied and customized with a child page';
};
