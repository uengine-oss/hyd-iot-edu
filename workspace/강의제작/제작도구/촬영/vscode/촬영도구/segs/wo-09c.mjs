// 06-2 구간 09c(첫 페이지): Codex가 물어 온 설치일 속성 이름 → properties.csv의 속성 이름들(영어 소문자) → R18(「installed로 할게」)을 보내고 답이 끝날 때까지.
// 시작: wo-09b 끝(R17 답 — Codex의 물음이 선 화면, 앞 take를 준다). 끝: R18 답이 선 화면(expected.csv 질문 4 줄) → 녹화 뒤 사본 SEG=09c.
// Codex가 묻지 않고 이름을 스스로 지어 적었으면 이 구간과 큐 wo0918을 뺀다(대본 wo0918 조작 칸 — PICK.askedName = false, PICK.installed = 그 이름).
import {atPhrase} from './lab-common.mjs';
import {ui, RESUME, QE, PICK, guideIn, seamOut, keepEnd, open, mark, dataRows, visibleLines, cx, cxMark, paste, send, answer, askOf} from './wo-common.mjs';

export default async ctx => {
 if (!PICK.askedName) throw Error('PICK.askedName = false — Codex가 속성 이름을 묻지 않았으므로 이 구간(wo0918)은 찍지 않는다. wo-09d로 간다');
 const c = await ui(ctx, 0);
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm5'});
 if (RESUME == null) await cx(c, ctx, 'r17Ask');
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 let since = RESUME;
 if (since == null) await ctx.say('wo0918', async () => {
  await cxMark(c, ctx, 'r17Ask', 'band');
  await atPhrase(ctx, '다른 속성들이 영어 소문자로');
  const d = await dataRows('app/features/properties.csv'); await open(c, ctx, 'app/features/properties.csv'); const [, last] = await visibleLines(c, ctx);
  for (let n = d.first; n <= Math.min(d.last, last); n++) await mark(c, ctx, n, {cell: 1, keep: n > d.first, point: n === d.first});
  await atPhrase(ctx, '같은 꼴로'); await paste(c, ctx, askOf('wo0918'));
  since = await send(c, ctx, 'installed라고 하겠습니다');
 }, {at: 'Codex가 적기 전에'});
 const r = await answer(c, ctx, since);
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '09c');
 return {segment: 'wo-09c', page: 0, cut, ask: 'R18', aiRequests: since == null ? 0 : 1, answer: r.message, codexMs: r.ms, used: r.used, next: 'wo-09d: 질문 4 줄 · 설비 대장 · python run.py query'};
};
