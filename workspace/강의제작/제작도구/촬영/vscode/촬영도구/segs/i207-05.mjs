// 통합 2회차 07편 구간 05: 결과 화면 공간 — F5로 새로 고쳐 모델 파일과 랩 DB(0)의 개수 표. AI 요청 없음.
import {vscode} from '../ui.mjs';
import {PAGE, cell} from './i207-common.mjs';

export default async ctx => {
 const c = await vscode(ctx);
 if (await c.serial(() => ctx.p.url()) !== PAGE) { await c.serial(() => ctx.p.goto(PAGE)); await ctx.sleep(800); }
 await c.installPointer({x: 1300, y: 160});
 await ctx.begin();
 await ctx.say('i207-0501', async () => {
  await c.gate(); await c.serial(() => ctx.p.reload());   // 학생 화면의 F5(촬영준비 길 6 — CDP F5 키는 file:// 문서를 다시 읽지 않았다)
  await ctx.waitFor(() => document.readyState === 'complete' && document.title.startsWith('랩 DB 준비') && !document.getElementById('recording-pointer'));
  await c.installPointer({x: 1300, y: 160});
  const a = await cell(c, ctx, '노드', 1); await c.move(a.x, a.y); await ctx.sleep(1500);
  const b = await cell(c, ctx, '노드', 2); await c.move(b.x, b.y);
 }, {at: 'F5를'});
 await ctx.say('i207-0502', async () => { const q = await cell(c, ctx, '관계', 1); await c.move(q.x, q.y); }, {at: '두 칸의'});
 return {segment: 'i207-05', next: 'i207-06: Codex와 모델 파악(가이드 3단계)', aiRequests: 0};
};
