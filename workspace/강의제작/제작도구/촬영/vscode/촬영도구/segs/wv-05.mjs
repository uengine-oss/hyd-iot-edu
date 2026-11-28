// 통합 2회차 06-1편 구간 05(첫 페이지 — 웹 VS Code): 바이브 코딩과 Codex — output을 접고, 바이브 코딩 한 줄 글상자, Codex 패널과 탐색기를 짚는다. Codex를 부르지 않는다.
// 시작: wv-04c 끝(output이 펴짐, 터미널 출력, 편집기에 field_notes.md · equipment.csv, 빈 Codex 새 대화). 앞 take: wv-04c.
// 끝: output이 접힘, 강조 · 글상자 없음, 빈 Codex 새 대화(다음 wv-06a가 막연한 부탁을 보낸다).
import {labUi, atPhrase, em} from './lab-common.mjs';
import {area, fold, note, speechEnd, snap} from './wv-common.mjs';

export default async ctx => {
 const c = await labUi(ctx);
 if (!(await c.serial(() => ctx.p.text())).includes('Ask Codex anything')) throw Error('빈 Codex 새 대화가 아님 — wv-04c 끝 상태에서 시작한다 (segs/wv-05.mjs)');
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 await ctx.say('wv0501', async () => {
  await fold(c, ctx, 'output', 1, false);
  await atPhrase(ctx, '바이브 코딩이라고'); await note(c, 'vibe');
  await snap(ctx, 'wv0501');
  await speechEnd(ctx); await c.note(null);
 }, {at: '자료가 다 온 건'});
 await ctx.say('wv0502', async () => {
  await c.emph(em.codex(0.02, 0.01, 0.98, 0.99), {shape: 'box'});
  await snap(ctx, 'wv0502-codex');
  await atPhrase(ctx, '이 폴더 안에서'); await c.emph(await area(c, ctx, '.part.sidebar'), {shape: 'box'});
  await snap(ctx, 'wv0502-explorer');
 }, {at: '오른쪽에 열려 있는 이 칸이'});
 await ctx.say('wv0503', async () => { await c.clearEmph(); }, {at: '이런 도구가'});
 return {segment: 'wv-05', next: 'wv-06a: 막연한 부탁(Codex 요청)', aiRequests: 0};
};
