// 통합 2회차 07편 구간 04: 랩 DB를 풀고 python run.py db로 처음 만든다(Docker 필요, 이 PC 약 20초). AI 요청 없음.
// 시작: i207-02 끝(터미널 열림). 이 폴더의 랩 DB가 없어야 한다(.lab_connection.json 없음 — i207-reset.mjs).
// 0404를 말한 뒤 출력이 나올 때까지의 무출력 대기는 합성 때 가운데만 줄인다(cut.py, 앞뒤 2초는 남긴다).
import {labUi, atPhrase, afterResult, termLine, termWait, exists} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.i207.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에
const READY = '이 폴더의 랩 DB를 준비했습니다';

export default async ctx => {
 const c = await labUi(ctx);
 if (await exists(ctx, LAB + '/.lab_connection.json')) throw Error('이 폴더의 랩 DB가 이미 있음 — 「처음 만든 DB」 장면이 아니다');
 await c.installPointer(ctx.prev ? null : {x: 700, y: 760});
 await ctx.begin();
 await ctx.say('i207-0401', async () => { const q = await termLine(c, ctx, 'graph-lab>'); await c.move(q.x + 200, q.y - 60); }, {at: '다시 VS Code로'});
 await ctx.say('i207-0402', async () => { const q = await termLine(c, ctx, 'graph-lab>'); await c.move(q.x, q.y); }, {at: 'Docker Desktop이'});
 await ctx.say('i207-0403', async () => {
  // 결과 화면 공간에 다녀온 뒤라 입력 초점을 터미널로 먼저 옮긴다 — 초점이 터미널이 아니면 labUi가 글을 보내지 않고 멈춘다
  const q = await termLine(c, ctx, 'graph-lab>'); await c.clickAt(q.x + 260, q.y);
  await c.typeKeys('python run.py db'); await atPhrase(ctx, 'no-open을 붙이고');
  await c.typeKeys(' --no-open'); await atPhrase(ctx, '실행할게요');
  await c.key('Enter');
 }, {at: 'python run.py db를'});
 await ctx.say('i207-0404');
 await termWait(ctx, READY, 90000);
 await afterResult(ctx);
 await ctx.say('i207-0405', async () => {
  const a = await termLine(c, ctx, READY); await c.move(a.x, a.y); await atPhrase(ctx, '맨 끝 줄은');
  const b = await termLine(c, ctx, '열린 화면에서 F5로'); await c.move(b.x, b.y);
 }, {at: '터미널에'});
 return {segment: 'i207-04', next: 'i207-05: 결과 화면 공간에서 모델 파일 · 랩 DB 개수', aiRequests: 0};
};
