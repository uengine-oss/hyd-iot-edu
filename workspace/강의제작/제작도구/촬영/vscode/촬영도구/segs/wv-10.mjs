// 통합 2회차 06-1편 구간 10(첫 페이지 — 웹 VS Code): 이렇게 말하는 대신 → 이렇게(큰 표 펜 그림, 화면 가운데) · 일하는 차례 일곱(글상자). Codex를 부르지 않고 답에 기대지 않는다.
// 시작: wv-09b 끝(갖춘 부탁의 답이 남은 화면). 앞 take: wv-09b. 끝: 시작과 같은 화면, 펜 그림 · 글상자 없음.
// 표의 다섯째 행(갈래마다 결과를 받아 보기)은 이 편에서 띄우지 않는다(대본 wv1004). 강사는 표 · 글상자의 글을 읽지 않는다.
// 1행 왼쪽 칸: wv1001에 「현장 메모 정리해 줘」(L0)를 먼저 띄우고, wv1002에서 그 자리에 「정리해 줘」(L1)를 긋는다 — 그림 층에 줄어드는 움직임이 없어 지우고 긋는다(판정/녹화모듈_06-1.md).
import {labUi, atPhrase} from './lab-common.mjs';
import {INSTEAD, INSTEAD_LEFT, note, noteLines, penArea, faint, answerScroll, speechEnd, snap} from './wv-common.mjs';

export default async ctx => {
 const c = await labUi(ctx);
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 const fig = c.pen(INSTEAD);
 await ctx.say('wv1001', async () => {
  await atPhrase(ctx, '그 두 부탁을'); await fig.draw('ttl', 'L0');
  await snap(ctx, 'wv1001');
 }, {at: '같은 Codex에 같은 자료인데'});
 await ctx.say('wv1002', async () => {
  await fig.erase('L0'); await fig.draw('L1', 'L2');
  await atPhrase(ctx, '오른쪽처럼'); await fig.draw('R1', 'T1', 'R2', 'T2');
  await snap(ctx, 'wv1002');
 }, {at: '정리해 줘, 이거 좀 봐 줘'});
 await ctx.say('wv1003', async () => {
  await fig.draw('L3', 'L4');
  await atPhrase(ctx, '적어 준 거죠'); await fig.draw('R3', 'T3', 'R4', 'T4');
  await snap(ctx, 'wv1003');
 }, {at: '다르게 적힌 데 있으면 알려 줘, 알아서 해 줘'});
 await ctx.say('wv1004', async () => {
  await c.emph(await penArea(c, ctx, INSTEAD_LEFT), {shape: 'box'});
  await atPhrase(ctx, '오른쪽에서 뭐가 빠졌는지');
  for (const [i, t] of ['T1', 'T2', 'T3', 'T4'].entries()) await c.emph({pen: t}, {shape: 'underline', ...(i ? {keep: true, point: false} : {})});   // 꼬리표 넷
  await snap(ctx, 'wv1004');
  await speechEnd(ctx); await fig.hide();
 }, {at: '왼쪽 같은 말이'});
 await ctx.say('wv1005', async () => {
  await atPhrase(ctx, '일하는 차례도'); await note(c, 'order');
  await atPhrase(ctx, '방금 한 일이 그 맨 윗줄'); { const r = (await noteLines(c, ctx, 1, 1)).rects[0]; await c.emph({note: 1}, {shape: 'box', at: {x: r[0] - 40, y: r[1] + r[3] / 2 - 6}}); }   // 화살표는 글상자 왼쪽(오른쪽 아래에 두면 ② 줄 글을 덮는다)
  await atPhrase(ctx, '아래 줄들은'); await faint(c, ctx, await noteLines(c, ctx, 2), {shape: 'band', keep: true, point: false});   // ①의 테두리는 둔 채 ②~⑦을 흐리게 한꺼번에(읽지 않는다)
  await snap(ctx, 'wv1005');
  await atPhrase(ctx, '그런데 저는'); await c.note(null);
 }, {at: '부탁하는 말은 이렇게 채우고'});
 return {segment: 'wv-10', next: 'wv-11: 폴더가 이렇게 나뉜 까닭', aiRequests: 0, answerScroll: await answerScroll(c, ctx)};
};
