// 실전 2회차 07편 구간 03: 결과 화면 공간(SPACE='통합02 결과화면 20261111', VP='{width:1843,height:1037,dsf:1.25}') — 제공 모델 개수 · 원자료 행 수.
import {labUi, atPhrase, resultView, heading, inView, tableCell} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.p207.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에

export default async ctx => {
 const c = await labUi(ctx);
 const view = await resultView(c, ctx, LAB, '원자료와 제공 모델');
 const at = (key, n) => tableCell(c, ctx, key, n, 2).then(inView);
 await c.installPointer({x: 1300, y: 160});
 await ctx.begin();
 await ctx.say('p207-0301', async () => {
  const h = inView(await heading(c, ctx, '제공된 설비')); await c.move(h.x, h.y); await atPhrase(ctx, 'Asset이 설비');
  const a = await at('Asset', 1); await c.move(a.x, a.y); await atPhrase(ctx, 'Part가 부품');
  const b = await at('Part', 1); await c.move(b.x, b.y);
 }, {at: '위 표에는'});
 await ctx.say('p207-0302', async () => {
  for (const [f, w] of [['approved_suppliers.csv', '승인 공급사 목록이'], ['supply_terms.csv', '견적 조건이'], ['receipts.csv', '입고 기록이']]) { await atPhrase(ctx, w); const q = await at(f, 1); await c.move(q.x, q.y); }
 }, {at: '승인 공급사 목록이'});
 await ctx.say('p207-0303', async () => { await c.move(view.w - 260, 200); }, {at: '앞으로는'});
 return {segment: 'p207-03', view, next: 'p207-04: 웹 VS Code 공간에서 Codex와 자료 파악(가이드 2단계)', aiRequests: 0};
};
