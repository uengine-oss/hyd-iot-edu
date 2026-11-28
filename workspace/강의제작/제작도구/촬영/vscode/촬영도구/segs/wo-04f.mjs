// 06-2 구간 04f(둘째 페이지 — PAGE=1): F5 → 「구성 요소 자리 5곳에 실물 6대」 · HYD-02 펌프 자리와 실물 둘 → 자리 이름이 주 펌프 (A)인 까닭(이름 맞춤 그림의 주 펌프 · 오일 쿨러 줄과 까닭 글). Codex 부탁 없음.
// 시작: 둘째 페이지에 클래스와 식별자 화면(wo-04b 끝) — 앞 take wo-04e를 준다. 끝: 구성 요소 이름과 실물 화면(이름 맞춤 그림까지 굴린 채).
import {atPhrase} from './lab-common.mjs';
import {ui, PICK, guideIn, seamOut, resultStart, f5, verdict, node, gatherRow, pageTo, TITLE} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 1);
 await resultStart(c, ctx, TITLE.classes);
 const G = await guideIn(c, ctx, 'res', {ring: 'm2'});
 await c.installPointer(ctx.prev ? null : {x: 1400, y: 500});
 await ctx.begin();
 const nodeAt = id => c.serial(() => ctx.p.evaluate(id => { const e = document.querySelector('g.n[data-id="' + CSS.escape(id) + '"]'); if (!e) return {error: '그림에 노드 없음: ' + id}; const b = e.getBoundingClientRect(); return {x: b.x + b.width / 2, y: b.y + b.height / 2}; }, id)).then(r => { if (r.error) throw Error(ctx.cueId + ': ' + r.error + ' — PICK.seat02를 본다 (segs/wo-04f.mjs)'); return r; });
 await ctx.say('wo0416', async () => {
  await f5(c, ctx, 'names', G);
  await c.emph(verdict(), {shape: 'underline'});
  await atPhrase(ctx, '그림을 보면'); await pageTo(c, ctx, () => nodeAt(PICK.seat02 + '|KP-1902-551'));
  await c.emph(node(PICK.seat02), {shape: 'box'});
  await c.emph(node(PICK.seat02 + '|KP-2603-114'), {shape: 'box', keep: true, point: false}); await c.emph(node(PICK.seat02 + '|KP-1902-551'), {shape: 'box', keep: true, point: false});
 }, {at: '구성 요소 자리 다섯 곳에'});
 await ctx.say('wo0417', async () => {
  await c.emph({sel: 'g.n[data-id="' + PICK.seat02 + '"] text.t'}, {shape: 'underline'});
  await atPhrase(ctx, '아래 그림이 그 까닭입니다'); const r = await pageTo(c, ctx, () => gatherRow(c, ctx, '주 펌프 (A)')); await c.emph({rects: r.rects}, {shape: 'box'});
  await atPhrase(ctx, '오일 쿨러와 열교환기가'); const o = await pageTo(c, ctx, () => gatherRow(c, ctx, '오일 쿨러')); await c.emph({rects: o.rects}, {shape: 'box'});
  await atPhrase(ctx, '같은 태그의 센서가 붙어'); await c.emph({sel: '.gather .gm .chip small', has: '같은 태그의 센서(FS2 · TS1 · TS2)'}, {shape: 'underline'});
 }, {at: '자리 이름이'});
 const cut = await seamOut(c, ctx, G);
 return {segment: 'wo-04f', page: 1, cut, aiRequests: 0, next: 'wo-05a: 같은 물리량의 범위 · R10'};
};
