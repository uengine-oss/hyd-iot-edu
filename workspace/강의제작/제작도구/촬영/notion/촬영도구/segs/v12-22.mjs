// v12-22 · 22단계 표 보기 추가 — 시작: 홈, 갤러리 「주제 카드」(작은 카드, 설정 닫힘). 끝: 홈, 보기 「전체 주제」(표)가 앞, 보기 이름 탭 둘.
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:22}];
export const ops=c=>{const {at}=kit(c);return{22:{
 보기추가짚기:at(0.75,async()=>{c.at(0.8);await c.hoverAt(await c.mark({css:'[contenteditable=true]',text:'주제 모음',first:true}));c.at(1);await c.hover('aria','보기 추가');}),
 표고르기:at(0,async()=>{c.at(0.1);await c.click('aria','보기 추가');c.at(1);await c.click('menu','표');}),
 이름입력:at(0,async()=>{c.at(0.3);await c.click('css','input[placeholder="보기 이름"]');await c.key('Control+a');await c.type('전체 주제');}),
 완료:()=>c.click('text','완료'),
 닫기:()=>c.click('aria','닫기'),
 주제카드탭:()=>c.click('text','주제 카드'),
 전체주제탭:()=>c.click('text','전체 주제'),
 // 표의 「Notion 익히기」 줄(분야 · 이해도가 한 줄에 보임)을 짚는다.
 줄짚기:async()=>c.hoverAt(await c.mark({scope:'.notion-table-view',text:'Notion 익히기',first:true})),
}};};
