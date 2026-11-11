// 통합 2회차 07편 구간 01: 목적 · 폴더 · 제공 모델 · 자기 모델은 선택 · AGENTS. 요청 · 파일 변경 없음.
// 시작: i207-reset.mjs가 만든 화면(graph-lab, README.md 탭 하나, 폴더 접힘, 빈 Codex 새 대화, 터미널 없음).
import {labUi, firstView, lineAt, rootHeader, row, rowSeen} from './lab-common.mjs';

export default async ctx => {
 const c = await labUi(ctx);
 const view = await firstView(c, ctx, 'graph-lab');
 await c.installPointer({x: 365, y: 92});
 await ctx.begin();
 await ctx.say('i207-0101', async () => { const q = await lineAt(c, ctx, '# 설계한'); await c.move(q.x, q.y); }, {at: '이번 시간에는'});
 await ctx.say('i207-0102', async () => { const q = await rootHeader(c, ctx); await c.move(q.x, q.y); }, {at: '안쪽의'});
 await ctx.say('i207-0103', async () => { const q = await c.codexPoint(0.5, 0.45); await c.move(q.x, q.y); }, {at: '오른쪽 Codex'});
 await ctx.say('i207-0104', async () => {
  const d = await c.explorerRow('data', 1); await c.clickAt(d.x, d.y);
  await rowSeen(ctx, 'model', 2);
  const m = await row(c, 'model', 2); await c.move(m.x, m.y);
 }, {at: '데이터 폴더를'});
 await ctx.say('i207-0105', async () => { const q = await row(c, 'model', 2); await c.move(q.x, q.y); }, {at: '직접 만든 모델'});
 await ctx.say('i207-0106', async () => { const q = await row(c, 'AGENTS.md', 1); await c.move(q.x, q.y); }, {at: '에이전츠 파일'});
 return {segment: 'i207-01', view, next: 'i207-02: 새 터미널과 첫 실행', aiRequests: 0};
};
