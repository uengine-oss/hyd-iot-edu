// v12-03 · 3단계 홈과 소개 한 줄 — 시작: 「내 학습 노트」 페이지(2단계 끝). 본문 캐럿이 제목 아래 빈 줄에 없으면 제목 끝에서 Enter로 내려간다.
// 끝: 소개 아래 빈 줄 하나 띄운 줄에 캐럿, 화살표는 소개 블록 손잡이.
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:3}];
export const ops=c=>{const {K}=kit(c);const INTRO='관심 있는 주제를 모으고, 배운 내용을 나만의 방식으로 쌓아 갑니다.';return{3:{
 소개입력:{pointFrac:0,fn:async()=>{c.at(0.1);await c.toBody();c.at('point');await c.type(INTRO);}},
 엔터두번:K('Enter','Enter'),
 손잡이짚기:async()=>{await c.handleOf(await c.blockOf(INTRO));},
}};};
