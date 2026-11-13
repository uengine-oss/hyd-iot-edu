// v12-07 · 7단계 첫 주제 열기 — 시작: 홈, 갤러리 「주제 모음」(보기 「주제 카드」, 설정 닫힘). 끝: 「Notion 익히기」(✏️) 전체 페이지, 파란 콜아웃 설명 끝 캐럿.
// 새 콜아웃이 앞 상자 색(파란색)을 이어받는 것을 확인한다(대본이 그렇게 말한다 — 아니면 멈춘다).
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:7}];
export const ops=c=>{const {at,T,K}=kit(c);return{7:{
 새로만들기:()=>c.click('text','새로 만들기'),
 전체페이지:()=>c.click('css','[role=region] a[aria-label="전체 페이지로 열기"]'),
 제목입력:at(0,async()=>{c.at(0.1);await c.titleType('Notion 익히기');}),
 이모지연필:at(0,()=>c.emoji('Notion 익히기',{times:{open:0.1,type:0.4,pick:1}})),
 속성줄짚기:async()=>c.hoverAt(await c.propRow('생성일')),
 소개입력:{pointFrac:0,fn:async()=>{c.at(0.1);await c.toBody();c.at('point');await c.type('글을 쓰고, 페이지를 연결하며 나에게 맞는 노트를 만들어 봅니다.');}},
 엔터두번:K('Enter','Enter'),
 콜아웃슬래시:T('/콜아웃'),
 콜아웃고르기:at(0,async()=>{c.at(0.3);await c.calloutPick(BLUE,'상자가 이번엔 처음부터 파란색으로 나왔죠');}),
 굵은줄:{pointFrac:0,fn:async()=>{c.at(0.05);await c.key('Control+b');c.at('point');await c.type('짧게 적고, 필요한 만큼 연결하기');}},
 설명줄:{pointFrac:0,fn:async()=>{c.at(0.05);await c.key('Control+b');await c.key('Enter');c.at(0.25);await c.type('한 페이지에서 시작해 내용이 쌓이면 하위 페이지로 이어 갑니다.');}},
}};};
