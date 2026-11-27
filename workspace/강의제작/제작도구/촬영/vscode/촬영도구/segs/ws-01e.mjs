// 5분 예시 구간 01e(첫 페이지): 고른 것을 Codex에 말해 결정 표에 적고 그 결정대로 표를 맞추게 한다 — 실제 요청, 쓰기를 맡긴다(촬영준비 길 9). 답이 끝날 때까지 자르지 않는다.
// 시작: ws-01d 끝(첫 번째 답이 남은 Codex 대화 — 같은 대화에 이어 보낸다). 끝: 두 번째 답이 다 선 화면. Codex가 고친 파일은 ws-01f가 연다.
// 다시 찍으려면 Codex가 고친 표를 _3장끝/의 사본으로 되돌린 뒤 01c부터 찍는다(lab-common.mjs LABS.ws 주석).
import {labUi, atPhrase, codexFocus, codexType, codexSubmit, codexWait, waitLines} from './lab-common.mjs';
import {ASK2} from './ws-common.mjs';

export default async ctx => {
 const c = await labUi(ctx);
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 let since = 0;
 await ctx.say('ws0111', async () => {
  await codexFocus(c, ctx); await codexType(c, ctx, ASK2);
  await atPhrase(ctx, '맞춰 달라고 할게요'); since = await codexSubmit(c, ctx);
 }, {at: '고른 것은 Codex한테'});
 const waited = await waitLines(ctx, since, ['ws0112']);
 const r = await codexWait(ctx, since);
 if (ctx.rehearsal) await ctx.fs.writeFile(ctx.out + '/답.md', r.message ?? '');
 return {segment: 'ws-01e', next: 'ws-01f: 고친 표 열어 보기 · 돌리기', aiRequests: 1, answer: r.message, codexMs: r.ms, used: r.used, waitLines: waited};
};
