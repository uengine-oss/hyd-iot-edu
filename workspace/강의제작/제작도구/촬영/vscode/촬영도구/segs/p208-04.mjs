// 실전 2회차 08편 구간 04: python run.py db로 이 폴더의 랩 DB를 처음 만든다(Docker 필요, 이 PC 약 20초). AI 요청 없음.
// 시작: p208-02 끝(터미널 열림). 이 폴더의 랩 DB가 없어야 한다(.lab_connection.json 없음 — p208-reset.mjs).
// 0404를 말한 뒤 출력이 나올 때까지의 무출력 대기는 합성 때 가운데만 줄인다(cut.py, 앞뒤 2초는 남긴다).
import {labUi, afterResult, termLine, termWait, exists} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.p208.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에

export default async ctx => {
 const c = await labUi(ctx);
 if (await exists(ctx, LAB + '/.lab_connection.json')) throw Error('이 폴더의 랩 DB가 이미 있음 — 「처음 만든 DB」 장면이 아니다');
 await c.installPointer(ctx.prev ? null : {x: 700, y: 760});
 await ctx.begin();
 await ctx.say('p208-0401', async () => { const q = await termLine(c, ctx, 'graph-lab>'); await c.move(q.x + 200, q.y - 60); }, {at: '다시 VS Code로'});
 await ctx.say('p208-0402', async () => { const q = await termLine(c, ctx, 'graph-lab>'); await c.move(q.x, q.y); }, {at: 'Docker Desktop이'});
 await ctx.say('p208-0403', async () => {
  // 입력이 터미널로 가도록 먼저 누른다 — 빈 Codex 입력칸에 Enter가 가면 「Unable to send message」 상자가 뜬다
  const q = await termLine(c, ctx, 'graph-lab>'); await c.clickAt(q.x + 260, q.y);
  await c.typeKeys('python run.py db');   // --no-open은 붙이지 않는다 — result.html이 02에서 이미 생겨 브라우저를 열지 않는다(run.py)
 }, {at: 'python run.py db를'});
 await ctx.say('p208-0404', async () => { await c.key('Enter'); }, {at: '직접 실행해요'});
 await ctx.say('p208-0405');   // 말만(기다리는 동안)
 await termWait(ctx, '이 폴더의 랩 DB를 준비했습니다', 180000);
 await termWait(ctx, '열린 화면에서 F5로');
 await afterResult(ctx);
 await ctx.say('p208-0406', async () => { const q = await termLine(c, ctx, '이 폴더의 랩 DB를 준비했습니다'); await c.move(q.x, q.y); }, {at: '터미널에'});
 await ctx.say('p208-0407', async () => { const q = await termLine(c, ctx, '열린 화면에서 F5로'); await c.move(q.x, q.y); }, {at: '맨 끝 줄은', gap: 500});
 if (!(await exists(ctx, LAB + '/.lab_connection.json'))) throw Error('랩 DB 연결 파일이 생기지 않음');
 return {segment: 'p208-04', next: 'p208-05: 결과 화면 공간에서 모델 파일 · 랩 DB 개수', aiRequests: 0};
};
