// v12-25 · 25단계 템플릿으로 새 주제 만들기 — 시작: 홈, 보기 「주제 카드」(템플릿 창 닫힘). 끝: 홈, 카드 셋(셋째 「나만의 독서 기록」 📚, 하위 페이지 「다음에 읽을 책」 📖).
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:25}];
export const ops=c=>{const {at}=kit(c);const INTRO='이 주제에서 알고 싶은 것, 기억하고 싶은 것을 한 줄로 적어 보세요.';return{25:{
 템플릿적용:at(0,async()=>{c.at(0.55);await c.click('aria','추가 옵션 더 보기');c.at(1);await c.click('text','새 주제');}),
 전체페이지:()=>c.click('css','[role=region] a[aria-label="전체 페이지로 열기"]'),
 소개짚기:()=>c.hoverText(INTRO),
 상자짚기:async()=>c.hoverAt(await c.mark({css:'[role=note]',has:'나의 주제를',first:true})),
 기록짚기:()=>c.hoverText('나의 기록'),
 토글짚기:()=>c.hoverText('나에게 맞게 바꾸려면'),
 이모지책:at(0.4,()=>c.emoji('나만의 독서 기록',{change:true,times:{open:0.45,type:0.8,pick:1}})),
 제목바꾸기:at(0,async()=>{c.at(0.25);await c.replaceTitle('나만의 독서 기록');}),
 소개바꾸기:at(0,async()=>{c.at(0.2);await c.selectText(INTRO);await c.type('읽으면서 남기고 싶은 생각과 자료를 모읍니다.');}),
 기록끝엔터:async()=>{await c.endText('나의 기록');await c.key('Enter');},
 페이지만들기:at(0,async()=>{c.at(0.05);await c.type('/페이지');c.at(1);await c.click('menu','페이지');await c.serial(()=>c.raw.waitForSelector('h1[contenteditable=true]',{timeout:10000}));}),
 하위제목이모지:at(0,async()=>{c.at(0.05);await c.titleType('다음에 읽을 책');c.at(0.6);await c.emoji('다음에 읽을 책');}),
 본문입력:{pointFrac:0,fn:async()=>{c.at(0.05);await c.titleEnter();c.at(0.2);await c.type('읽고 싶은 책과 그 이유를 짧게 남깁니다.');}},
 홈으로:()=>c.link(c.ctx.homeTitle,true),
 카드세장짚기:at(0,async()=>{c.at(0.2);await c.hoverAt(await c.card(0));c.at(1);await c.hoverAt(await c.card(2));}),
}};};
