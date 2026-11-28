// 06-2 구간 02d(둘째 페이지 — PAGE=1): 결과 화면 F5 → 「기대 답 N줄을 정했습니다」(숫자는 말하지 않는다) → 질문 1 · 질문 3 카드. Codex 부탁 없음.
// 시작: 둘째 페이지에 06-1 끝의 결과 화면(F5 앞의 옛 화면)이 열려 있다 — 앞 take wo-02c를 준다. 끝: 기대 답 화면.
// 결론이 「근거로 적은 줄이 맞지 않는 줄」(볼 곳 있음)이면 대본 wo0209 조작 칸대로 근거를 고치는 장면을 새 큐로 정한 뒤 찍는다 — 여기서는 멈춘다.
import {atPhrase} from './lab-common.mjs';
import {ui, guideIn, seamOut, resultStart, f5, verdict, card, pageTo} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 1);
 await resultStart(c, ctx, null);   // 06-1이 남긴 화면(원자료 화면일 것) — 제목은 보지 않는다
 const G = await guideIn(c, ctx, 'res', {ring: 'm1'});
 await c.installPointer(ctx.prev ? null : {x: 1400, y: 500});
 await ctx.begin();
 await ctx.say('wo0209', async () => {
  await f5(c, ctx, 'expected', G);
  const st = await c.serial(() => ctx.p.evaluate(() => document.querySelector('.verdict')?.className ?? ''));
  if (!st.includes('v-info')) throw Error('wo0209: 기대 답 화면의 결론이 「정했습니다」가 아님(' + st + ') — 대본 wo0209 조작 칸의 「근거를 고치는 장면」을 새 큐로 정한다');
  await atPhrase(ctx, '맨 위에 몇 곳인지'); await c.emph(verdict(), {shape: 'underline'});
  await atPhrase(ctx, '아래에는 질문마다'); const k = await pageTo(c, ctx, () => card(c, ctx, '질문 1', 'card'));
  await c.emph({box: k.box}, {shape: 'box'}); await c.emph({box: (await card(c, ctx, '질문 3', 'card')).box}, {shape: 'box', keep: true, point: false});
 }, {at: '이 명령은'});
 const cut = await seamOut(c, ctx, G);
 return {segment: 'wo-02d', page: 1, cut, aiRequests: 0, next: 'wo-03a: 스키마 표 세 장 · R3'};
};
