// 실전 2회차 07편 구간 02: data 펼침 → 모델 · 공급 자료 넷 · 구매 기준서 · 현장 메모 → 견적 조건(2 · 3 · 5행) → run.py · 터미널 풀이 → 새 터미널 → 첫 실행. AI 요청 없음.
// 시작: p207-01 끝(README.md 탭, 폴더 접힘, 빈 Codex). output/ 없음, 터미널 없음.
import {labUi, atPhrase, afterResult, termLine, termWait, lineAt, row, rowSeen, exists, newTerminal, waitRun} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.p207.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에

export default async ctx => {
 const c = await labUi(ctx);
 if (await exists(ctx, LAB + '/output')) throw Error('output/이 이미 있음 — p207-reset.mjs로 지우고 시작');
 if (await c.serial(() => ctx.p.evaluate(() => !!document.querySelector('.terminal-wrapper')?.checkVisibility()))) throw Error('터미널이 이미 열려 있음');
 await c.installPointer(ctx.prev ? null : {x: 120, y: 200});
 await ctx.begin();
 await ctx.say('p207-0201', async () => {
  const d = await c.explorerRow('data', 1); await c.clickAt(d.x, d.y);
  await rowSeen(ctx, 'model', 2);
  const m = await row(c, 'model', 2); await c.move(m.x, m.y);
 }, {at: '데이터 폴더를'});
 await ctx.say('p207-0202', async () => {
  for (const [name, at] of [['approved_suppliers.csv', '승인 공급사 목록'], ['supply_terms.csv', '공급사별 견적'], ['receipts.csv', '입고 기록'], ['part_aliases.csv', '품번 목록']]) { await atPhrase(ctx, at); const q = await row(c, name, 2); await c.move(q.x, q.y); }
 }, {at: '승인 공급사 목록'});
 await ctx.say('p207-0203', async () => {
  const a = await row(c, 'purchasing_standard_pr07.md', 2); await c.move(a.x, a.y); await atPhrase(ctx, '현장 메모에는');
  const b = await row(c, 'field_notes.md', 2); await c.move(b.x, b.y);
 }, {at: '구매 기준서에는'});
 await ctx.say('p207-0204', async () => { const q = await c.explorerRow('supply_terms.csv', 2); await c.clickAt(q.x, q.y); await c.key('Enter'); }, {at: '견적 조건 파일부터'});
 await ctx.waitFor(() => document.querySelector('.tabs-container .tab.active .label-name')?.textContent === 'supply_terms.csv');
 await afterResult(ctx);
 await ctx.say('p207-0205', async () => {
  const h = await lineAt(c, ctx, '품번,공급사,'); await c.move(h.x, h.y); await atPhrase(ctx, '그 아래 한 줄이');
  const a = await lineAt(c, ctx, 'P-PMP-SEAL,A정밀 (저가)'); await c.move(a.x, a.y); await atPhrase(ctx, '같은 공급사가');
  const b = await lineAt(c, ctx, 'P-PMP-SEAL,B-OEM (순정),HI-SK-45A,예,55'); await c.move(b.x, b.y); await atPhrase(ctx, '두 번 낸');
  const d = await lineAt(c, ctx, 'P-PMP-SEAL,B-OEM (순정),HI-SK-45A,예,58'); await c.move(d.x, d.y);
 }, {at: '맨 윗줄은'});
 await ctx.say('p207-0206', async () => { const q = await row(c, 'run.py', 1); await c.move(q.x, q.y); }, {at: '맨 아래 run.py', gap: 2300});   // 화제가 바뀌는 큐(영상 V-14 구간 전환 쉼, 2회차부터 2.3초)
 await ctx.say('p207-0207', () => newTerminal(c, ctx), {at: '왼쪽 위 줄 세 개 메뉴에서'});
 await termWait(ctx, 'ontology-lab>');
 await afterResult(ctx);
 await ctx.say('p207-0208', async () => {
  const t = await c.serial(() => ctx.p.evaluate(() => { const e = [...document.querySelectorAll('.terminal-tabs-entry, .single-terminal-tab, .terminal-tab')].filter(x => x.innerText.trim() === 'cmd' && x.getBoundingClientRect().width > 0); if (e.length !== 1) throw Error('터미널 이름표 cmd가 ' + e.length + '개'); const b = e[0].getBoundingClientRect(); return {x: b.x + b.width / 2, y: b.y + b.height / 2}; }));
  await c.move(t.x, t.y);
 }, {at: 'cmd라고'});
 await ctx.say('p207-0212', async () => { const q = await termLine(c, ctx, 'ontology-lab>'); await c.move(q.x, q.y); }, {at: '깜빡이는 커서'});
 // 학생 명령 · 웹판 덧붙임 · Enter는 말하는 문장마다 큐를 나눈다(본보기 i206-0211~0213). 터미널 초점 확인은 공용 lab-common이 맡는다.
 await ctx.say('p207-0209', () => c.typeKeys('python run.py'), {at: 'python run.py를'});
 await ctx.say('p207-0213', () => c.typeKeys(' --no-open'), {at: '빼기 두 개와 no-open을'});
 await ctx.say('p207-0214', () => c.key('Enter'), {at: 'Enter를 눌러'});
 await waitRun(ctx, LAB);
 await ctx.say('p207-0210', async () => { const q = await termLine(c, ctx, '관계 305'); await c.move(q.x, q.y); }, {at: '터미널에'});
 await ctx.say('p207-0211', async () => { const q = await termLine(c, ctx, '결과: output/result.html'); await c.move(q.x, q.y); }, {at: '여러분 PC에서는'});
 return {segment: 'p207-02', next: 'p207-03: 결과 화면 공간', aiRequests: 0};
};
