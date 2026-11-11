// 통합 2회차 06편 구간 01: 목적 · 폴더 · 웹 메뉴 · 탐색기 · 편집기 · Codex · AGENTS · data/app. 요청 · 파일 변경 없음.
// 시작: i206-reset.mjs가 만든 화면(ontology-lab, README.md 탭 하나, 폴더 접힘, 빈 Codex 새 대화, 터미널 없음).
import {labUi, atPhrase, firstView, lineAt, rootHeader, row} from './lab-common.mjs';

export default async ctx => {
 const c = await labUi(ctx);
 const view = await firstView(c, ctx, 'ontology-lab');
 await c.installPointer({x: 365, y: 92});
 await ctx.begin();
 await ctx.say('i206-0101', async () => { const q = await lineAt(c, ctx, '# 현장'); await c.move(q.x, q.y); }, {at: '이번 시간에는'});
 await ctx.say('i206-0102', async () => { const q = await lineAt(c, ctx, '포털 지식 지도에서'); await c.move(q.x, q.y); }, {at: '포털의 지식 지도에서는'});
 await ctx.say('i206-0103', async () => { const q = await rootHeader(c, ctx); await c.move(q.x, q.y); }, {at: '안쪽의'});
 await ctx.say('i206-0104', async () => { const q = await c.point('.menubar-menu-button', 'Application Menu'); await c.move(q.x, q.y); }, {at: '브라우저에서 여는'});
 await ctx.say('i206-0105', async () => { const q = await rootHeader(c, ctx); await c.move(q.x, q.y); }, {at: '맨 위의 폴더 이름이'});
 await ctx.say('i206-0106', async () => {
  const q = await c.point('.tabs-container .tab.active .label-name', 'README.md'); await c.move(q.x, q.y); await atPhrase(ctx, '지금 연 리드미에는');
  const l = await lineAt(c, ctx, '# 현장'); await c.move(l.x, l.y);
 }, {at: '가운데 편집기는'});
 await ctx.say('i206-0110', async () => { const q = await c.codexPoint(0.5, 0.45); await c.move(q.x, q.y); }, {at: '오른쪽 Codex는'});
 await ctx.say('i206-0111', async () => {
  const q = await c.codexPoint(0.04, 0.86); await c.move(q.x, q.y); await atPhrase(ctx, '어떤 답이 필요한지');
  const l = await lineAt(c, ctx, '포털 지식 지도에서'); await c.move(l.x, l.y);
 }, {at: '코드를 쓰는 일은'});
 await ctx.say('i206-0113', async () => { const q = await row(c, 'AGENTS.md', 1); await c.move(q.x, q.y); }, {at: '에이전츠 파일은'});
 await ctx.say('i206-0112', async () => {
  const d = await row(c, 'data', 1); await c.move(d.x, d.y); await atPhrase(ctx, '앱 폴더에는');
  const a = await row(c, 'app', 1); await c.move(a.x, a.y);
 }, {at: '데이터 폴더에는'});
 return {segment: 'i206-01', view, next: 'i206-02: 원자료와 첫 실행', aiRequests: 0};
};
