// 통합 3회차 06편 구간 03: 결과 화면 공간(SPACE='통합02 결과화면 20261111', VP='{width:1843,height:1037,dsf:1.25}') — 경보마다 판정 요청 직전 원천 기록 표.
// 칸 차례: 경보 · 설비 · 판정 요청(UTC) · PLC 마지막 수신 · 카운터 마지막 기록 · 예측 행.
import {labUi, atPhrase, resultView, heading, inView, tableCell, tableHead} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.i306.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에
const A1 = 'ALT-hyd03-0280-beaf', A2 = 'ALT-hyd02-0153-06b1';

export default async ctx => {
 const c = await labUi(ctx);
 const view = await resultView(c, ctx, LAB, '판정 요청 직전 원천 기록');
 const at = (key, n) => tableCell(c, ctx, key, n, 6).then(inView);
 await c.installPointer({x: 1300, y: 160});
 await ctx.begin();
 await ctx.say('i306-0301', async () => {
  const b = await at(A1, 0); await c.move(b.x, b.y);
  await atPhrase(ctx, '제목 끝에'); const a = await heading(c, ctx, '경보마다 판정 요청 직전'); await c.move(a.x, a.y);
 }, {at: '표 한 줄이'});
 await ctx.say('i306-0302', async () => { const q = await at(A1, 3); await c.move(q.x, q.y); }, {at: 'PLC 마지막 수신'});
 await ctx.say('i306-0303', async () => {
  const a = await at(A1, 4); await c.move(a.x, a.y);
 }, {at: '카운터 마지막 기록'});
 await ctx.say('i306-0306', async () => { const q = await at(A2, 4); await c.move(q.x, q.y); }, {at: '둘째 경보는'});
 // 끊긴 경보(52 · 60번째 줄)는 처음 30줄 밖이라 짚지 않고 칸 머리만 짚는다 — 찾는 일은 다음 구간에서 Codex에게 묻는다
 await ctx.say('i306-0304', async () => { const q = inView(await tableHead(c, ctx, '카운터 마지막 기록')); await c.move(q.x, q.y); }, {at: '그런데'});
 await ctx.say('i306-0307', async () => { const q = await at(A1, 5); await c.move(q.x, q.y); }, {at: '예측 행 칸에는'});
 await ctx.say('i306-0305', async () => { await c.move(view.w - 260, 200); }, {at: '원천 네 곳과'});
 return {segment: 'i306-03', view, next: 'i306-04: 웹 VS Code 공간에서 Codex와 원천 기록 파악(가이드 2단계)', aiRequests: 0};
};
