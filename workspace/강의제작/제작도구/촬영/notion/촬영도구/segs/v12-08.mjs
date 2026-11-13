// v12-08 · 8단계 구역 제목과 첫 하위 페이지 — 시작: 「Notion 익히기」 전체 페이지, 파란 콜아웃 설명 끝 캐럿. 끝: 하위 페이지 「첫 페이지 꾸미기」(🎨), 화살표는 위 경로의 「Notion 익히기」.
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:8}];
export const ops=c=>{const {at,T,K}=kit(c);return{8:{
 상자밖:()=>c.exitBox(),
 한줄띄움:K('Enter'),
 제목2단축:at(0,async()=>{c.at(0.35);await c.md('## ');}),
 제목2입력:at(0,async()=>{c.at(0.03);await c.type('나의 페이지');c.at(1);await c.key('Enter');}),
 페이지슬래시:T('/페이지'),
 페이지고르기:async()=>{await c.click('menu','페이지');await c.serial(()=>c.raw.waitForSelector('h1[contenteditable=true]',{timeout:10000}));},
 하위제목:at(0,async()=>{c.at(0.3);await c.titleType('첫 페이지 꾸미기');}),
 이모지팔레트:at(0,()=>c.emoji('첫 페이지 꾸미기',{times:{open:0.05,type:0.5,pick:1}})),
 경로짚기:async()=>c.hoverAt(await c.crumb('첫 페이지 꾸미기')),
 경로부모짚기:async()=>c.hoverAt(await c.crumb('Notion 익히기')),
}};};
