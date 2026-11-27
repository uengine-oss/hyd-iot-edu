// 5분 예시 구간 01d(첫 페이지): 첫 번째 답에서 볼 곳 셋(두 길 · 추천)을 짚고, 내 이유로 고른다. Codex를 다시 부르지 않는다(촬영준비 길 9).
// 시작: ws-01c 끝(답이 다 서고 패널이 답 끝으로 굴러가 있다). 앞 take를 주어 화살표를 잇는다. 찾는 글은 그 take의 답(ws01c-r2)에서 골랐다 — 답이 바뀌면 그 답에 맞춘다.
import {labUi, atPhrase, codexBoxes, codexScrollInto, em} from './lab-common.mjs';

const L13 = 'HYD-02,동력,유압 펌프,PMP-SEAL';
const one = async (c, ctx, css, has) => {
 const l = await codexBoxes(c, ctx, css, has);
 if (l.length !== 1) throw Error(ctx.cueId + ': Codex 답에서 「' + has + '」이 든 ' + css + '이 ' + l.length + '개 (segs/ws-01d.mjs)');
 return l[0];
};
const speechEnd = async ctx => { const q = ctx.__cue; if (!ctx.rehearsal) { const w = q.t0 + q.dur - Date.now(); if (w > 0) await ctx.sleep(w); } };

export default async ctx => {
 const c = await labUi(ctx);
 await one(c, ctx, 'strong', '속성으로 두면');   // 시작 화면에 그 답이 있는지 먼저 본다
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 await ctx.say('ws0108', async () => {
  await codexScrollInto(c, ctx, () => one(c, ctx, 'strong', '속성으로 두면'), 0.1);
  await atPhrase(ctx, '첫째는'); await c.emph(em.box(await one(c, ctx, 'strong', '속성으로 두면')), {shape: 'underline'});
  await atPhrase(ctx, '둘째는'); await c.emph(em.box(await codexScrollInto(c, ctx, () => one(c, ctx, 'strong', '실물을 따로 두면'), 0.35)), {shape: 'underline'});
  await atPhrase(ctx, '추천은 실물 쪽'); await c.emph(em.box(await codexScrollInto(c, ctx, () => one(c, ctx, 'strong', '추천'), 0.45)), {shape: 'underline'});
  await atPhrase(ctx, '결정은 아니라고'); await c.emph(em.box(await one(c, ctx, 'p', '실제 결정은 아닙니다')), {shape: 'band'});
 }, {at: '볼 곳은'});
 await ctx.say('ws0109', async () => {
  await c.note(['구성 요소마다 어떤 센서가 붙고,', '그 자리에 어떤 장치(일련번호)가 달렸나?'], {title: '첫 번째 질문', at: [560, 640]});
  await c.emph({note: '어떤 장치'}, {shape: 'underline'});
  await atPhrase(ctx, '보전팀이 옛 펌프의'); await c.emph(em.line(L13), {shape: 'underline', phrase: '철거(구 일련번호)'});
 }, {at: '우리 질문이'});
 await ctx.say('ws0110', async () => { await c.note(null); }, {at: '다만'});
 return {segment: 'ws-01d', next: 'ws-01e: 두 번째 부탁', aiRequests: 0};
};
