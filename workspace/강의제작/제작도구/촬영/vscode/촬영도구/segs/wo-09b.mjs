// 06-2 구간 09b(첫 페이지): R16 답 — 후보 셋 · 고른 후보 · 왜 지금 답할 수 없는지 → R17(쓰기 — 질문 4 기대 답, 없는 속성 이름은 나에게 물어보게)를 보내고 답이 끝날 때까지.
// 시작: wo-09a 끝(R16 답이 선 화면, 앞 take를 준다). 끝: R17 답이 선 화면(Codex가 속성 이름을 되물었으면 wo-09c, 묻지 않고 적었으면 wo-09d로 — PICK.askedName). 녹화 뒤 사본 SEG=09b.
// 부탁 글의 ○(후보 번호)는 PICK.candidate — R16 답을 보고 채운다(대본 wo0912 조작 칸). 후보의 글은 FIND(r16*).
import {atPhrase} from './lab-common.mjs';
import {ui, RESUME, QE, guideIn, seamOut, keepEnd, cx, cxMark, paste, send, answer, ask17} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const text = ask17();   // 후보 번호가 비었으면 여기서 멈춘다
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm5'});
 if (RESUME == null) await cx(c, ctx, 'r16Pick');
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 let since = RESUME;
 if (since == null) await ctx.say('wo0912', async () => {
  await cxMark(c, ctx, 'r16All', 'band');
  await atPhrase(ctx, '저는 이걸로 할게요'); await cxMark(c, ctx, 'r16Pick', 'box');
  await atPhrase(ctx, '지금은 답할 수 없다고'); await cxMark(c, ctx, 'r16Why', 'underline');
  await atPhrase(ctx, '하는 순서는 처음과'); await paste(c, ctx, text);
  since = await send(c, ctx, '한 줄 적게 합니다');
 }, {at: '후보가 세 개 왔습니다'});
 const r = await answer(c, ctx, since);
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '09b');
 return {segment: 'wo-09b', page: 0, cut, ask: 'R17', aiRequests: since == null ? 0 : 1, answer: r.message, codexMs: r.ms, used: r.used, next: 'wo-09c: Codex가 물은 속성 이름에 답하기(R18) — 묻지 않았으면 wo-09d'};
};
