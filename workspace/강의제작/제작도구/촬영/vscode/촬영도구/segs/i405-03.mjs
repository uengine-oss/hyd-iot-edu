// 통합 4회차 05편 구간 03: 결과 화면 공간(SPACE='통합02 결과화면 20261111', VP='{width:1843,height:1037,dsf:1.25}') — 검토 결과 · 기존 ID · 승인 후보 표.
// 검토 결과 칸: 파일 · 문서 · 판 · 승인 · 보류 · 제외 · 조건 근거. 승인 후보 칸: 검토 파일 · 후보 · 절 · 절차 · 종류 · 줄 · 인용.
import {labUi, atPhrase, resultView, heading, inView, tableCell, tableHead, scrollPageTo} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.i405.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에
const cand = (c, ctx, id, n) => c.serial(() => ctx.p.evaluate(({id, n}) => {
 const tr = [...document.querySelectorAll('tbody tr')].filter(r => r.cells.length === 7 && r.cells[1].textContent.trim() === id);
 if (tr.length !== 1) throw Error('후보 줄이 ' + tr.length + '개: ' + id);
 const b = tr[0].cells[n].getBoundingClientRect(); return {x: b.x + Math.min(30, b.width / 2), y: b.y + b.height / 2};
}, {id, n}));

export default async ctx => {
 const c = await labUi(ctx);
 const view = await resultView(c, ctx, LAB, '검토 결과와 기존 ID');
 // 첫 표(검토 결과)에서 파일 이름이 file인 줄의 n번째 칸 — 승인 후보 표도 7칸이고 첫 칸이 같은 파일 이름이라 표를 첫 표로 묶는다
 const rv = (file, n) => c.serial(() => ctx.p.evaluate(({file, n}) => {
  const tr = [...document.querySelectorAll('table')[0].tBodies[0].rows].filter(r => r.cells[0].textContent.trim() === file);
  if (tr.length !== 1) throw Error('검토 결과 줄이 ' + tr.length + '개: ' + file);
  const b = tr[0].cells[n].getBoundingClientRect(); return {x: b.x + Math.min(30, b.width / 2), y: b.y + b.height / 2};
 }, {file, n})).then(inView);
 await c.installPointer({x: 1300, y: 160});
 await ctx.begin();
 await ctx.say('i405-0301', async () => { const q = inView(await tableHead(c, ctx, '승인')); await c.move(q.x, q.y); }, {at: '첫 표는'});
 await ctx.say('i405-0302', async () => { const q = await rv('HM-8_1.1_review.json', 3); await c.move(q.x, q.y); }, {at: '84건이'});
 await ctx.say('i405-0303', async () => {
  const a = await rv('HM-8_1.0_review.json', 5); await c.move(a.x, a.y); await atPhrase(ctx, '개정 요청은');
  const b = await rv('HM-8_1.2_review.json', 5); await c.move(b.x, b.y);
 }, {at: '폐기된 판본과'});
 await ctx.say('i405-0304', async () => { const q = await rv('HM-8_1.1_review.json', 6); await c.move(q.x, q.y); }, {at: '끝의 조건 근거'});
 await ctx.say('i405-0305', async () => {
  const a = await rv('HM-9_1.0_review.json', 6); await c.move(a.x, a.y); await atPhrase(ctx, '원문과 다른');
  const b = await rv('SR-04_2024_review.json', 6); await c.move(b.x, b.y);
 }, {at: '원문이 없는 조건'});
 await ctx.say('i405-0306', async () => {
  await scrollPageTo(c, ctx, () => tableCell(c, ctx, 'Step', 1, 2));
  const t = inView(await heading(c, ctx, '기존 ID')); await c.move(t.x, t.y);
 }, {at: '기존 ID 표에는'});
 await ctx.say('i405-0307', async () => {
  const s = inView(await tableCell(c, ctx, 'Skill', 1, 2)); await c.move(s.x, s.y); await atPhrase(ctx, '조건표의 규칙인');
  const r = inView(await tableCell(c, ctx, 'Rule', 1, 2)); await c.move(r.x, r.y);
 }, {at: '조치 방법인 Skill'});
 await ctx.say('i405-0308', async () => {
  await scrollPageTo(c, ctx, () => cand(c, ctx, 'HI-01-M002', 6), view.h, 260);
  const t = inView(await heading(c, ctx, '승인 후보 찾아보기')); await c.move(t.x, t.y);
 }, {at: '그 아래 표가'});
 await ctx.say('i405-0309', async () => {
  const a = inView(await cand(c, ctx, 'HI-01-M002', 2)); await c.move(a.x, a.y); await atPhrase(ctx, '원문 인용이');
  const b = inView(await cand(c, ctx, 'HI-01-M002', 6)); await c.move(b.x, b.y);
 }, {at: '어느 절에서'});
 await ctx.say('i405-0310', async () => { await c.move(view.w - 260, 200); }, {at: '문서에는 같은'});
 return {segment: 'i405-03', view, next: 'i405-04: 웹 VS Code 공간에서 Codex와 기존 ID 찾기(가이드 2단계)', aiRequests: 0};
};
