// v12-15 · 15단계 두 하위 페이지를 회색 상자로 묶기 — 시작: 「페이지 연결하기」(이유 한 줄 끝 캐럿). 끝: 「Notion 익히기」, 「나의 페이지」 아래 회색 상자 「01 ·」 · 「02 ·」(세로로), 두 하위 페이지 링크.
// 새 상자 색: 첫 상자는 앞 색(파란색)을 이어받고, 둘째는 방금 쓴 회색을 이어받는다(대본이 그렇게 말한다 — 아니면 멈춘다).
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:15}];
export const ops=c=>{const {at,T,K}=kit(c);return{15:{
 경로부모:()=>c.link('Notion 익히기',true),
 두줄짚기:at(0,async()=>{c.at(0.3);await c.hoverAt(await c.pageLink('첫 페이지 꾸미기'));c.at(1);await c.hoverAt(await c.pageLink('페이지 연결하기'));}),
 나의페이지끝엔터:at(0,async()=>{c.at(0.35);await c.endText('나의 페이지');await c.key('Enter');}),
 콜아웃만들기:async()=>{await c.callout(BLUE,'이번에도 파란색으로 나왔는데');},
 굵은줄:{pointFrac:0,fn:async()=>{c.at(0.03);await c.key('Control+b');c.at(0.1);await c.type('01 · 글 정리하기');}},
 굵게끄고엔터:K('Control+b','Enter'),
 설명1:T('제목·목록·토글로'),
 설명2:{pointFrac:0,fn:async()=>{c.at(0.05);await c.key('Shift+Enter');c.at('point');await c.type('읽기 편하게 정리합니다.');}},
 손잡이색이름:{pointFrac:0,fn:async()=>{c.at(0.1);await c.noteHandle();c.at('point');await c.type('회색 배경');}},
 색고르기:()=>c.click('menu','회색 배경'),
 상자밖:()=>c.exitBox(),
 콜아웃만들기2:()=>c.callout(GRAY,'이번엔 방금 쓴 회색으로 나오죠'),
 회색짚기:async()=>{await c.expectNote(GRAY,'이번엔 방금 쓴 회색으로 나오죠');await c.hoverAt(await c.mark({css:'[role=note]',last:true}));},
 둘째상자글:{pointFrac:0,fn:async()=>{c.at(0.02);await c.boxText('02 · 내용 연결하기','하위 페이지와 링크로');}},
 둘째설명2:{pointFrac:0,fn:async()=>{c.at(0.05);await c.key('Shift+Enter');await c.type('내용을 이어 갑니다.');}},
}};};
