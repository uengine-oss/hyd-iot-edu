// v12-23 · 23단계 표 다듬기와 검색 — 시작: 홈, 보기 「전체 주제」(표). 끝: 홈, 보기 「주제 카드」, 표 「전체 주제」는 이름 · 분야 · 이해도만 보임, 검색 닫힘.
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:23}];
export const ops=c=>{const {at}=kit(c);const SEARCH='input[placeholder="검색어를 입력하세요…"]';
 const table=()=>c.serial(()=>c.raw.evaluate(()=>document.querySelector('.notion-table-view')?.innerText||''));
 return{23:{
 설정:()=>c.dbSettings(),
 속성표시:()=>c.click('menu','속성 표시 여부'),
 생성일태그숨김:at(0,async()=>{c.at(0.75);await c.hideProp('생성일');c.at(1);await c.hideProp('태그');}),
 카드이미지숨김:()=>c.hideProp('카드 이미지'),
 닫기:()=>c.click('aria','닫기'),
 주제카드탭:()=>c.click('text','주제 카드'),
 그림짚기:async()=>c.hoverAt(await c.card(0)),
 전체주제복귀:()=>c.click('text','전체 주제'),
 검색지식:at(0,async()=>{c.at(0.6);await c.click('aria','검색');await c.serial(()=>c.raw.waitForSelector(SEARCH,{state:'visible',timeout:6000}));c.at(1);await c.click('css',SEARCH);await c.type('지식');
  await c.serial(()=>c.raw.waitForFunction(()=>{const t=document.querySelector('.notion-table-view')?.innerText;return t?.includes('지식 자산화')&&!t.includes('Notion 익히기');},undefined,{timeout:6000})).catch(async()=>{throw Error('Search did not filter the table: '+(await table()).slice(0,200));});}),
 검색지우기:async()=>{await c.click('css',SEARCH);await c.key('Control+a');await c.key('Backspace');await c.serial(()=>c.raw.waitForFunction(()=>document.querySelector('.notion-table-view')?.innerText.includes('Notion 익히기'),undefined,{timeout:6000}));},
 검색닫고카드탭:at(0,async()=>{c.at(0.15);await c.key('Escape');c.at(1);await c.click('text','주제 카드');}),
}};};
