// 06-2 구간 03f(첫 페이지): R5 답의 속성 쪽 보기(필수면 걸리는 줄 수 — 단위 · 한계, 센서 표 3행 · 메모 28행) · 단위 덩어리(HYD-03 PS1) · 자료형 후보 → R6(쓰기 — properties.csv)를 보내고 답이 끝날 때까지.
// 시작: wo-03e 끝(R5 답이 선 화면, 앞 take를 준다). 끝: R6 답이 선 화면 → 녹화 뒤 사본 SEG=03f. 답을 짚는 글은 FIND(r5Unit · r5Limit · r5Ps1 · r5Types).
import {atPhrase} from './lab-common.mjs';
import {ui, RESUME, QE, guideIn, seamOut, keepEnd, open, tab, mark, cx, cxMark, toAnswer, paste, send, answer, waitSay, askOf} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const G = await guideIn(c, ctx, 'vs', {items: [...QE, 'todo'], ring: 'm2'});
 if (RESUME == null) await cx(c, ctx, 'r5Limit');
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 let since = RESUME;
 if (since == null) {
  await ctx.say('wo0330', async () => {
   await cxMark(c, ctx, 'r5Unit', 'underline');
   await atPhrase(ctx, '한계는 필수로 두면'); await cxMark(c, ctx, 'r5Limit', 'underline');
   await atPhrase(ctx, '한 줄 열어 보죠'); await tab(c, ctx, 'sensors.csv'); await mark(c, ctx, 3); await mark(c, ctx, 3, {cell: 7, shape: 'box', keep: true, point: false});
   await atPhrase(ctx, '메모에는'); await open(c, ctx, 'data/field_notes.md'); await mark(c, ctx, 28, {sub: '「한계」 칸은 인터록이 걸리는 값이고', shape: 'underline'});
   await atPhrase(ctx, '그래서 한계는'); await toAnswer(c, ctx);
  }, {at: '센서의 단위는 걸리는 줄이'});
  await ctx.say('wo0339', async () => {
   await cxMark(c, ctx, 'r5Ps1', 'band');
   await atPhrase(ctx, '그대로 담으면 18.2이고'); await cxMark(c, ctx, 'r5Ps1', 'underline', {scroll: false});
   await atPhrase(ctx, '나머지 속성과 자료형은'); await cxMark(c, ctx, 'r5Types', 'band');
   await atPhrase(ctx, '이렇게 고른 것과 이유를'); await paste(c, ctx, askOf('wo0339'));
   since = await send(c, ctx, '속성 표를 채웁니다');
  }, {at: 'Codex가 짚은 게'});
 }
 const waited = [];
 if (await waitSay(c, ctx, since, 'wo0396')) waited.push('wo0396');
 const r = await answer(c, ctx, since);
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '03f');
 return {segment: 'wo-03f', page: 0, cut, ask: 'R6', aiRequests: since == null ? 0 : 1, answer: r.message, codexMs: r.ms, used: r.used, waitLines: waited, next: 'wo-03g: python run.py properties'};
};
