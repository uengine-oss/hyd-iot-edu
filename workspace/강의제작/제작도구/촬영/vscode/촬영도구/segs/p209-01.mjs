// 실전 2회차 09편 구간 01: 목적 · 폴더 · Codex(되짚기) · AGENTS(정할 지점) · data/app. 요청 · 파일 변경 없음.
// 시작: p209-reset.mjs가 만든 화면(condition-table-lab, README.md 탭 하나, 폴더 접힘, 빈 Codex 새 대화, 터미널 없음).
import {labUi, atPhrase, firstView, lineAt, rootHeader, row} from './lab-common.mjs';

export default async ctx => {
 const c = await labUi(ctx);
 const view = await firstView(c, ctx, 'condition-table-lab');
 await c.installPointer({x: 365, y: 92});
 await ctx.begin();
 await ctx.say('p209-0101', async () => { const q = await lineAt(c, ctx, '# 작업 기준의'); await c.move(q.x, q.y); }, {at: '이번 시간에는'});
 await ctx.say('p209-0102', async () => { const q = await lineAt(c, ctx, '포털 판단 규칙'); await c.move(q.x, q.y); }, {at: '만든 표는'});
 await ctx.say('p209-0103', async () => { const q = await rootHeader(c, ctx); await c.move(q.x, q.y); }, {at: '안쪽의'});
 await ctx.say('p209-0104', async () => {
  const h = await rootHeader(c, ctx); await c.move(h.x, h.y); await atPhrase(ctx, '오른쪽 Codex');
  const q = await c.codexPoint(0.5, 0.45); await c.move(q.x, q.y);
 }, {at: '왼쪽 탐색기'});
 await ctx.say('p209-0105', async () => { const q = await row(c, 'AGENTS.md', 1); await c.move(q.x, q.y); }, {at: '에이전츠 파일에는'});
 await ctx.say('p209-0106', async () => {
  const d = await row(c, 'data', 1); await c.move(d.x, d.y); await atPhrase(ctx, '앱 폴더에는');
  const a = await row(c, 'app', 1); await c.move(a.x, a.y);
 }, {at: '데이터 폴더에는'});
 return {segment: 'p209-01', view, next: 'p209-02: 원자료와 첫 실행', aiRequests: 0};
};
