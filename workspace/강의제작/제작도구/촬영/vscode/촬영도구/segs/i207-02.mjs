// 통합 2회차 07편 구간 02: 새 터미널 → 경로 확인 → python run.py 첫 실행(원자료와 모델 개수). AI 요청 없음.
// 시작: i207-01 끝(README.md 탭, data 펼침, 빈 Codex). output/ 없음, 터미널 없음.
import {labUi, atPhrase, afterResult, termLine, termWait, exists, newTerminal, waitRun} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.i207.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에

export default async ctx => {
 const c = await labUi(ctx);
 if (await exists(ctx, LAB + '/output')) throw Error('output/이 이미 있음 — i207-reset.mjs로 지우고 시작');
 if (await c.serial(() => ctx.p.evaluate(() => !!document.querySelector('.terminal-wrapper')?.checkVisibility()))) throw Error('터미널이 이미 열려 있음');
 await c.installPointer(ctx.prev ? null : {x: 120, y: 200});
 await ctx.begin();
 await ctx.say('i207-0201', () => newTerminal(c, ctx), {at: '왼쪽 위 줄 세 개 메뉴에서'});
 await termWait(ctx, 'graph-lab>');
 await afterResult(ctx);
 await ctx.say('i207-0202', async () => { const q = await termLine(c, ctx, 'graph-lab>'); await c.move(q.x, q.y); }, {at: '글자 앞 경로가'});
 // 학생 명령 · 웹판 덧붙임 · Enter를 그 말을 하는 구절에 맞춘다. 터미널 초점 확인은 공용 lab-common이 맡는다.
 await ctx.say('i207-0203', async () => {
  await c.typeKeys('python run.py'); await atPhrase(ctx, 'no-open을 붙여');
  await c.typeKeys(' --no-open'); await atPhrase(ctx, '실행할게요');
  await c.key('Enter');
 }, {at: 'python run.py를'});
 await waitRun(ctx, LAB);
 await ctx.say('i207-0204', async () => { const q = await termLine(c, ctx, '노드 206'); await c.move(q.x, q.y); }, {at: '터미널에'});
 await ctx.say('i207-0205', async () => { const q = await termLine(c, ctx, '결과: output/result.html'); await c.move(q.x, q.y); }, {at: '여러분 PC에서는'});
 return {segment: 'i207-02', next: 'i207-03: 결과 화면 공간', aiRequests: 0};
};
