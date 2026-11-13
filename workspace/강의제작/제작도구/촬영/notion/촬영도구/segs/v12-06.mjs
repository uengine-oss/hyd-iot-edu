// v12-06 · 6단계 보기 이름 붙이기 — 시작: 홈, 갤러리 「주제 모음」(보기 설정 닫힘). 끝: 보기 이름 「주제 카드」, 설정 창 닫힘.
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:6}];
export const ops=c=>{const {at}=kit(c);return{6:{
 설정:()=>c.dbSettings(),
 보기이름입력:at(0,async()=>{c.at(0.45);await c.click('css','input[placeholder="보기 이름"]');await c.key('Control+a');await c.type('주제 카드');c.at(1);await c.key('Enter');}),
 보기이름짚기:()=>c.hoverAt('input[placeholder="보기 이름"]'),
 목록이름짚기:async()=>c.hoverAt(await c.mark({css:'[contenteditable=true]',text:'주제 모음',first:true})),
 닫기:()=>c.click('aria','닫기'),
}};};
