// v12-13 · 13단계 두 번째 하위 페이지 — 시작: 「첫 페이지 꾸미기」(목차로 내려간 화면). 끝: 「페이지 연결하기」(🔗), 번호 목록 넷 아래 안내 상자 글 끝 캐럿.
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:13}];
export const ops=c=>{const {at,T,ET,K,H2}=kit(c);return{13:{
 경로부모:()=>c.link('Notion 익히기',true),
 첫페이지줄짚기:async()=>c.hoverAt(await c.pageLink('첫 페이지 꾸미기')),
 나의페이지끝엔터:async()=>{await c.endText('나의 페이지');await c.key('Enter');},
 페이지만들기:at(0,async()=>{c.at(0.05);await c.type('/페이지');c.at(1);await c.click('menu','페이지');await c.serial(()=>c.raw.waitForSelector('h1[contenteditable=true]',{timeout:10000}));}),
 제목입력:at(0,async()=>{c.at(0.1);await c.titleType('페이지 연결하기');}),
 이모지사슬:at(0,()=>c.emoji('페이지 연결하기',{times:{open:0.05,type:0.4,pick:1}})),
 소개입력:{pointFrac:0,fn:async()=>{c.at(0.05);await c.titleEnter();c.at('point');await c.type('내용이 길어지면 같은 주제 안에서 페이지를 나눠 봅니다.');}},
 엔터두번:K('Enter','Enter'),
 제목2:H2('하위 페이지 만들기'),
 번호단축:at(0,async()=>{c.at(0.9);await c.md('1. ');}),
 번호1:T('주제 카드를 엽니다.'),
 번호2:ET('빈 줄에서 슬래시를 입력하고 페이지를 고릅니다.'),
 번호3:ET('페이지 이름을 붙이고 내용을 적습니다.'),
 번호4:ET('위쪽 경로를 눌러 부모 주제로 돌아옵니다.'),
 목록끝:K('Enter','Enter'),
 한줄띄움:K('Enter'),
 콜아웃만들기:at(0,async()=>{c.at(0.8);await c.callout(BLUE,'(색을 말하지 않음 — 앞에 쓴 파란색을 이어받아야 한다)');}),
 상자글:T('페이지 이름은 내용에 맞게 자유롭게 붙이세요.'),
}};};
