// v12-04 · 4단계 안내 상자(콜아웃) — 시작: 홈, 소개 아래 빈 줄(한 줄 띄움)에 캐럿. 끝: 파란색 배경 콜아웃(제목 줄 굵게 · 설명 줄), 색 메뉴 닫힘.
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:4}];
export const ops=c=>{const {at,T,K}=kit(c);return{4:{
 슬래시:at(0,async()=>{c.at(0.3);await c.type('/');}),
 콜아웃검색:at(0,async()=>{c.at(0.25);await c.type('콜아웃');}),
 콜아웃고르기:at(0,async()=>{c.at(0.15);await c.calloutPick(GRAY,'처음이시면 기본 회색으로 나올 거예요');}),
 굵게켜기:K('Control+b'),
 굵은줄:T('하나의 주제에서, 나만의 지식으로'),
 굵게끄기:K('Control+b'),
 상자엔터:at(0,async()=>{c.at(0.15);await c.key('Enter');}),
 설명줄:T('카드 하나에 주제 하나. 카드 안에는 글과 자료를 자유롭게 담고, 내용이 늘어나면 하위 페이지로 나누세요.'),
 손잡이누르기:()=>c.noteHandle(),
 // 손잡이 메뉴가 열린 채로 색 이름을 치면 그 항목만 남는다(길뚫기).
 색이름치기:at(0,async()=>{c.at(0.4);await c.type('파란색 배경');await c.serial(()=>c.raw.waitForFunction(()=>[...document.querySelectorAll('[role=menuitem],[role=option]')].some(e=>e.textContent.trim()==='파란색 배경'),undefined,{timeout:4000}));}),
 색고르기:()=>c.click('menu','파란색 배경'),
}};};
