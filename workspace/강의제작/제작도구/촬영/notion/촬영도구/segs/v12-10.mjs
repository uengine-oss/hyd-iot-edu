// v12-10 · 10단계 토글 — 시작: 「첫 페이지 꾸미기」, 글머리 목록 아래 보통 줄 캐럿. (토글은 만들 때부터 펼쳐져 있어 삼각형은 짚기만 한다) 끝: 접힌 토글 아래 보통 줄 캐럿.
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:10}];
export const ops=c=>{const {at,T,K}=kit(c);const Q='제목과 굵은 글씨는 어떻게 다를까?';return{10:{
 토글단축:at(0,async()=>{c.at(0.85);await c.md('> ');}),
 토글질문:T(Q),
 삼각형짚기:()=>c.toggleTriangle(),
 안쪽누르기:()=>c.toggleInside(),
 설명1:T('제목은 문서의 구획을 만들고 목차에도 표시됩니다.'),
 설명2:T(' 굵은 글씨는 문장 안에서 중요한 말을 강조할 때 씁니다.'),
 접기:()=>c.click('aria','닫기'),
 펴기:()=>c.click('aria','열기'),
 다시접기:()=>c.click('aria','닫기'),
 질문끝엔터:async()=>{await c.endText(Q);await c.key('Enter');},
 빈토글지우기:K('Backspace'),
}};};
