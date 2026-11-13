// v12-20 · 20단계 칸 채우기와 카드 그림 — 시작: 홈, 갤러리 「주제 카드」(설정 닫힘). 준비에서 가이드 탭이 없으면 뒤 탭에 연다.
// 그림 주소는 가이드 「11 카드 그림과 크기 맞추기」의 복사 단추(n33 · n34)로 복사하고, 카드 이미지 → 링크 탭 → Ctrl+V(복사한 주소인지 확인) → 링크.
// 끝: 「지식 자산화」 전체 페이지, 분야 · 이해도 · 카드 이미지가 채워짐, 파일 창 닫힘, 노션 탭이 앞.
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:20}];
export async function prepare(c){await c.ensureGuide();}
export const ops=c=>{const {at}=kit(c);const esc2=async()=>{await c.key('Escape');await c.sleep(300);await c.key('Escape');};return{20:{
 // 말 없는 시간을 줄이려고 쪽 열기 · 긴 스크롤 · 내려받기를 말 도중에 시작한다(녹화 전 훑기 2026-11-13: 이 큐들은 누른 뒤 기다림이 2.5초를 넘을 후보).
 카드열기:at(0,async()=>{c.at(0.45);await c.click('text','Notion 익히기');c.at(0.8);await c.click('css','[role=region] a[aria-label="전체 페이지로 열기"]');}),
 분야짚기:async()=>c.hoverAt(await c.propRow('분야')),
 이해도짚기:async()=>c.hoverAt(await c.propRow('이해도')),
 카드이미지짚기:async()=>c.hoverAt(await c.propRow('카드 이미지')),
 분야칸:()=>c.slot('분야'),
 도구:()=>c.role('option','도구'),
 대충앎:at(0,async()=>{c.at(0.1);await c.slot('이해도');c.at(1);await c.role('option','대충 앎');}),
 // 가이드 쪽 긴 스크롤(10,383px · 6.5초)은 「가이드에 그림 주소를 마련해 뒀습니다」를 말할 때부터 시작한다.
 가이드복사1:at(0,()=>c.guideCopy('part11','n33-input1',{navAt:0.3,copyAt:1})),
 이미지칸:async()=>{await c.front('notion');await c.imagePopup();},
 링크탭:at(0,async()=>{c.at(0.6);await c.role('tab','링크');}),
 붙여넣기:async()=>{await c.popupInput();await c.paste();},
 링크버튼:()=>c.role('button','링크'),
 창닫기:esc2,
 가이드복사2:at('point',()=>c.guideCopy(null,'n34-input1',{copyAt:1})),
 둘째카드열기:at(0,async()=>{await c.front('notion');c.at(0.15);await c.link(c.ctx.homeTitle,true);c.at(0.45);await c.click('text','지식 자산화');c.at(0.8);await c.click('css','[role=region] a[aria-label="전체 페이지로 열기"]');}),
 학습방법:at(0,async()=>{c.at(0.1);await c.slot('분야');c.at(1);await c.role('option','학습 방법');}),
 이해도고르기:at(0,async()=>{c.at(0.1);await c.slot('이해도');c.at(1);await c.role('option','대충 앎');}),
 링크탭2:at(0,async()=>{c.at(0.1);await c.imagePopup();c.at(1);await c.role('tab','링크');}),
 붙여넣고링크:at(0,async()=>{c.at(0.1);await c.popupInput();await c.paste();c.at(1);await c.role('button','링크');}),
 붙음짚기:at(0,async()=>{c.at(0.02);await esc2();c.at(0.5);await c.hoverAt(await c.propValue('카드 이미지'));}),
}};};
