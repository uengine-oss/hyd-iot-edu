// 06-2 구간 05d(첫 페이지): R12 답 — Codex가 물어 온 센서 셋에 하나씩 답하기(메모 27행) → R13(쓰기 — quantity_rules.py 규칙)을 보내고, 기다리는 동안 센서 표 10 · 40행(FS2)을 본다. 답이 끝날 때까지.
// 시작: wo-05c 끝(R12 답이 선 화면, 앞 take를 준다). 끝: R13 답이 선 화면 → 녹화 뒤 사본 SEG=05d.
// Codex가 물어 온 센서는 Codex에 달렸다 — FIND(r12Q1~3)와 대본 wo0511 · wo0512(부탁 글) · wo0513 · wo0514 · wo0515를 한 묶음으로 맞춘다. 묻지 않고 바로 코드를 썼으면 뜻이 다른 것이라 모아서 묻는다(대본).
import {atPhrase} from './lab-common.mjs';
import {ui, LAB, RESUME, QE, guideIn, seamOut, keepEnd, open, tab, mark, cx, cxMark, paste, send, answer, waitSay, askOf} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 if (RESUME == null && !(await ctx.fs.readFile(LAB + '/app/features/quantity_rules.py', 'utf8')).includes('raise NotImplementedError')) throw Error('quantity_rules.py가 이미 채워져 있음 — R12에 Codex가 묻지 않고 코드를 썼다(대본 wo0511: 뜻이 다른 것이라 모아서 묻는다)');
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm2'});
 if (RESUME == null) await cx(c, ctx, 'r12Q1');
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 let since = RESUME;
 if (since == null) {
  await ctx.say('wo0511', async () => {
   await cxMark(c, ctx, 'r12Q1', 'band');
   await atPhrase(ctx, '메모에 적혀 있으니까요'); await open(c, ctx, 'data/field_notes.md'); await mark(c, ctx, 27, {sub: '태그 이름(TS1, PS1 …)은 한일유압 파워팩(HPP-45A · 45B)이 모두 같은 이름을 씁니다', shape: 'underline'});
   await atPhrase(ctx, '이동식 설비의 유온계는'); await cxMark(c, ctx, 'r12Q2', 'band');
   await atPhrase(ctx, 'HYD-04의 FS2는'); await cxMark(c, ctx, 'r12Q3', 'band');
  }, {at: 'HYD-02의 TS1은'});
  await ctx.say('wo0512', async () => {
   await paste(c, ctx, askOf('wo0512'));
   since = await send(c, ctx, '짚어 달라는 거예요');
  }, {at: '이 답을 그대로 적어 보내면서'});
 }
 await ctx.say('wo0513', async () => {
  await tab(c, ctx, 'sensors.csv'); await mark(c, ctx, 10, {cell: 1, shape: 'underline'}); await mark(c, ctx, 10, {cell: 4, shape: 'underline', keep: true, point: false});
  await atPhrase(ctx, '40행'); await mark(c, ctx, 40); await mark(c, ctx, 40, {cell: 1, shape: 'underline', keep: true, point: false}); await mark(c, ctx, 40, {cell: 4, shape: 'box', keep: true, point: false});
 }, {at: '센서 표 10행'});
 const waited = [];
 if (await waitSay(c, ctx, since, 'wo0595')) waited.push('wo0595');
 const r = await answer(c, ctx, since);
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '05d');
 return {segment: 'wo-05d', page: 0, cut, ask: 'R13', aiRequests: since == null ? 0 : 1, answer: r.message, codexMs: r.ms, used: r.used, waitLines: waited, next: 'wo-05e: 규칙 코드 보기 · python run.py quantities'};
};
