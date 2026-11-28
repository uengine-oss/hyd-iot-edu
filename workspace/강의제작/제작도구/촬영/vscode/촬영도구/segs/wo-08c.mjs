// 06-2 구간 08c(둘째 페이지 — PAGE=1): F5 → 「기대 답과 같음 N/N」 · 「모든 줄이 …」 → 펌프 실물 줄 · RF-10 줄 · 없는 품번 줄 → 다를 때 할 일(칸 머리 셋 · 글상자). Codex 부탁 없음.
// 시작: 둘째 페이지에 넣기 전 검증 화면(wo-07b 끝) — 앞 take wo-08b를 준다. 끝: 질문별 대조 화면.
// 같음이 아닌 줄이 나오면 대본 wo0814 조작 칸대로 그 줄을 Codex에 보이는 장면을 새 큐로 정한 뒤 찍는다 — 여기서는 멈춘다.
import {atPhrase} from './lab-common.mjs';
import {ui, PICK, guideIn, seamOut, resultStart, f5, verdict, verdictSub, cmpCell, cmpHead, pageTo, note, speechEnd, TITLE} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 1);
 await resultStart(c, ctx, TITLE.check);
 const G = await guideIn(c, ctx, 'res', {ring: 'm5'});
 await c.installPointer(ctx.prev ? null : {x: 1400, y: 500});
 await ctx.begin();
 await ctx.say('wo0814', async () => {
  await f5(c, ctx, 'query', G);
  const st = await c.serial(() => ctx.p.evaluate(() => document.querySelector('.verdict')?.className ?? ''));
  if (!st.includes('v-ok')) throw Error('wo0814: 질문별 대조가 모두 같음이 아님(' + st + ') — 대본 wo0814 조작 칸대로 그 줄을 Codex에 보이는 장면을 새 큐로 정한다');
  await c.emph(verdict(), {shape: 'underline'});
  await atPhrase(ctx, '모든 줄이'); await c.emph(verdictSub(), {shape: 'underline'});
 }, {at: '맨 위를 보세요'});
 await ctx.say('wo0815', async () => {
  const p = await pageTo(c, ctx, () => cmpCell(c, ctx, ['1', 'HYD-02', PICK.pumpItem], 3), 130, 900); await c.emph({box: p.box}, {shape: 'band'});
  await atPhrase(ctx, '줄여 쓴 품번으로'); const r = await pageTo(c, ctx, () => cmpCell(c, ctx, ['3', 'RF-10', 'P-RTN-FLT'], 3), 130, 900); await c.emph({box: r.box}, {shape: 'band'});
  await atPhrase(ctx, '없는 품번은'); const x = await pageTo(c, ctx, () => cmpCell(c, ctx, ['3', 'P-PMP-SEAL-X'], 3), 130, 900); await c.emph({box: x.box}, {shape: 'band'});
 }, {at: 'HYD-02의 펌프 줄에는'});
 await ctx.say('wo0816', async () => {
  const h = await pageTo(c, ctx, () => cmpHead(c, ctx, '질문 · 입력 · 항목'), 130, 700); await c.emph({box: h.box}, {shape: 'underline'});
  await atPhrase(ctx, '기대 답은 무엇이었는지'); await c.emph({box: (await cmpHead(c, ctx, '답 — 기대')).box}, {shape: 'underline'});
  await atPhrase(ctx, '실제로는 무엇이 나왔는지'); await c.emph({box: (await cmpHead(c, ctx, '답 — 실제')).box}, {shape: 'underline'});
  await atPhrase(ctx, '원인부터 묻습니다'); await note(c, 'diff');
  await speechEnd(ctx); await c.note(null);
 }, {at: '무엇을 물었는지'});
 const cut = await seamOut(c, ctx, G);
 return {segment: 'wo-08c', page: 1, cut, aiRequests: 0, next: 'wo-09a: 새 질문 후보 · R16'};
};
