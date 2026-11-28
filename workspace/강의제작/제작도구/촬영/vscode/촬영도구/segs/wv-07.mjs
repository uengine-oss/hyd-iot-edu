// 통합 2회차 06-1편 구간 07(첫 페이지 — 웹 VS Code): AI를 어디에 두고 일할까 — 편집기 위에 펜 그림 하나를 두 칸으로 긋는다(왼쪽 ① 모를 때 — 사람과 AI가 나란히 물어 가며, 오른쪽 ② 알고 나면 — 사람이 위에서 방향을 잡고 판단).
// 시작: wv-06b 끝(막연한 부탁의 답이 남은 화면). 앞 take: wv-06b. Codex를 부르지 않고 답에 기대지 않는다. 그림은 wv0702의 말이 끝날 때 걷는다(구간 끝에 떠 있으면 녹화가 멈춘다).
// 끝: 시작과 같은 화면, 펜 그림 없음.
import {labUi, atPhrase} from './lab-common.mjs';
import {ROLE, answerScroll, speechEnd, snap} from './wv-common.mjs';

export default async ctx => {
 const c = await labUi(ctx);
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 const fig = c.pen(ROLE);
 await ctx.say('wv0701', async () => {
  await fig.draw('h1', 'a1');
  await atPhrase(ctx, '먼저 물어봅니다'); await fig.draw('ha', 'ah');
  await atPhrase(ctx, '딱 그 첫날이에요'); await fig.draw('t1');
  await atPhrase(ctx, '우리만 알지만'); await fig.draw('k1');
  await atPhrase(ctx, '금방 다 읽어 내죠'); await fig.draw('k2');
  await snap(ctx, 'wv0701');
 }, {at: '첫날을 떠올려 보면'});
 await ctx.say('wv0702', async () => {
  await fig.draw('h2', 'a2');
  await atPhrase(ctx, '우리가 정하고 Codex가 따릅니다'); await fig.draw('down');
  await atPhrase(ctx, '내가 정해요'); await fig.draw('t2');
  await snap(ctx, 'wv0702');
  await speechEnd(ctx); await fig.hide();
 }, {at: '파악이 끝나면'});
 return {segment: 'wv-07', next: 'wv-08: 갖춰서 다시 부탁하기(Codex 요청)', aiRequests: 0, answerScroll: await answerScroll(c, ctx)};
};
