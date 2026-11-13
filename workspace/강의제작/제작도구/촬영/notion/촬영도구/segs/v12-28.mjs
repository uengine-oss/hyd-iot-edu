// v12-28 · 28단계 둘러보기와 마무리 — 시작: 내보낸 HTML 탭이 앞(노션 탭은 홈). 첫 조작에서 노션 탭으로 돌아온다. 끝: 홈(카드 셋).
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:28}];
export const ops=c=>{const {at}=kit(c);return{28:{
 // 말 없는 시간을 줄이려고 쪽 열기 · 긴 스크롤 · 내려받기를 말 도중에 시작한다(녹화 전 훑기 2026-11-13: 이 큐들은 누른 뒤 기다림이 2.5초를 넘을 후보).
 카드열기:at('point',async()=>{await c.front('notion');c.at(0.7);await c.click('text','Notion 익히기');c.at(0.85);await c.click('css','[role=region] a[aria-label="전체 페이지로 열기"]');}),
 두상자짚기:at(0,async()=>{c.at(0.15);await c.hoverAt(await c.pageLink('첫 페이지 꾸미기'));c.at(1);await c.hoverAt(await c.pageLink('페이지 연결하기'));}),
 첫페이지열기:()=>c.link('첫 페이지 꾸미기'),
 // 열고 나서 도움말 링크가 보이는 자리까지 들인다(말하지 않는 스크롤 — 다음 큐가 그 링크를 말한다).
 둘째페이지열기:at(0,async()=>{c.at(0.1);await c.link('Notion 익히기',true);c.at(0.8);await c.link('페이지 연결하기');await c.inView(await c.mark({css:'.notion-page-content a',text:'Notion 글쓰기 도움말'}));}),
 홈으로:()=>c.link(c.ctx.homeTitle,true),
}};};
