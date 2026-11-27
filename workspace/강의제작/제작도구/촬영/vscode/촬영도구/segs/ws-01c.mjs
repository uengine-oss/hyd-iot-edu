// 5분 예시 구간 01c(첫 페이지): 첫 번째 부탁(갈래마다 답이 어떻게 달라지는지)을 Codex에 보내고 답이 끝날 때까지 기다린다 — 실제 요청(리허설도 같다), 자르지 않는다.
// 시작: ws-01b 끝(components.csv가 열린 화면, 빈 Codex 새 대화). 끝: 답이 다 선 화면. 끝난 답은 result.answer로 남고 ws-01d의 말 · 짚기를 그 답에 맞춘다.
import {labUi, atPhrase, codexFocus, codexType, codexSubmit, codexWait, waitLines} from './lab-common.mjs';
import {ASK1} from './ws-common.mjs';

export default async ctx => {
 const c = await labUi(ctx);
 if (!(await c.serial(() => ctx.p.text())).includes('Ask Codex anything')) throw Error('빈 Codex 새 대화가 아님');
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 let since = 0;
 await ctx.say('ws0105', async () => {
  await codexFocus(c, ctx); await codexType(c, ctx, ASK1);
  await atPhrase(ctx, '손해 볼 게 없거든요'); since = await codexSubmit(c, ctx);
 }, {at: '부탁 맨 앞에는'});
 await ctx.say('ws0106', async () => {
  await c.note(['클래스 하나', '식별자 하나', '관계 하나'], {title: '길 2를 고르면 늘어나는 것', at: [560, 600]});   // 편집기 아래쪽 — 오른쪽 위(기본)는 Codex 칸의 보낸 부탁을 가렸다(ws01c-r1)
  const q = ctx.__cue; if (!ctx.rehearsal) { const w = q.t0 + q.dur - Date.now(); if (w > 0) await ctx.sleep(w); }
  await c.note(null);
 }, {at: '둘째 길은 공짜가'});
 const waited = await waitLines(ctx, since, ['ws0107']);
 const r = await codexWait(ctx, since);
 if (ctx.rehearsal) await ctx.fs.writeFile(ctx.out + '/답.md', r.message ?? '');
 return {segment: 'ws-01c', next: 'ws-01d: 답 보고 고르기', aiRequests: 1, answer: r.message, codexMs: r.ms, used: r.used, waitLines: waited};
};
