// 실전 2회차 08편 구간 02: 새 터미널 → 경로 확인 → python run.py 첫 실행(원자료와 모델 개수). AI 요청 없음.
// 시작: p208-01 끝(README.md 탭, data 펼침, 빈 Codex). output/ 없음, 터미널 없음.
import {labUi, atPhrase, afterResult, termLine, termWait, exists, newTerminal, waitRun} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.p208.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에

export default async ctx => {
 const c = await labUi(ctx);
 if (await exists(ctx, LAB + '/output')) throw Error('output/이 이미 있음 — p208-reset.mjs로 지우고 시작');
 if (await c.serial(() => ctx.p.evaluate(() => !!document.querySelector('.terminal-wrapper')?.checkVisibility()))) throw Error('터미널이 이미 열려 있음');
 await c.installPointer(ctx.prev ? null : {x: 120, y: 200});
 await ctx.begin();
 await ctx.say('p208-0201', () => newTerminal(c, ctx), {at: '왼쪽 위 줄 세 개 메뉴에서'});
 await termWait(ctx, 'graph-lab>');
 await afterResult(ctx);
 await ctx.say('p208-0202', async () => { const q = await termLine(c, ctx, 'graph-lab>'); await c.move(q.x, q.y); }, {at: '커서 앞의 경로가'});
 await ctx.say('p208-0203', async () => { await c.typeKeys('python run.py'); }, {at: 'python run.py를'});
 await ctx.say('p208-0204', async () => { await c.typeKeys(' --no-open'); await c.key('Enter'); }, {at: 'no-open을 붙여'});
 await waitRun(ctx, LAB);
 await ctx.say('p208-0205', async () => {
  const a = await termLine(c, ctx, '원자료 파일과 행 수'); await c.move(a.x, a.y); await atPhrase(ctx, '그 아래에 이번에');
  const b = await termLine(c, ctx, '관계 326'); await c.move(b.x, b.y);   // 개수 줄의 첫 줄(관계가 노드보다 앞)
 }, {at: '터미널에'});
 await ctx.say('p208-0206', async () => { const q = await termLine(c, ctx, '결과: output/result.html'); await c.move(q.x, q.y); }, {at: '여러분 PC에서는'});
 return {segment: 'p208-02', next: 'p208-03: 결과 화면 공간', aiRequests: 0};
};
