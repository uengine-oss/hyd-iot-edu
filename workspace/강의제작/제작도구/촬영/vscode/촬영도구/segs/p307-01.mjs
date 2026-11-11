// 실전 3회차 07편 구간 01: 목적 · 폴더 · Codex(되짚기) · AGENTS · data/app. 요청 · 파일 변경 없음.
// 시작: p307-reset.mjs가 만든 화면(condition-extract-lab, README.md 탭 하나, 폴더 접힘, 빈 Codex 새 대화, 터미널 없음).
import {labUi, atPhrase, firstView, lineAt, rootHeader, row} from './lab-common.mjs';

export default async ctx => {
 const c = await labUi(ctx);
 const view = await firstView(c, ctx, 'condition-extract-lab');
 await c.installPointer({x: 365, y: 92});
 await ctx.begin();
 await ctx.say('p307-0101', async () => { const q = await lineAt(c, ctx, '# 문서에서'); await c.move(q.x, q.y); }, {at: '이번 시간에는'});
 await ctx.say('p307-0102', async () => { const q = await lineAt(c, ctx, '포털에서 본'); await c.move(q.x, q.y); }, {at: '문서를 어떤 단위로'});
 await ctx.say('p307-0103', async () => { const q = await rootHeader(c, ctx); await c.move(q.x, q.y); }, {at: '안쪽의'});
 await ctx.say('p307-0104', async () => {   // 탐색기 → 편집기 → Codex를 말 차례대로
  const a = await rootHeader(c, ctx); await c.move(a.x, a.y); await atPhrase(ctx, '가운데 편집기에서');
  const b = await lineAt(c, ctx, '# 문서에서'); await c.move(b.x, b.y); await atPhrase(ctx, '오른쪽 Codex에게');
  const d = await c.codexPoint(0.5, 0.45); await c.move(d.x, d.y);
 }, {at: '왼쪽 탐색기에서'});
 await ctx.say('p307-0105', async () => { const q = await row(c, 'AGENTS.md', 1); await c.move(q.x, q.y); }, {at: '에이전츠 파일'});
 await ctx.say('p307-0106', async () => {
  const d = await row(c, 'data', 1); await c.move(d.x, d.y); await atPhrase(ctx, '앱 폴더에는');
  const a = await row(c, 'app', 1); await c.move(a.x, a.y);
 }, {at: '데이터 폴더에는'});
 return {segment: 'p307-01', view, next: 'p307-02: 원자료와 첫 실행', aiRequests: 0};
};
