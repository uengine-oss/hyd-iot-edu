// 실전 2회차 07편 구간 01: 목적 · 폴더와 웹판 · VS Code(원래 무엇 → 쓰임) · Codex와 바이브 코딩 · 안심 · AGENTS · data/app. 요청 · 파일 변경 없음.
// 실전반 첫 코딩 랩이라 VS Code 화면과 바이브 코딩을 여기서 푼다. 시작: p207-reset.mjs가 만든 화면.
import {labUi, atPhrase, firstView, lineAt, rootHeader, row} from './lab-common.mjs';

export default async ctx => {
 const c = await labUi(ctx);
 const view = await firstView(c, ctx, 'ontology-lab');
 const purpose = () => lineAt(c, ctx, '포털 지식 지도에서 본');
 await c.installPointer({x: 365, y: 92});
 await ctx.begin();
 await ctx.say('p207-0101', async () => { const q = await lineAt(c, ctx, '# 설비·부품·공급'); await c.move(q.x, q.y); }, {at: '이번 시간에는'});
 await ctx.say('p207-0102', async () => { const q = await purpose(); await c.move(q.x, q.y); }, {at: '제공된 설비와'});
 await ctx.say('p207-0103', async () => {
  const a = await rootHeader(c, ctx); await c.move(a.x, a.y);
 }, {at: '안쪽의'});
 await ctx.say('p207-0104', async () => {
  const m = await c.point('[role="menubar"]'); await c.move(m.x, m.y); await atPhrase(ctx, '왼쪽 탐색기, Explorer');
  const a = await row(c, 'README.md', 1); await c.move(a.x, a.y); await atPhrase(ctx, '가운데 편집기에');
  const b = await c.point('.tabs-container .tab.active .label-name'); await c.move(b.x - 24, b.y);
 }, {at: '브라우저에서'});
 await ctx.say('p207-0105', async () => { const q = await c.codexPoint(0.5, 0.45); await c.move(q.x, q.y); }, {at: '오른쪽 칸이'});
 await ctx.say('p207-0106', async () => {
  const a = await c.codexPoint(0.06, 0.86); await c.move(a.x, a.y); await atPhrase(ctx, '어떤 정보가 필요한지');
  const b = await purpose(); await c.move(b.x, b.y);
 }, {at: '코드는 몰라도'});
 await ctx.say('p207-0107', async () => { const q = await row(c, 'AGENTS.md', 1); await c.move(q.x, q.y); }, {at: '에이전츠 파일은'});
 await ctx.say('p207-0108', async () => {
  const d = await row(c, 'data', 1); await c.move(d.x, d.y); await atPhrase(ctx, '앱 폴더에는');
  const a = await row(c, 'app', 1); await c.move(a.x, a.y);
 }, {at: '데이터 폴더에는'});
 return {segment: 'p207-01', view, next: 'p207-02: 원자료와 첫 실행', aiRequests: 0};
};
