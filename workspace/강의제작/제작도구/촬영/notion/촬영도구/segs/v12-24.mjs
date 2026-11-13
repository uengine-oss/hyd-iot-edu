// v12-24 · 24단계 새 주제 템플릿 — 시작: 홈, 보기 「주제 카드」. 끝: 템플릿 「새 주제」(📄) 저장 · 창 닫힘, 홈.
// 템플릿은 가운데 창([role=region])에서 고친다. 새 콜아웃은 앞 색(파란색)을 이어받는다(대본 — 아니면 멈춘다).
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:24}];
export const ops=c=>{const {at,T,ET,K,H2,OUT}=kit(c);return{24:{
 화살표:()=>c.click('aria','추가 옵션 더 보기'),
 새템플릿:()=>c.click('menu','새 템플릿'),
 안내짚기:async()=>c.hoverAt(await c.mark({scope:'region',has:['템플릿','편집'],first:true})),
 제목입력:at(0,async()=>{c.at(0.15);await c.titleType('새 주제','region');}),
 이모지종이:at(0,()=>c.emoji('새 주제',{scope:'region',times:{open:0.5,type:0.75,pick:1}})),
 소개입력:{pointFrac:0,fn:async()=>{c.at(0.05);await c.toBody('region');c.at(0.15);await c.type('이 주제에서 알고 싶은 것, 기억하고 싶은 것을 한 줄로 적어 보세요.');}},
 엔터두번:K('Enter','Enter'),
 콜아웃만들기:at(0,async()=>{c.at(0.05);await c.callout(BLUE,'콜아웃 만드시면 방금 쓴 파란색으로 나와요');}),
 상자글:{pointFrac:0,fn:async()=>{c.at(0.02);await c.boxText('나의 주제를, 나의 방식으로','짧은 글부터 시작하세요. 아래 항목은 필요한 만큼 바꾸고 모두 채울 필요는 없습니다.');}},
 상자밖한줄:OUT(),
 제목2:H2('나의 기록'),
 글머리1:{pointFrac:0,fn:async()=>{c.at(0.05);await c.md('- ');await c.type('기억하고 싶은 내용');}},
 글머리2:ET('다시 보고 싶은 자료'),
 목록끝:K('Enter','Enter'),
 토글질문:at('point',async()=>{c.at('point');await c.md('> ');await c.type('나에게 맞게 바꾸려면');}),
 안쪽설명:{pointFrac:0,fn:async()=>{c.at(0.1);await c.toggleInside();await c.type('항목 이름과 배치는 자유롭게 바꾸세요. 내용이 길어지면 하위 페이지로 나누세요.');}},
 접기:()=>c.click('aria','닫기'),
 템플릿닫기:async()=>{
  const body=await c.serial(()=>c.raw.evaluate(()=>{const r=document.querySelector('[role=region]')||document;const h=[...r.querySelectorAll('[role=textbox]')].find(e=>e.textContent==='나의 기록');return{title:r.querySelector('h1')?.textContent,notes:[...r.querySelectorAll('[role=note]')].map(e=>({text:e.textContent,bg:getComputedStyle(e.firstElementChild).backgroundColor})),headingOutside:!!h&&!h.closest('[role=note]')};}));
  await c.fs.writeFile(c.out+'/template-body.json',JSON.stringify(body));if(!body.headingOutside)throw Error('Template heading nested or missing');
  await c.key('Escape');await c.key('Escape');},
}};};
