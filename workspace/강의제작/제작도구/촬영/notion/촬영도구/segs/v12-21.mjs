// v12-21 · 21단계 카드 앞면에 그림 보이기 — 시작: 「지식 자산화」 전체 페이지(속성 채움). 끝: 홈, 갤러리 「주제 카드」, 카드 미리보기 = 카드 이미지, 카드 크기 작게, 설정 닫힘.
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:21}];
export const ops=c=>{const {at}=kit(c);return{21:{
 홈으로:()=>c.link(c.ctx.homeTitle,true),
 설정:()=>c.dbSettings(),
 레이아웃:()=>c.click('menu','레이아웃'),
 미리보기값짚기:()=>c.hoverLabel('카드 미리보기'),
 미리보기누르기:()=>c.clickLabel('카드 미리보기'),
 카드이미지:at(0,async()=>{c.at(0.3);await c.click('menu','페이지 속성');c.at(1);await c.click('menu','카드 이미지');}),
 카드크기작게:at(0,async()=>{c.at(0.6);await c.clickLabel('카드 크기');c.at(1);await c.click('menu','작게');}),
 닫기:()=>c.click('aria','닫기'),
 작은카드짚기:at(0,async()=>{c.at(0.2);await c.hoverAt(await c.card(0));c.at(1);await c.hoverAt(await c.card(1));}),
}};};
