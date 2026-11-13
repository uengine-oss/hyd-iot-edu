// v12-17 · 17단계 지식 자산화 주제 — 시작: 「Notion 익히기」(두 칸 배치). 끝: 「지식 자산화」(💡) 전체 페이지, 파란 콜아웃(색 메뉴 「배경 색상」에서 고름).
// 새 상자는 방금 쓴 회색을 이어받는다(대본 — 아니면 멈춘다). 「최근 사용」에는 마지막에 쓴 색(회색) 하나만 나오므로 파란색은 「배경 색상」 목록에서 고른다(k14 s17-10).
import {kit,BLUE,GRAY,wheelSmooth} from '../lib/ui-v12.mjs';
export const parts=[{step:17}];
export const ops=c=>{const {at}=kit(c);return{17:{
 홈으로:()=>c.link(c.ctx.homeTitle,true),
 새로만들기:()=>c.click('text','새로 만들기'),
 전체페이지:()=>c.click('css','[role=region] a[aria-label="전체 페이지로 열기"]'),
 제목입력:at(0,async()=>{c.at(0.1);await c.titleType('지식 자산화');}),
 이모지전구:at(0,()=>c.emoji('지식 자산화',{times:{open:0.05,type:0.4,pick:1}})),
 소개입력:{pointFrac:0,fn:async()=>{c.at(0.05);await c.toBody();c.at(0.2);await c.type('배운 것을 한 번 읽고 끝내지 않고, 필요할 때 다시 꺼내 쓰는 방법을 생각합니다.');}},
 콜아웃만들기:at(0,async()=>{c.at(0.2);await c.key('Enter');await c.key('Enter');c.at(0.6);await c.callout(GRAY,'이번엔 방금 쓴 회색으로 나와요');}),
 상자글:{pointFrac:0,fn:async()=>{c.at(0.02);await c.boxText('모아 두는 데서, 다시 꺼내 쓰는 데까지','내 말로 정리하면 무엇을 알고 무엇이 아직 모호한지 드러난다. 출처도 함께 남겨 두면 나중에 다시 확인하기 좋다.');}},
 최근파랑:at(0,async()=>{c.at(0.1);await c.noteHandle();c.at(0.3);await c.click('menu','색');
  // 「파란색 배경」은 색 하위 메뉴 아래쪽에 잘려 있다. 사람처럼 하위 메뉴 안에 커서를 두고 휠로 「배경 색상」을 내린 뒤 고른다
  // (k14 · k15: 잘린 좌표로 바로 가다 메뉴 밖으로 나가 하위 메뉴가 닫혔다).
  c.at(0.5);const sub=await c.serial(()=>c.raw.evaluate(()=>{const h=[...document.querySelectorAll('div,span')].find(e=>e.textContent.trim()==='배경 색상'&&e.checkVisibility());if(!h)return null;
   let p=h.parentElement;while(p&&!(p.scrollHeight>p.clientHeight+2&&/(auto|scroll)/.test(getComputedStyle(p).overflowY)))p=p.parentElement;const r=(p||h).getBoundingClientRect();return{x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height*0.55)};}));
  if(!sub)throw Error('색 하위 메뉴(「배경 색상」)가 없음');const at=await c.pointerAt();await c.glide(sub.x,at.y);await c.glide(sub.x,sub.y);  // 「색」에서 수평으로 하위 메뉴에 들어간 뒤 아래로(대각선으로 가면 하위 메뉴가 닫힐 수 있다)
  for(let i=0;i<4;i++){const seen=await c.serial(()=>c.raw.evaluate(()=>{const e=[...document.querySelectorAll('[role=menuitem],[role=option]')].find(e=>e.textContent.trim()==='파란색 배경');if(!e)return false;let p=e.parentElement;while(p&&!(p.scrollHeight>p.clientHeight+2&&/(auto|scroll)/.test(getComputedStyle(p).overflowY)))p=p.parentElement;const r=e.getBoundingClientRect(),box=(p||document.documentElement).getBoundingClientRect();return r.top>=box.top+2&&r.bottom<=Math.min(box.bottom,innerHeight)-4;}));if(seen)break;await wheelSmooth(c,0,220);await c.sleep(250);}
  c.at(0.75);await c.hover('menu','파란색 배경');c.at(1);await c.click('menu','파란색 배경');}),
}};};
