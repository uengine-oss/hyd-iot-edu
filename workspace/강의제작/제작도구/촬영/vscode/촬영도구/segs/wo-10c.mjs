// 06-2 구간 10c(첫 페이지): features에 남은 것 → 다섯 칸 그림으로 되짚기(키워 띄우고 차례로 덧긋기 · 펌프와 온도 두 줄) → 결정 표 두 줄 → 모델 파일 둘 · 세 걸음 그림(①② 체크, ③에 동그라미). 끝 프레임은 세 걸음 그림이 떠 있는 화면. Codex 부탁 없음.
// 시작: 첫 페이지는 wo-10a 끝 화면(사이에 둘째 페이지 wo-10b) — 앞 take wo-10a. 끝: 같은 화면 — 걷는 모습은 합성 때 cut에서 자른다(마지막 구간). 큐 wo1082는 대본 wo1001을 나눈 넷째 조각(판정 문서 「막힌 곳 ①」).
import {atPhrase} from './lab-common.mjs';
import {ui, QE, guideIn, guideHide, guideShow, seamOut, keepEnd, open, mark, unfold, label, lineHas, FLOW, STEPS2} from './wo-common.mjs';

const D = 'app/features/decisions.csv';
export default async ctx => {
 const c = await ui(ctx, 0);
 const d1 = await lineHas(ctx, D, '구성 요소 자리와 그 실물'), d2 = await lineHas(ctx, D, '같은 물리량의 범위');
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm5'});
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 await ctx.say('wo1082', async () => { await c.emph(label('features'), {shape: 'box'}); }, {at: 'features의 표와 규칙에'});
 const F = c.pen(FLOW);
 await ctx.say('wo1002', async () => {
  await guideHide(G); await F.show('f1', 'f2', 'f3', 'f4', 'f5', 'a12', 'a23', 'a34', 'a45', 'back', 'backT', 'fileT');   // 다섯 칸 그림을 가운데로 키운다
  await atPhrase(ctx, '보전팀의 질문 세 개를'); await F.trace('f1');
  await atPhrase(ctx, '질문의 낱말을'); await F.trace('f2', {keep: true}); await F.trace('f3', {keep: true});
  await atPhrase(ctx, '갈아 끼운 펌프는'); await F.draw('pump');
  await atPhrase(ctx, '온도는 재는 곳마다'); await F.draw('temp');
  await atPhrase(ctx, '넣기 전에 검증하고'); await F.trace('f4', {keep: true});
  await atPhrase(ctx, '기대 답과 맞춰 봤어요'); await F.trace('f5', {keep: true});
  await atPhrase(ctx, '새 질문이 왔을 때는'); await F.trace('back', {keep: true});
 }, {at: '그림으로 되짚어 보죠'});
 await ctx.say('wo1003', async () => {
  await F.hide(); await guideShow(G, false);
  await open(c, ctx, D); await mark(c, ctx, Math.min(d1, d2), {to: Math.max(d1, d2)});
  await atPhrase(ctx, '왜 그렇게 골랐고'); for (const [i, k] of [1, 2, 3].entries()) await mark(c, ctx, 3, {cell: k, shape: 'underline', keep: i > 0, point: i === 0});   // 고른_것 · 근거 · 바뀌는_답 칸(칸 머리 — 줄의 근거 · 바뀌는_답은 편집기 오른쪽 밖으로 길다)
 }, {at: '결정 표의 두 줄을'});
 const S = c.pen(STEPS2);
 await ctx.say('wo1004', async () => {
  await unfold(c, ctx, 'output', 1); await c.emph(label('schema.json'), {shape: 'box'}); await c.emph(label('graph.json'), {shape: 'box', keep: true, point: false});
  await atPhrase(ctx, '다음은 이 지식을 그래프 DB에'); await guideHide(G); await S.show('s1', 'a12', 's2', 'a23', 's3');
  await atPhrase(ctx, '세 걸음 가운데 마지막 걸음'); await S.draw('ok1', 'ok2'); await S.ring('s3');
 }, {at: '보전팀의 질문에 답하는 모델이'});
 const cut = await seamOut(c, ctx, G, {figs: [S]});
 await keepEnd(c, ctx, '10c');
 return {segment: 'wo-10c', page: 0, cut, aiRequests: 0, next: '끝 — 끝 프레임은 세 걸음 그림(cut까지 쓴다)'};
};
