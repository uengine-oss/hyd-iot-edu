// 실전 3회차 08편 구간 03: 결과 화면 공간(SPACE='통합02 결과화면 20261111', VP='{width:1843,height:1037,dsf:1.25}') — 검토 결과 · 랩 DB 적재 뒤 개수.
// 검토 결과 칸: 파일 · 문서 · 판 · 승인 · 보류 · 제외 · 조건 근거. 마지막 표는 랩 DB 적재 뒤 개수(항목 · 개수).
import {labUi, atPhrase, resultView, heading, inView, scrollPageTo} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.p308.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에

export default async ctx => {
 const c = await labUi(ctx);
 const view = await resultView(c, ctx, LAB, '랩 DB 준비와 검토 결과');
 // 첫 표(검토 결과)에서 파일 이름이 file인 줄의 n번째 칸 — 승인 후보 표도 7칸이고 첫 칸이 같은 파일 이름이라 표를 첫 표로 묶는다
 const rv = (file, n) => c.serial(() => ctx.p.evaluate(({file, n}) => {
  const tr = [...document.querySelectorAll('table')[0].tBodies[0].rows].filter(r => r.cells[0].textContent.trim() === file);
  if (tr.length !== 1) throw Error('검토 결과 줄이 ' + tr.length + '개: ' + file);
  const b = tr[0].cells[n].getBoundingClientRect(); return {x: b.x + Math.min(30, b.width / 2), y: b.y + b.height / 2};
 }, {file, n})).then(inView);
 await c.installPointer({x: 1300, y: 160});
 await ctx.begin();
 await ctx.say('p308-0301', async () => {
  const a = await rv('HM-8_1.1_review.json', 3); await c.move(a.x, a.y); await atPhrase(ctx, '폐기된 옛 판');
  const b = await rv('HM-8_1.0_review.json', 5); await c.move(b.x, b.y); await atPhrase(ctx, '개정 요청은');
  const d = await rv('HM-8_1.2_review.json', 5); await c.move(d.x, d.y);
 }, {at: '첫 표는'});
 await ctx.say('p308-0302', async () => {
  for (const [f, at] of [['HM-9_1.0_review.json', '원문이 없는 조건'], ['SR-04_2024_review.json', '원문과 다른 조건']]) { await atPhrase(ctx, at); const q = await rv(f, 6); await c.move(q.x, q.y); }
 }, {at: '끝의 조건 근거'});
 await ctx.say('p308-0303', async () => { const q = await scrollPageTo(c, ctx, () => heading(c, ctx, '기존 ID'), view.h, 300); await c.move(q.x, q.y); }, {at: '그 아래 표는'});
 await ctx.say('p308-0304', async () => { const q = await scrollPageTo(c, ctx, () => heading(c, ctx, '승인 후보 찾아보기'), view.h, 300); await c.move(q.x, q.y); }, {at: '그 아래 긴 표는'});
 await ctx.say('p308-0305', async () => {
  // 마지막 표(랩 DB 적재 뒤 개수)의 첫 칸이 name인 줄
  const last = name => c.serial(() => ctx.p.evaluate(name => { const t = [...document.querySelectorAll('table')].pop(); const r = [...t.tBodies[0].rows].find(x => x.cells[0].textContent.trim() === name); if (!r) throw Error('마지막 표에 없음: ' + name); const b = r.cells[1].getBoundingClientRect(); return {x: b.x + 30, y: b.y + b.height / 2}; }, name));
  await scrollPageTo(c, ctx, () => last('Supplier'), view.h, 70);
  const a = inView(await last('노드')); await c.move(a.x, a.y); await atPhrase(ctx, '관계 449개로');
  const b = inView(await last('관계')); await c.move(b.x, b.y);
 }, {at: '맨 아래 표는'});
 await ctx.say('p308-0306', async () => { await c.move(view.w - 260, 200); }, {at: '이 개수는'});
 return {segment: 'p308-03', view, next: 'p308-04: 웹 VS Code 공간에서 적재 수 기록', aiRequests: 0};
};
