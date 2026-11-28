// 06-2 구간 02b(첫 페이지): R1 답 보기(근거 칸 · 오일 쿨러 줄을 센서 표와 맞춰 보기 · 갈래로 남긴 줄) → R2(쓰기 — expected.csv에 정해진 줄만)를 보내고 답이 끝날 때까지.
// 시작: wo-02a 끝(R1 답이 다 서고 패널이 답 끝으로 굴러가 있다 — 앞 take를 준다). 끝: R2 답이 다 선 화면. Codex가 expected.csv를 고친다 → 녹화 뒤 사본 SEG=02b.
// 답을 짚는 글은 wo-common.mjs FIND(r1*) — 녹화한 R1 답에 맞춘다. 이 구간은 R1 답이 선 뒤에 리허설할 수 있다(WO_NOSEND=1이면 R2를 보내지 않는다).
import {atPhrase} from './lab-common.mjs';
import {ui, RESUME, QE, guideIn, seamOut, keepEnd, open, mark, markAll, cx, cxMark, toAnswer, paste, send, answer, waitSay, askOf} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm1'});
 if (RESUME == null) await cx(c, ctx, 'r1Oil');   // 시작 화면에 R1 답이 있는지 먼저 본다
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 let since = RESUME;
 if (since == null) {
  await ctx.say('wo0206', async () => {
   await cxMark(c, ctx, 'r1Evidence', 'underline');
   await atPhrase(ctx, 'HYD-01의 오일 쿨러에는'); await cxMark(c, ctx, 'r1Oil', 'band');
   await atPhrase(ctx, '근거로 적어 준 센서 표를'); await open(c, ctx, 'data/sensors.csv'); await markAll(c, ctx, [2, 3, 10]);
   await atPhrase(ctx, '붙은곳 칸에 오일 쿨러라고'); await markAll(c, ctx, [2, 3, 10], {cell: 3, shape: 'underline'});
   await atPhrase(ctx, '태그도 답에 적힌 그대로'); await markAll(c, ctx, [2, 3, 10], {cell: 1, shape: 'underline'});
   await atPhrase(ctx, '맞게 찾아왔습니다'); await toAnswer(c, ctx);
  }, {at: '줄 끝을 보면'});
  await ctx.say('wo0207', async () => {
   await cxMark(c, ctx, 'r1Pump', 'box');
   await atPhrase(ctx, '두 번째 질문의 줄들이'); await cxMark(c, ctx, 'r1Q2', 'box');
  }, {at: '펌프에 달린 장치를 적는 줄'});
  await ctx.say('wo0281', async () => {
   await paste(c, ctx, askOf('wo0281'));
   since = await send(c, ctx, '꼭 붙여요');
  }, {at: '그러니 지금은'});
 }
 const waited = [];
 if (await waitSay(c, ctx, since, 'wo0293')) waited.push('wo0293');
 const r = await answer(c, ctx, since);
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '02b');
 return {segment: 'wo-02b', page: 0, cut, ask: 'R2', aiRequests: since == null ? 0 : 1, answer: r.message, codexMs: r.ms, used: r.used, waitLines: waited, next: 'wo-02c: expected.csv 열어 보기 · python run.py expected'};
};
