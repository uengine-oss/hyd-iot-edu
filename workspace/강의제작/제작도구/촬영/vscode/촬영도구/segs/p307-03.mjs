// 실전 3회차 07편 구간 03: 결과 화면 공간(SPACE='통합02 결과화면 20261111', VP='{width:1843,height:1037,dsf:1.25}') — 사건 조치 후보 · 핀 세척 관계 · 문서 묶음 표.
// 문서 묶음 표는 첫 화면 아래라 휠로 내린 뒤 짚는다. 칸 차례: 문서 · 판 · 상태 · 파일 · 글자 방식 · 줄 수 · 절 머리 수 · 첫 줄 또는 읽지 못한 까닭.
import {labUi, atPhrase, resultView, heading, inView, tableCell, scrollPageTo} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.p307.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에
// 문서 묶음 표에서 문서 · 판이 같은 줄의 n번째 칸
const doc = (c, ctx, name, rev, n) => c.serial(() => ctx.p.evaluate(({name, rev, n}) => {
 const tr = [...document.querySelectorAll('tbody tr')].filter(r => r.cells.length === 8 && r.cells[0].textContent.trim() === name && (rev === null || r.cells[1].textContent.trim() === rev));
 if (tr.length !== 1) throw Error('문서 줄이 ' + tr.length + '개: ' + name + ' ' + rev);
 const b = tr[0].cells[n].getBoundingClientRect(); return {x: b.x + Math.min(30, b.width / 2), y: b.y + b.height / 2};
}, {name, rev, n}));
// h3 제목(글이 text로 시작) 안에서 글 tail이 시작하는 자리 — 「제목 끝에 적힌 대로」처럼 긴 제목의 끝 괄호를 짚을 때(i404-03과 같은 함수)
const headTail = (c, ctx, text, tail) => c.serial(() => ctx.p.evaluate(({text, tail}) => {
 const e = [...document.querySelectorAll('h3')].find(x => x.textContent.startsWith(text)); if (!e) throw Error('제목 없음: ' + text);
 const w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
 for (let n = w.nextNode(); n; n = w.nextNode()) { const i = n.textContent.indexOf(tail); if (i >= 0) { const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + 1); const b = r.getBoundingClientRect(); return {x: b.x + 4, y: b.y + b.height / 2}; } }
 throw Error('제목 안에 글 없음: ' + tail);
}, {text, tail}));

export default async ctx => {
 const c = await labUi(ctx);
 const view = await resultView(c, ctx, LAB, '사건과 문서 묶음');
 await c.installPointer({x: 1300, y: 160});
 await ctx.begin();
 await ctx.say('p307-0301', async () => { const q = inView(await heading(c, ctx, '사건 경보')); await c.move(q.x, q.y); }, {at: '맨 위 표는'});
 await ctx.say('p307-0302', async () => { const q = inView(await tableCell(c, ctx, 'SOP-COOL-14', 1, 3)); await c.move(q.x, q.y); }, {at: '판정 칸이'});
 await ctx.say('p307-0303');   // 말만(화살표는 판정 칸에 둔다)
 await ctx.say('p307-0304', async () => {
  const a = inView(await tableCell(c, ctx, 'REMEDIED_BY', 1, 4)); await c.move(a.x, a.y); await atPhrase(ctx, '아래 줄은');
  const b = inView(await tableCell(c, ctx, 'ADDRESSES', 2, 4)); await c.move(b.x, b.y); await atPhrase(ctx, '출처 칸에는');
  const d = inView(await tableCell(c, ctx, 'ADDRESSES', 3, 4)); await c.move(d.x, d.y);
 }, {at: '위 줄은'});
 await ctx.say('p307-0305', async () => {
  const a = await scrollPageTo(c, ctx, () => doc(c, ctx, 'HM-8', '1.2', 2), view.h, 420); await c.move(a.x, a.y - 84);
  for (const [rev, at] of [['1.0', '폐기,'], ['1.1', '현행,'], ['1.2', '개정 요청으로']]) { await atPhrase(ctx, at); const q = inView(await doc(c, ctx, 'HM-8', rev, 2)); await c.move(q.x, q.y); }
 }, {at: '그 아래는'});
 await ctx.say('p307-0306', async () => { const q = inView(await doc(c, ctx, 'SR-04', null, 4)); await c.move(q.x, q.y); }, {at: '글자 방식 칸은'});
 await ctx.say('p307-0307', async () => { const q = await scrollPageTo(c, ctx, () => doc(c, ctx, 'OEM-HPP45B-MM', null, 7), view.h); await c.move(q.x, q.y); }, {at: '아래쪽 제조사'});
 await ctx.say('p307-0308', async () => { const q = inView(await headTail(c, ctx, '문서 묶음', '(지문')); await c.move(q.x, q.y); }, {at: '제목 끝에'});
 await ctx.say('p307-0309', async () => { await c.move(view.w - 260, 200); }, {at: '이렇게 문서마다'});
 return {segment: 'p307-03', view, next: 'p307-04: 웹 VS Code 공간에서 Codex와 핀 세척 원문 찾기(가이드 2단계)', aiRequests: 0};
};
