// 06-2 구간 03b(첫 페이지): R3 답 보기(낱말 가르기 · 물리량 — 두 길 펜 그림 · 식별자 선택지) → R4(쓰기 — classes.csv)를 보내고 답이 끝날 때까지.
// 시작: wo-03a 끝(R3 답이 선 화면, 앞 take를 준다). 끝: R4 답이 선 화면 → 녹화 뒤 사본 SEG=03b. 답을 짚는 글은 FIND(r3*).
import {atPhrase} from './lab-common.mjs';
import {ui, RESUME, QE, guideIn, guideHide, guideShow, seamOut, keepEnd, open, mark, markAll, tab, note, cx, cxMark, cxRows, toAnswer, speechEnd, PANELS, paste, send, answer, waitSay, askOf} from './wo-common.mjs';
const rowsOf = cxRows;

export default async ctx => {
 const c = await ui(ctx, 0);
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm2'});
 if (RESUME == null) await cx(c, ctx, 'r3Groups');
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 let since = RESUME;
 if (since == null) {
  await ctx.say('wo0324', async () => {
   await rowsOf(c, ctx, 'r3Class');
   await atPhrase(ctx, '그 대상에 딸린 값은 속성으로'); await rowsOf(c, ctx, 'r3Prop');
   await atPhrase(ctx, '같은 말은 관계로'); await rowsOf(c, ctx, 'r3Rel');
  }, {at: '설비, 구성 요소, 센서, 부품은'});
  const P = c.pen(PANELS);
  await ctx.say('wo0381', async () => {
   await cxMark(c, ctx, 'r3Groups', 'underline');
   await atPhrase(ctx, '유온과 오일 온도처럼'); await tab(c, ctx, 'sensors.csv'); await mark(c, ctx, 2, {cell: 4, shape: 'underline'}); await mark(c, ctx, 12, {cell: 4, shape: 'underline', keep: true, point: false});
   await atPhrase(ctx, '속성으로 두면 센서마다'); await guideHide(G); await P.draw('lt', 'l1', 'l2', 'l3', 'l4');
   await atPhrase(ctx, '유온을 대상 하나로'); await P.draw('rt', 'q');
   await atPhrase(ctx, '센서들을 거기에 이어'); await P.draw('r1', 'm1', 'r2', 'm2', 'r3', 'm3', 'r4', 'm4', 'mt');
   await speechEnd(ctx); await P.hide(); await guideShow(G);
  }, {at: '열다섯 묶음으로'});
  await ctx.say('wo0337', async () => {
   await cxMark(c, ctx, 'r3SensorOpt', 'band'); await cxMark(c, ctx, 'r3SensorClash', 'band', {keep: true, point: false, scroll: false});
   await atPhrase(ctx, '학교에 이름이 같은'); await note(c, 'ts1');
   await atPhrase(ctx, '구성 요소도 같은 까닭으로'); await cxMark(c, ctx, 'r3CompOpt', 'underline');
   await atPhrase(ctx, '리턴 필터 같은 이름은'); await open(c, ctx, 'data/components.csv'); await markAll(c, ctx, [8, 18, 27, 35, 42]);
   await atPhrase(ctx, '이렇게 지어도 한 군데가'); await toAnswer(c, ctx);
   await atPhrase(ctx, '부품은 사내 품번 하나로'); await cxMark(c, ctx, 'r3PartOpt', 'underline');
   await speechEnd(ctx); await c.note(null);
  }, {at: '센서부터 보죠'});
  await ctx.say('wo0325', async () => {
   await paste(c, ctx, askOf('wo0325'));
   since = await send(c, ctx, '같이 남게 합니다');
  }, {at: '고른 것을 이제 표에'});
 }
 const waited = [];
 if (await waitSay(c, ctx, since, 'wo0391')) waited.push('wo0391');
 const r = await answer(c, ctx, since);
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '03b');
 return {segment: 'wo-03b', page: 0, cut, ask: 'R4', aiRequests: since == null ? 0 : 1, answer: r.message, codexMs: r.ms, used: r.used, waitLines: waited, next: 'wo-03c: classes.csv 열어 보기 · python run.py classes'};
};
