// v12-11 · 11단계 구분선과 할 일 목록 — 시작: 「첫 페이지 꾸미기」, 토글 아래 보통 줄 캐럿. 끝: 할 일 둘 아래 보통 줄 캐럿.
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:11}];
export const ops=c=>{const {at,T,ET,K,H2}=kit(c);return{11:{
 구분선:at(0,async()=>{c.at('point');await c.md('---');}),
 제목2:H2('다음에 해 볼 것'),
 할일단축:at(0,async()=>{c.at(0.93);await c.md('[] ');}),
 // 지금 할 일 줄의 네모(체크 상자)를 짚는다: 캐럿 블록의 왼쪽 끝.
 네모짚기:async()=>{const q=await c.serial(()=>c.raw.evaluate(()=>{const n=getSelection()?.anchorNode,e=n?.nodeType===1?n:n?.parentElement,b=e?.closest('.notion-to_do-block');if(!b)throw Error('Caret is not in a to-do block');const r=b.getBoundingClientRect();return{x:r.x+12,y:r.y+Math.min(r.height,30)/2};}));await c.move(q.x,q.y);},
 할일1:T('내 관심 주제로 카드 하나 더 만들기'),
 할일2:ET('내용에 어울리는 하위 페이지 이름 붙이기'),
 목록끝:K('Enter','Enter'),
}};};
