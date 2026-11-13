// v12-09 · 9단계 제목과 글머리 목록 — 시작: 「첫 페이지 꾸미기」 페이지(제목 · 이모지만). 끝: 「오늘 써 본 방법」 아래 글머리 셋, 목록을 끝낸 보통 줄에 캐럿.
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:9}];
export const ops=c=>{const {at,T,ET,K}=kit(c);return{9:{
 소개입력:{pointFrac:0,fn:async()=>{c.at(0.1);await c.titleEnter();c.at('point');await c.type('한 페이지 안에서도 글의 모양을 바꾸어 읽기 쉽게 정리할 수 있습니다.');}},
 엔터두번:K('Enter','Enter'),
 제목2:at(0,async()=>{c.at(0.05);await c.md('## ');await c.type('오늘 써 본 방법');}),
 제목2엔터:K('Enter'),
 글머리단축:at(0,async()=>{c.at(0.85);await c.md('- ');}),
 항목1:T('제목으로 내용의 구획 나누기'),
 항목2:ET('같은 성격의 내용은 목록으로 정리하기'),
 항목3:ET('긴 설명은 토글 안에 접어 두기'),
 목록끝:K('Enter','Enter'),
}};};
