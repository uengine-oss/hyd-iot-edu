// v12-19 · 19단계 속성 만들기 — 시작: 「지식 자산화」 전체 페이지(18단계 끝). 끝: 홈, 갤러리 「주제 카드」, 속성 분야 · 이해도(선택, 옵션 셋씩) · 카드 이미지(파일과 미디어), 설정 창 닫힘.
// 속성은 갤러리 보기 설정의 「속성 편집」 목록에서 만든다(이 판은 표 보기를 22단계에서 만든다).
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:19}];
export const ops=c=>{const {at}=kit(c);const item=t=>c.mark({css:'[role=menuitem],[role=option],[role=button]',has:t,scope:'dialog',first:true});
 const name=async t=>{await c.click('css','input[placeholder="속성 이름"]');await c.type(t);};
 const listOpen=()=>c.serial(()=>c.raw.evaluate(()=>{const d=[...document.querySelectorAll('[role=dialog]')].filter(e=>e.checkVisibility()).at(-1);return !!d&&[...d.querySelectorAll('[role=menuitem]')].some(e=>e.textContent.trim()==='새 속성');}));
 const back=async()=>{let n=0;for(;n<2&&!(await listOpen());n++){await c.click('aria','뒤로');await c.sleep(300);}
  if(!(await listOpen()))throw Error('Property list not shown after '+n+' 뒤로 clicks');await c.fs.appendFile(c.out+'/back-clicks.jsonl',JSON.stringify({cue:c.ctx.cue?.id,clicks:n})+String.fromCharCode(10));};
 return{19:{
 홈으로:()=>c.link(c.ctx.homeTitle,true),
 설정:()=>c.dbSettings(),
 속성편집:()=>c.propEdit(),
 이름짚기:async()=>c.hoverAt(await item('이름')),
 생성일짚기:async()=>c.hoverAt(await item('생성일')),
 태그짚기:async()=>c.hoverAt(await item('태그')),
 새속성:()=>c.click('menu','새 속성'),
 분야이름:at('point',async()=>{c.at('point');await name('분야');}),
 선택유형:at(0,async()=>{c.at(0.15);await c.click('menu','선택');}),
 옵션추가:()=>c.click('text','옵션 추가'),
 옵션도구:at(0,async()=>{c.at(0.05);await c.option('도구');}),
 옵션학습방법:at(0,async()=>{c.at(0.05);await c.option('학습 방법');}),
 옵션AI실습:at(0,async()=>{c.at(0.05);await c.option('AI 실습');}),
 // 「닫기」는 설정 창을 통째로 닫으므로(리허설 r14) 위쪽 「뒤로」로 속성 목록에 돌아간다(대본 「위쪽 뒤로를 누르세요」). 「뒤로」 한 번은 「주제 모음의 새 속성」
 // (유형 고르기)으로 돌아가고 목록은 한 번 더 눌러야 나온다(리허설 r33) — 목록이 보일 때까지 두 번까지 누르고, 누른 횟수를 back-clicks.jsonl에 남긴다(대본 말과 견줄 곳).
 뒤로:()=>back(),
 분야짚기:async()=>{const open=await c.serial(()=>c.raw.evaluate(()=>[...document.querySelectorAll('[role=dialog] [role=menuitem],[role=dialog] [role=option]')].some(e=>e.textContent.includes('분야')&&e.checkVisibility({checkVisibilityCSS:true}))));
  if(open)await c.hoverAt(await item('분야'));else await c.scriptGap('창을 닫으면 설정 창이 통째로 닫혀 「속성 목록」이 화면에 없음');},
 새속성2:at('point',async()=>{c.at('point');await c.click('menu','새 속성');}),
 이해도이름유형:at(0,async()=>{c.at(0.05);await name('이해도');c.at(0.6);await c.click('menu','선택');}),
 옵션설명못함:at(0,async()=>{c.at(0.1);await c.option('설명 못함');}),
 옵션대충앎:at(0,async()=>{c.at(0.05);await c.option('대충 앎');}),
 옵션설명가능뒤로:at(0,async()=>{c.at(0.05);await c.option('설명 가능');c.at(1);await back();}),
 새속성3:at('point',async()=>{c.at('point');await c.click('menu','새 속성');}),
 이미지이름유형닫기:at(0,async()=>{c.at(0.05);await name('카드 이미지');c.at(0.75);await c.click('menu','파일과 미디어');c.at(1);await c.click('aria','닫기');}),
}};};
