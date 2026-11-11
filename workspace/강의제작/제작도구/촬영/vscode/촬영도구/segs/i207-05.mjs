// 통합 2회차 07편 구간 05: 결과 화면 공간 — F5로 새로 고쳐 모델 파일과 랩 DB(0)의 개수 표. AI 요청 없음.
// 시작: i207-03이 연 결과 화면(원자료와 모델). 녹화 전에 다시 읽지 않는다 — F5로 새 화면이 뜨는 것이 이 구간의 장면이다.
import {labUi, atPhrase, cell, inView, page} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.i207.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에

export default async ctx => {
 const c = await labUi(ctx);
 if (await c.serial(() => ctx.p.url()) !== page(LAB)) { await c.serial(() => ctx.p.goto(page(LAB))); await ctx.sleep(800); }
 await c.installPointer({x: 1300, y: 160});
 await ctx.begin();
 await ctx.say('i207-0501', async () => {
  const f = {x: 1300, y: 160}; await c.move(f.x, f.y);   // 학생 화면의 F5(촬영준비 길 6 — CDP F5 키는 file:// 문서를 다시 읽지 않았다)
  await c.gate(); await c.serial(() => ctx.p.reload());
  await ctx.waitFor(() => document.readyState === 'complete' && document.title.startsWith('랩 DB 준비') && !document.getElementById('recording-pointer'));
  await c.installPointer(f);
  await atPhrase(ctx, '가운데 칸이');
  const a = inView(await cell(c, ctx, '노드', 1)); await c.move(a.x, a.y); await atPhrase(ctx, '오른쪽 칸이');
  const b = inView(await cell(c, ctx, '노드', 2)); await c.move(b.x, b.y);
 }, {at: 'F5를'});
 await ctx.say('i207-0502', async () => { const q = inView(await cell(c, ctx, '관계', 1)); await c.move(q.x, q.y); }, {at: '두 칸의'});
 return {segment: 'i207-05', next: 'i207-06: Codex와 모델 파악(가이드 3단계)', aiRequests: 0};
};
