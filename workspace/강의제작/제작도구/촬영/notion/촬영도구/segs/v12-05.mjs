// v12-05 · 5단계 주제 모음 만들기 — 시작: 홈, 파란 콜아웃(색 메뉴 닫힘). 끝: 갤러리 보기 「주제 모음」(제목 입력 뒤), 빈 줄 둘 아래.
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:5}];
export const ops=c=>{const {at,K}=kit(c);return{5:{
 상자밖:()=>c.exitBox(),
 빈줄둘:K('Enter','Enter'),
 갤러리검색:at(0,async()=>{c.at(0.4);await c.type('/갤러리');}),
 갤러리보기:()=>c.click('menu','갤러리 보기'),
 // 갤러리 보기를 고르면 틀 고르는 창 없이 빈 갤러리가 바로 생긴다(리허설 r12) — 대본 「빈 목록이 하나 생겼어요」: 새 갤러리를 짚는다.
 빈목록짚기:async()=>{const has=await c.serial(()=>c.raw.evaluate(()=>[...document.querySelectorAll('div,span,a,button')].some(e=>e.textContent.trim()==='비어 있는 새 데이터 소스'&&e.checkVisibility({checkVisibilityCSS:true}))));
  // 오른쪽 「새 데이터베이스」 패널(비어 있는 새 데이터 소스 · CSV 가져오기 …)이 뜨는 때가 있다(k9). 빈 갤러리는 패널과 상관없이 이미 생겨 있어 대본(「빈 목록이
  // 하나 생겼어요」)과 맞으므로 멈추지 않는다 — 패널은 다음 조작(제목 칸 누르기)에서 닫힌다. 뜬 일은 기록에 남긴다.
  if(has)await c.fs.appendFile(c.out+'/panel.jsonl',JSON.stringify({cue:c.ctx.cue?.id,what:'새 데이터베이스 패널이 떠 있음'})+String.fromCharCode(10));// 방금 생긴 갤러리 = 제목 칸이 비어 있는(「새 데이터베이스」 자리 글) 갤러리. 편집 영역 안이라 data-* 표시가 지워지므로 Notion의 data-block-id로 가리킨다.
  const sel=await c.serial(()=>c.raw.evaluate(()=>{const g=[...document.querySelectorAll('.notion-gallery-view')].filter(g=>{const b=g.closest('[data-block-id]');return b&&[...b.querySelectorAll('[contenteditable=true][placeholder="새 데이터베이스"]')].some(e=>!e.textContent.trim());});if(g.length!==1)throw Error('New empty gallery: '+g.length);return '[data-block-id="'+g[0].closest('[data-block-id]').getAttribute('data-block-id')+'"] .notion-gallery-view';}));
  // 갤러리 요소는 화면 너비보다 넓다(k10: 왼쪽 -6px) — 화면 안에 보이는 부분의 가운데쯤(카드 자리)으로 옮긴다. 갤러리는 콜아웃 바로 밑이라 위아래로는 화면 안에 있다.
  const q=await c.serial(()=>c.raw.evaluate(s=>{const r=document.querySelector(s).getBoundingClientRect();const l=Math.max(0,r.left),rt=Math.min(innerWidth,r.right);return{x:Math.round(l+(rt-l)*0.3),y:Math.round(r.top+Math.min(r.height,140)/2)};},sel));await c.move(q.x,q.y);},
 새페이지자리짚기:async()=>c.hoverAt(await c.mark({scope:'.notion-gallery-view',has:'새 페이지',first:true})),
 제목자리짚기:()=>c.hoverAt('[contenteditable=true][placeholder="새 데이터베이스"]'),
 이름입력엔터:at(0,async()=>{c.at(0.15);await c.click('css','[contenteditable=true][placeholder="새 데이터베이스"]');await c.type('주제 모음');c.at(1);await c.key('Enter');}),
}};};
