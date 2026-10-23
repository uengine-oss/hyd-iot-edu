// 구간25 후반 재촬영(오류 문구 42초 결함 교체): take-25d 3:05.585(N06-v002 직전) 상태에서 안내 상자 끝까지.
// 시작 상태: 소개 아래 빈 줄 캐럿, 포인터 (203,280). 종료 상태: 안내 상자 두 번째 줄 입력 직후.
import {v10} from '../ui.mjs';
export default async ctx=>{
 const c=await v10(ctx);const PAGE=ctx.page;
 if(!(await c.serial(()=>c.raw.url())).includes(PAGE))throw Error('Not on the shooting page');
 if(await c.serial(()=>c.raw.evaluate(()=>!!document.querySelector('[role=note]'))))throw Error('Callout already exists; restore first');
 const start={x:203,y:280};await c.installPointer(start);await c.serial(()=>c.raw.mouse.move(start.x,start.y,{steps:1}));c.setPos(start);await c.sleep(600);
 await c.begin();
 await c.say('N06-v002',()=>c.type('/'));
 await c.say('live-callout-search',()=>c.type('콜아웃'));
 await c.say('N06-v003',()=>c.click('menu','콜아웃'));
 await c.waitFor(()=>!!document.querySelector('[role=note]'));
 await c.say('N06-v005');await c.say('live-bold-on',()=>c.key('Control+b'));
 await c.say('N06-v006',()=>c.type('하나의 주제에서, 나만의 지식으로'));
 await c.say('live-bold-off',()=>c.key('Control+b'));
 await c.say('N06-v007',()=>c.key('Shift+Enter'));await c.say('N06-v008');
 await c.say('N06-v009',()=>c.type('카드 하나에 주제 하나. 카드 안에는 글과 자료를 자유롭게 담고, 내용이 늘어나면 하위 페이지로 나누세요.'));
 return 'seg-25t done';
};
