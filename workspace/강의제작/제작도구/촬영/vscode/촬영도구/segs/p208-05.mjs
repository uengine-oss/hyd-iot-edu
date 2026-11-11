// 실전 2회차 08편 구간 05: 결과 화면 공간 — F5로 새로 고쳐 모델 파일과 랩 DB(0)의 개수 표. AI 요청 없음.
import {labUi, atPhrase, page, inView, tableCell} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.p208.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에

export default async ctx => {
 const c = await labUi(ctx);
 if (await c.serial(() => ctx.p.url()) !== page(LAB)) { await c.serial(() => ctx.p.goto(page(LAB))); await ctx.sleep(800); }
 await c.installPointer({x: 1300, y: 160});
 await ctx.begin();
 await ctx.say('p208-0501', async () => {
  await c.gate(); await c.serial(() => ctx.p.reload());   // 학생 화면의 F5(촬영준비 길 6 — CDP F5 키는 file:// 문서를 다시 읽지 않았다)
  await ctx.waitFor(() => document.readyState === 'complete' && document.title.startsWith('랩 DB 준비') && !document.getElementById('recording-pointer'));
  await c.installPointer({x: 1300, y: 160});
  const a = inView(await tableCell(c, ctx, '노드', 1, 3)); await c.move(a.x, a.y); await atPhrase(ctx, '오른쪽 칸이');
  const b = inView(await tableCell(c, ctx, '노드', 2, 3)); await c.move(b.x, b.y);
 }, {at: 'F5를'});
 await ctx.say('p208-0502', async () => { const q = inView(await tableCell(c, ctx, '관계', 1, 3)); await c.move(q.x, q.y); }, {at: '두 칸이'});
 return {segment: 'p208-05', next: 'p208-06: Codex와 모델 파악(가이드 3단계)', aiRequests: 0};
};
