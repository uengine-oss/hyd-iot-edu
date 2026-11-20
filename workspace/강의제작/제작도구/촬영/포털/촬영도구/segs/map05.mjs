// 통합반 2회차 실습 05 「포털 지식 지도 탐색」(2026-11 새 포털 판, 다시 찍는 판) 구간 모듈 — take.sh에 이 이름(map05.mjs)과 큐 ../../통합_02_05_지식지도탐색_큐.json을 준다.
// 큐는 대본에서 ../../통합_02_05_지식지도탐색_큐만들기.py가 만들고, 조작과 강조는 map.mjs가 한다(대상 · 시점 · 강조 · 리허설 검사는 그 파일 머리말).
// 이 모듈이 정하는 것은 쉬는 화살표 자리 하나다: 포털 홈에서 위 막대 「홈」 오른쪽 빈자리.
// 구간 1이 포털 홈을 새로 열고 「서비스 N/N」의 앞뒤 숫자가 같은지 잰다(map.mjs). 보기만 하는 편이라 되돌릴 조작은 없고, 설비 고르기가 HYD-02로 바뀐 채 끝난다(다음 구간 1이 홈을 새로 열면 HYD-01로 돌아온다).
import {seg as mapSeg} from './map.mjs';

export async function seg(ctx, n) {
 ctx.rest = {css: '#pageLocation', anchor: 'after', dx: 56};
 return mapSeg(ctx, n);
}
