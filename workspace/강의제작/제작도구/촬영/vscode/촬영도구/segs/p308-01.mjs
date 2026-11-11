// 실전 3회차 08편 구간 01: 목적 · 폴더 · Codex(되짚기) · AGENTS · data/app. 요청 · 파일 변경 없음.
// 시작: p308-reset.mjs가 만든 화면(work-card-lab, README.md 탭 하나, 폴더 접힘, 빈 Codex 새 대화, 터미널 없음).
import {labUi, atPhrase, firstView, lineAt, rootHeader, row} from './lab-common.mjs';

export default async ctx => {
 const c = await labUi(ctx);
 const view = await firstView(c, ctx, 'work-card-lab');
 await c.installPointer({x: 365, y: 92});
 await ctx.begin();
 await ctx.say('p308-0101', async () => { const q = await lineAt(c, ctx, '# 검토 지식으로'); await c.move(q.x, q.y); }, {at: '이번 시간에는'});
 await ctx.say('p308-0102', async () => { const q = await lineAt(c, ctx, '검토해 승인한'); await c.move(q.x, q.y); }, {at: '작업 확인 카드는'});
 await ctx.say('p308-0103', async () => { const q = await rootHeader(c, ctx); await c.move(q.x, q.y); }, {at: '안쪽의'});
 await ctx.say('p308-0104', async () => { const q = await c.codexPoint(0.5, 0.45); await c.move(q.x, q.y); }, {at: '화면 구성과'});
 await ctx.say('p308-0105', async () => { const q = await row(c, 'AGENTS.md', 1); await c.move(q.x, q.y); }, {at: '에이전츠 파일에는'});
 await ctx.say('p308-0106', async () => {
  const d = await row(c, 'data', 1); await c.move(d.x, d.y); await atPhrase(ctx, '앱 폴더에는');
  const a = await row(c, 'app', 1); await c.move(a.x, a.y);
 }, {at: '데이터 폴더에는'});
 return {segment: 'p308-01', view, next: 'p308-02: 원자료와 첫 실행', aiRequests: 0};
};
