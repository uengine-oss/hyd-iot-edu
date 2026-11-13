// v12-12 · 12단계 목차 — 시작: 「첫 페이지 꾸미기」 아래쪽(할 일 목록 끝). 끝: 목차에서 「다음에 해 볼 것」을 눌러 그 제목 자리로 내려간 화면.
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:12}];
export const ops=c=>{const {at,K}=kit(c);const toc=t=>c.mark({css:'.notion-table_of_contents-block a,.notion-table_of_contents-block [role=link]',text:t});return{12:{
 소개끝엔터:async()=>{await c.endText('한 페이지 안에서도 글의 모양을 바꾸어 읽기 쉽게 정리할 수 있습니다.');await c.key('Enter');},
 한줄띄움:K('Enter'),
 목차:at(0,async()=>{c.at(0.05);await c.type('/목차');c.at(1);await c.click('menu','목차');}),
 목차항목1짚기:async()=>c.hoverAt(await toc('오늘 써 본 방법')),
 목차항목2짚기:async()=>c.hoverAt(await toc('다음에 해 볼 것')),
 목차누르기:async()=>{await c.click('css',await toc('다음에 해 볼 것'));await c.sleep(600);},
}};};
