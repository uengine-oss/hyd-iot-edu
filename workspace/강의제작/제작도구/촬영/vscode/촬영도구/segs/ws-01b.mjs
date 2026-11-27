// 5분 예시 구간 01b(첫 페이지 — 웹 VS Code): components.csv를 열어 13 · 14행(옛 펌프 · 새 펌프)을 짚고, 펜 그림으로 「자리와 실물」을 세운 뒤 길 둘을 적는다.
// 시작: ws-reset.mjs 뒤 화면(편집기 닫힘, 폴더 접힘, 빈 Codex). 끝: components.csv가 열린 화면.
// 펜 그림은 구간 안에서 걷어야 하므로(ctrl.mjs — 구간 끝에 떠 있으면 멈춘다) 끝 큐 ws0104의 말이 끝날 때 걷는다.
import {labUi, atPhrase, em, row, rowSeen} from './lab-common.mjs';
import {SEAT} from './ws-common.mjs';

const L13 = 'HYD-02,동력,유압 펌프,PMP-SEAL', L14 = 'HYD-02,동력,유압 펌프,P-PMP-SEAL';
const speechEnd = async ctx => { const q = ctx.__cue; if (!ctx.rehearsal) { const w = q.t0 + q.dur - Date.now(); if (w > 0) await ctx.sleep(w); } };

export default async ctx => {
 const c = await labUi(ctx);
 if ((await c.serial(() => ctx.p.evaluate(() => document.querySelectorAll('.tabs-container .tab').length))) !== 0) throw Error('편집기 탭이 열려 있음 — ws-reset.mjs로 맞추고 시작');
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 await ctx.say('ws0102', async () => {
  const d = await c.explorerRow('data', 1); await c.clickAt(d.x, d.y);
  await rowSeen(ctx, 'components.csv', 2);
  const f = await row(c, 'components.csv', 2); await c.clickAt(f.x, f.y); await c.key('Enter');
  await ctx.waitFor(() => document.querySelector('.tabs-container .tab.active .label-name')?.textContent === 'components.csv');
  await c.emph(em.line(L13), {shape: 'band'}); await c.emph(em.line(L14), {shape: 'band', keep: true});
  await atPhrase(ctx, '일련번호가 서로'); await c.emph(em.line(L13), {shape: 'underline', phrase: 'KP-1902-551'}); await c.emph(em.line(L14), {shape: 'underline', phrase: 'KP-2603-114', keep: true});
  await atPhrase(ctx, '비고에도'); await c.emph(em.line(L13), {shape: 'underline', phrase: '철거(구 일련번호)'}); await c.emph(em.line(L14), {shape: 'underline', phrase: '교체 설치', keep: true});
 }, {at: '둘 다'});
 const fig = c.pen(SEAT);
 await ctx.say('ws0103', async () => {
  await fig.draw('seat');
  await atPhrase(ctx, '그 자리에 달린 펌프'); await fig.draw('an', 'now');
  await atPhrase(ctx, '이사를 가도'); await fig.draw('ao', 'old');
  await atPhrase(ctx, '센서가 그 초인종'); await fig.draw('as1', 's1', 'as2', 's2');
 }, {at: '펌프가 놓이는 자리'});
 await ctx.say('ws0104', async () => {
  await fig.draw('r1');
  await atPhrase(ctx, '둘째는'); await fig.draw('r2');
  await speechEnd(ctx); await fig.hide();
 }, {at: '첫째는'});
 return {segment: 'ws-01b', next: 'ws-01c: 첫 번째 부탁', aiRequests: 0};
};
