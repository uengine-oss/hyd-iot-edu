// 구간39 뒷부분(take-n39가 둘러보기에서 멈춤 — Notion 업데이트 막대로 본문이 밀려 「첫 페이지 꾸미기」 링크가 화면 끝에 걸림). take-n39 73.2s(live-layout-down-r3 직전),
// 「Notion 익히기」 전체 페이지 맨 위에서 잇는다. 막대는 새로고침으로 사라진 상태.
import {v10} from '../ui.mjs';
export default async ctx=>{
 const c=await v10(ctx);await c.begin();
 await c.say('live-layout-down-r3',()=>c.scroll(550));
 await c.source('N29-02',()=>c.link('첫 페이지 꾸미기'));await c.line('제목과 목록, 토글, 목차가 한 페이지에 들어 있습니다.');await c.source('N29-03',()=>c.link('Notion 익히기',true));await c.say('live-layout-down-r4',()=>c.scroll(550));await c.source('N29-04',()=>c.link('페이지 연결하기'));await c.line('순서와 도움말 링크가 남아 있죠.');await c.source('N29-05',()=>c.home());
 // 마무리: 완성한 홈을 짚으며 오늘 만든 것을 정리하고 끝인사.
 await c.say('new-wrap-structure',()=>c.hoverSel('[role=note]'));
 await c.say('new-wrap-features',()=>c.hoverLabel('전체 주제'));
 await c.say('new-wrap-close');
 return 'DONE';
};
