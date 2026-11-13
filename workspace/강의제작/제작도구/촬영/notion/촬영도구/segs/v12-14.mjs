// v12-14 · 14단계 도움말 링크 — 시작: 「페이지 연결하기」, 안내 상자 글 끝 캐럿. 준비에서 가이드(config v12.guide)를 뒤 탭에 열어 둔다.
// 가이드 탭 → 「05 번호 목록과 도움말 링크」 → 주소 칸 복사 → 노션 탭 → 글자 끌어 고르기 → Ctrl+K → Ctrl+V(복사한 주소인지 확인) → Enter.
// 끝: 링크 글자와 이유 한 줄, 노션 탭이 앞.
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:14}];
export async function prepare(c){await c.ensureGuide();}
export const ops=c=>{const {at,T,K,H2,OUT}=kit(c);const LINK='Notion 글쓰기 도움말';return{14:{
 상자밖한줄:OUT(),
 제목2:H2('필요할 때 찾아보기'),
 도움말글:T(LINK),
 가이드복사:at('point',()=>c.guideCopy('part05','n19-input1',{navAt:0.75,copyAt:1})),
 노션복귀:()=>c.front('notion'),
 글자고르기:()=>c.selectText(LINK),
 링크단축:at(0,async()=>{c.at('point');await c.key('Control+k');await c.serial(()=>c.raw.waitForFunction(()=>document.activeElement?.matches('input'),undefined,{timeout:4000})).catch(()=>{throw Error('Ctrl+K link box did not open');});}),
 붙여넣기엔터:at(0,async()=>{c.at(0.35);await c.paste();c.at(1);await c.key('Enter');}),
 링크짚기:async()=>c.hoverAt(await c.mark({css:'.notion-page-content a',text:LINK})),
 선택풀고엔터:K('ArrowRight','Enter'),
 이유글:T('글과 블록을 다루는 방법이 필요할 때 공식 도움말에서 다시 확인합니다.'),
}};};
