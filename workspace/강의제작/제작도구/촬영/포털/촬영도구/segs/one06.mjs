// 1회차 실습 06 「전체과정관찰」(두 과정 공통, 2026-11 새 포털 판) 구간 모듈 — take.sh에 이 이름(one06.mjs)과 큐 ../../통합_01_06_전체과정관찰_큐.json을 준다.
// 큐는 확정 대본에서 ../../통합_01_06_전체과정관찰_큐만들기.py가 만들고, 조작은 map.mjs가 한다(대상 · 시점 · 굴리기 · 리허설 검사는 그 파일 머리말).
// 이 모듈이 정하는 것은 쉬는 화살표 자리 하나다: 대본 v0601 「커서는 위 막대 「홈」 오른쪽 빈자리」.
// 되돌릴 수 없는 조작(제공 문서 올리기 · AI 추출 · 적재 · 쿨러 열화 주입 · 승인)이 있으므로 리허설 뒤에는 촬영준비 「길」대로 시작 상태를 다시 만든다.
import {seg as mapSeg} from './map.mjs';

export async function seg(ctx, n) {
 ctx.rest = {css: '#pageLocation', anchor: 'after', dx: 56};
 return mapSeg(ctx, n);
}
