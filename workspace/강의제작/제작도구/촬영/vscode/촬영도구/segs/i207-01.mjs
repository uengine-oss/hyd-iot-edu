// 통합 2회차 07편 구간 01: 목적 · 폴더 · 제공 모델 · 자기 모델은 선택 · AGENTS. 요청 · 파일 변경 없음.
// 시작: i207-reset.mjs가 만든 화면(graph-lab, README.md 탭 하나, 폴더 접힘, 빈 Codex 새 대화, 터미널 없음).
import {vscode} from '../ui.mjs';

export default async ctx => {
 const c = await vscode(ctx);
 const view = await c.serial(() => ctx.p.evaluate(() => ({
  w: innerWidth, h: innerHeight, dpr: devicePixelRatio,
  title: document.querySelector('.tabs-container .tab.active .label-name')?.textContent,
  root: document.querySelector('.pane-header[aria-label^="Explorer Section:"]')?.innerText,
  rows: [...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].map(e => e.innerText.trim()),
 })));
 if (view.title !== 'README.md' || view.root?.toLowerCase() !== 'graph-lab' || view.w !== 1843 || Math.abs(view.dpr - 1.25) > 0.01 || view.rows.includes('output')) throw Error('첫 화면 조건 불일치: ' + JSON.stringify(view));
 const snap = await c.serial(() => ctx.p.snapshot());
 if (!snap.includes('Ask Codex anything.') || !snap.includes('6-Luna') || snap.includes('Restricted Mode')||snap.includes('Unable to send message')) throw Error('빈 Codex 새 대화 · 모델 · 폴더 신뢰를 먼저 확인합니다.');
 const lineAt = text => c.serial(() => ctx.p.evaluate(text => {
  const l = [...document.querySelectorAll('.editor-instance .view-lines .view-line')].find(e => e.textContent.replace(/ /g, ' ').startsWith(text));
  if (!l) throw Error('줄 없음: ' + text); const b = l.getBoundingClientRect(); return {x: b.x + 60, y: b.y + b.height / 2};
 }, text));
 const rootHeader = () => c.serial(() => ctx.p.evaluate(() => { const b = document.querySelector('.pane-header[aria-label^="Explorer Section:"] .title').getBoundingClientRect(); return {x: b.x + 20, y: b.y + b.height / 2}; }));
 await c.installPointer({x: 365, y: 92});
 await ctx.begin();
 await ctx.say('i207-0101', async () => { const q = await lineAt('# 설계한'); await c.move(q.x, q.y); }, {at: '이번 시간에는'});
 await ctx.say('i207-0102', async () => { const q = await rootHeader(); await c.move(q.x, q.y); }, {at: '안쪽의'});
 await ctx.say('i207-0103', async () => { const q = await c.codexPoint(0.5, 0.45); await c.move(q.x, q.y); }, {at: '오른쪽 Codex'});
 await ctx.say('i207-0104', async () => {
  const d = await c.explorerRow('data', 1); await c.clickAt(d.x, d.y);
  await ctx.waitFor(() => [...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].some(e => e.getAttribute('aria-level') === '2' && e.innerText.trim() === 'model'));
  const m = await c.explorerRow('model', 2); await c.move(m.x - 34, m.y);
 }, {at: '데이터 폴더를'});
 await ctx.say('i207-0105', async () => { const q = await c.explorerRow('model', 2); await c.move(q.x - 34, q.y); }, {at: '직접 만든 모델'});
 await ctx.say('i207-0106', async () => { const q = await c.explorerRow('AGENTS.md', 1); await c.move(q.x - 34, q.y); }, {at: '에이전츠 파일'});
 return {segment: 'i207-01', next: 'i207-02: 새 터미널과 첫 실행', aiRequests: 0};
};
