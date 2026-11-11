// 실전 2회차 08편 구간 01: 목적 · 폴더 · Codex(되짚기) · AGENTS(랩 DB) · data 펼침과 제공 모델 · 자기 모델은 선택. 요청 · 파일 변경 없음.
// 시작: p208-reset.mjs가 만든 화면(graph-lab, README.md 탭 하나, 폴더 접힘, 빈 Codex 새 대화, 터미널 없음, 랩 DB 없음).
import {labUi, atPhrase, firstView, lineAt, rootHeader, row, rowSeen} from './lab-common.mjs';

export default async ctx => {
 const c = await labUi(ctx);
 const view = await firstView(c, ctx, 'graph-lab');
 await c.installPointer({x: 365, y: 92});
 await ctx.begin();
 await ctx.say('p208-0101', async () => { const q = await lineAt(c, ctx, '# 부품의 사용'); await c.move(q.x, q.y); }, {at: '이번 시간에는'});
 await ctx.say('p208-0102', async () => { const q = await lineAt(c, ctx, '설비·부품·공급 모델을'); await c.move(q.x, q.y); }, {at: '이 답은'});
 await ctx.say('p208-0103', async () => { const q = await rootHeader(c, ctx); await c.move(q.x, q.y); }, {at: '안쪽의'});
 await ctx.say('p208-0104', async () => {   // 탐색기 → 편집기 → Codex를 말 차례대로
  const a = await rootHeader(c, ctx); await c.move(a.x, a.y); await atPhrase(ctx, '가운데 편집기에');
  const b = await lineAt(c, ctx, '# 부품의 사용'); await c.move(b.x, b.y); await atPhrase(ctx, '오른쪽 Codex에');
  const d = await c.codexPoint(0.5, 0.45); await c.move(d.x, d.y);
 }, {at: '왼쪽 탐색기에서'});
 await ctx.say('p208-0105', async () => { const q = await row(c, 'AGENTS.md', 1); await c.move(q.x, q.y); }, {at: '에이전츠 파일에는'});
 await ctx.say('p208-0106', async () => {
  const d = await c.explorerRow('data', 1); await c.clickAt(d.x, d.y);
  await rowSeen(ctx, 'model', 2);
  const m = await row(c, 'model', 2); await c.move(m.x, m.y);
 }, {at: '데이터 폴더를'});
 await ctx.say('p208-0107', async () => { const q = await row(c, 'model', 2); await c.move(q.x, q.y); }, {at: '온톨로지를 설계하며'});
 return {segment: 'p208-01', view, next: 'p208-02: 새 터미널과 첫 실행', aiRequests: 0};
};
