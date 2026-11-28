// 06-2 구간 07b(둘째 페이지 — PAGE=1): F5 → 「구조 검사 통과」 · 노드 · 관계 수(말하지 않는다) → 맞춰 본 것 카드 셋 → 걸렸을 때 할 일(글상자) → 검사한 그래프 그림 · 길잡이 ⑤. Codex 부탁 없음.
// 시작: 둘째 페이지에 부품과 모델 화면(wo-06b 끝) — 앞 take wo-07a를 준다. 끝: 넣기 전 검증 화면(그래프 그림까지 굴린 채).
// 결론이 「통과」가 아니면(실제로 걸린 곳) 대본 wo0712 조작 칸대로 그 장면을 새 큐로 정한 뒤 찍는다 — 여기서는 멈춘다.
import {atPhrase} from './lab-common.mjs';
import {ui, NOTE, guideIn, guideRing, seamOut, resultStart, f5, verdict, verdictSub, card, pageTo, note, speechEnd, TITLE} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 1);
 await resultStart(c, ctx, TITLE.parts);
 const G = await guideIn(c, ctx, 'res', {ring: 'm4'});
 await c.installPointer(ctx.prev ? null : {x: 1400, y: 500});
 await ctx.begin();
 await ctx.say('wo0712', async () => {
  await f5(c, ctx, 'check', G);
  const st = await c.serial(() => ctx.p.evaluate(() => [document.querySelector('.verdict')?.className ?? '', document.querySelector('.verdict span')?.textContent ?? '']));
  if (!st[0].includes('v-ok')) throw Error('wo0712: 넣기 전 검증이 통과가 아님(' + st[0] + ') — 대본 wo0712 조작 칸대로 걸린 장면을 새 큐로 정한다');
  const counts = /노드 \d+개, 관계 \d+개/.exec(st[1])?.[0]; if (!counts) throw Error('wo0712: 결론 아래 글에 「노드 N개, 관계 M개」가 없음: ' + st[1]);
  await c.emph(verdict(), {shape: 'underline'}); await c.emph(verdictSub(), {shape: 'underline', phrase: counts, keep: true, point: false});
  for (const [p, t] of [['식별자가 겹치는 것은', '식별자가 겹치는 인스턴스가 없다'], ['필수 속성이 빠지지', '필수 속성이 빠지지 않았다'], ['적어도 하나라고 정한 관계가', '「적어도 하나」로 정한 관계가 빠진 인스턴스가 없다']]) {
   await atPhrase(ctx, p); const b = await pageTo(c, ctx, () => card(c, ctx, t, 'head'), 130, 900); await c.emph({box: b.box}, {shape: 'underline'});
  }
 }, {at: '구조 검사를 통과했다고'});
 await ctx.say('wo0713', async () => {
  await note(c, 'fix', NOTE.fix.lines.slice(0, 1));
  await atPhrase(ctx, '원자료가 맞다면'); await note(c, 'fix', NOTE.fix.lines.slice(0, 2));
  await atPhrase(ctx, 'parts와 check를'); await note(c, 'fix');
  await speechEnd(ctx); await c.note(null);
 }, {at: '왜 걸렸는지를'});
 await ctx.say('wo0714', async () => {
  await pageTo(c, ctx, () => c.serial(() => ctx.p.evaluate(() => { const h = [...document.querySelectorAll('h3')].find(x => x.textContent.startsWith('검사한 그래프')); const b = h.getBoundingClientRect(); return {x: b.x + 40, y: b.y + b.height / 2}; })), 130, 420);
  await atPhrase(ctx, '실제로 물어봐야'); await guideRing(G, 'm5');
 }, {at: '다만 이 검사를'});
 const cut = await seamOut(c, ctx, G);
 return {segment: 'wo-07b', page: 1, cut, aiRequests: 0, next: 'wo-08a: 정답표 보강 · R15'};
};
