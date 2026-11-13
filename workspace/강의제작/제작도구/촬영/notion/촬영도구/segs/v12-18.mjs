// v12-18 · 18단계 메모와 질문 — 시작: 「지식 자산화」, 파란 콜아웃(색 메뉴 닫힘). 끝: 메모 글머리 셋과 접힌 토글.
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:18}];
export const ops=c=>{const {at,T,ET,K,H2,OUT}=kit(c);return{18:{
 상자밖한줄:OUT(),
 제목2:H2('내 말로 남기는 짧은 메모'),
 글머리단축:at(0,async()=>{c.at(0.5);await c.md('- ');}),
 항목1:T('기록의 목적은 다시 찾고 활용하는 것이다.'),
 항목2:ET('원문과 내가 이해한 내용을 구분해 남긴다.'),
 항목3:ET('나중에 다시 보고 싶은 질문도 함께 남긴다.'),
 목록끝:K('Enter','Enter'),
 토글단축:at(0,async()=>{c.at(0.85);await c.md('> ');}),
 질문:T('어떻게 다시 찾아볼까?'),
 안쪽설명:{pointFrac:0,fn:async()=>{c.at(0.1);await c.toggleInside();await c.type('주제 이름을 분명하게 정하고 필요한 출처를 함께 남긴다.');}},
 접기:()=>c.click('aria','닫기'),
}};};
