// v12-26 · 26단계 공유 · 게시 · 댓글 — 시작: 홈(카드 셋). 끝: 홈, 공유 창 · 댓글 칸 닫힘(아무것도 바꾸지 않는다).
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:26}];
export const ops=c=>{const {K}=kit(c);return{26:{
 공유:()=>c.role('button','공유'),
 공유짚기:async()=>c.hoverAt(await c.mark({css:'[role=tab]',text:'공유',first:true})),
 게시탭:()=>c.role('tab','게시'),
 닫기:K('Escape'),
 문장고르기:()=>c.selectText('관심 있는 주제를 모으고, 배운 내용을 나만의 방식으로 쌓아 갑니다.'),
 // 댓글 칸은 대화상자가 아니라 고른 문장 옆에 뜬다(리허설 r27 — 「댓글 추가」 칸, role=dialog 밖).
 댓글단축:async()=>{await c.key('Control+Shift+m');await c.serial(()=>c.raw.waitForFunction(()=>[...document.querySelectorAll('[role=textbox][aria-label="댓글 추가"]')].some(e=>e.checkVisibility()),undefined,{timeout:8000}));},
 댓글닫기:async()=>{await c.key('Escape');await c.serial(()=>c.raw.waitForFunction(()=>![...document.querySelectorAll('[role=textbox][aria-label="댓글 추가"]')].some(e=>e.checkVisibility()),undefined,{timeout:8000}));},
}};};
