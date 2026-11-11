// 실전 2회차 09편 구간 02: data 펼침 → 매뉴얼 · 결정표 · 후보 · 사건 메모 · 확인 사례 → 매뉴얼 금지와 제한(86~88행) → run.py → 새 터미널 → 첫 실행. AI 요청 없음.
// 시작: p209-01 끝(README.md 탭, 폴더 접힘, 빈 Codex). output/ 없음, 터미널 없음.
import {labUi, atPhrase, afterResult, termLine, termWait, lineAt, row, rowSeen, exists, inView, newTerminal, waitRun, scrollEditorTo} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.p209.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에
const L87 = '- 원격 조치(SOP-COOL-11~13)는', L88 = '- 팬 100 % 연속 운전이 24시간을';

export default async ctx => {
 const c = await labUi(ctx);
 if (await exists(ctx, LAB + '/output')) throw Error('output/이 이미 있음 — p209-reset.mjs로 지우고 시작');
 if (await c.serial(() => ctx.p.evaluate(() => !!document.querySelector('.terminal-wrapper')?.checkVisibility()))) throw Error('터미널이 이미 열려 있음');
 await c.installPointer(ctx.prev ? null : {x: 120, y: 200});
 await ctx.begin();
 await ctx.say('p209-0201', async () => {
  const d = await c.explorerRow('data', 1); await c.clickAt(d.x, d.y);
  await rowSeen(ctx, 'hm8_manual.md', 2);
  const m = await row(c, 'hm8_manual.md', 2); await c.move(m.x, m.y);
 }, {at: '데이터 폴더를'});
 await ctx.say('p209-0202', async () => {
  const a = await row(c, 'decision_table_export.txt', 2); await c.move(a.x, a.y); await atPhrase(ctx, '후보 목록 파일에');
  const b = await row(c, 'targets.csv', 2); await c.move(b.x, b.y); await atPhrase(ctx, '작업 기준 파일에');
  const w = await row(c, 'work_standard.md', 2); await c.move(w.x, w.y);
 }, {at: '판단 시스템 결정표는'});
 await ctx.say('p209-0203', async () => {
  const a = await row(c, 'incident_hyd02_1027.md', 2); await c.move(a.x, a.y); await atPhrase(ctx, '확인 사례가');
  const b = await row(c, 'check_cases.csv', 2); await c.move(b.x, b.y);
 }, {at: '그래서 운전원이'});
 await ctx.say('p209-0204', async () => { const q = await c.explorerRow('hm8_manual.md', 2); await c.clickAt(q.x, q.y); await c.key('Enter'); }, {at: '매뉴얼 원문을'});
 await ctx.waitFor(() => document.querySelector('.tabs-container .tab.active .label-name')?.textContent === 'hm8_manual.md');
 await afterResult(ctx);
 // 앞 take가 이 파일을 내려 둔 채 닫았으면 VS Code가 그 스크롤 자리로 다시 연다 — 첫 줄(제목)이 편집기 안에 보이지 않으면 멈춘다
 inView(await lineAt(c, ctx, '# 유압 파워유닛 쿨러 팬 정비 매뉴얼'));

 await ctx.say('p209-0205', async () => {
  await scrollEditorTo(c, ctx, '## HM-8.8', 520);
  const h = inView(await lineAt(c, ctx, '## HM-8.8')); await c.move(h.x, h.y); await atPhrase(ctx, '운전 모드가');
  const a = inView(await lineAt(c, ctx, L87)); await c.move(a.x, a.y); await atPhrase(ctx, '바로 아래에는');
  const b = inView(await lineAt(c, ctx, L88)); await c.move(b.x, b.y);
 }, {at: '아래쪽 금지와 제한'});
 await ctx.say('p209-0206', async () => {
  const a = inView(await lineAt(c, ctx, L87)); await c.move(a.x, a.y); await atPhrase(ctx, '아래 줄은');
  const b = inView(await lineAt(c, ctx, L88)); await c.move(b.x, b.y);
 }, {at: '같은 절에 있어도'});
 await ctx.say('p209-0207', async () => { const q = await row(c, 'run.py', 1); await c.move(q.x, q.y); }, {at: '맨 아래 run.py', gap: 2300});   // 화제가 바뀌는 큐(영상 V-14 구간 전환 쉼, 2회차부터 2.3초)
 await ctx.say('p209-0208', () => newTerminal(c, ctx), {at: '왼쪽 위 줄 세 개 메뉴에서'});
 await termWait(ctx, 'condition-table-lab>');
 await afterResult(ctx);
 await ctx.say('p209-0209', async () => { const q = await termLine(c, ctx, 'condition-table-lab>'); await c.move(q.x, q.y); }, {at: '글자 앞 경로가'});
 // 학생 명령 · 웹판 덧붙임 · Enter는 말하는 문장마다 큐를 나눈다(본보기 i206-0211~0213). 터미널 초점 확인은 공용 lab-common이 맡는다.
 await ctx.say('p209-0210', () => c.typeKeys('python run.py'), {at: 'python run.py를'});
 await ctx.say('p209-0213', () => c.typeKeys(' --no-open'), {at: '빼기 두 개와 no-open을'});
 await ctx.say('p209-0214', () => c.key('Enter'), {at: 'Enter를 눌러'});
 await waitRun(ctx, LAB);
 await ctx.say('p209-0211', async () => { const q = await termLine(c, ctx, '후보 4'); await c.move(q.x, q.y); }, {at: '터미널에'});
 await ctx.say('p209-0212', async () => { const q = await termLine(c, ctx, '결과: output/result.html'); await c.move(q.x, q.y); }, {at: '여러분 PC에서는'});
 return {segment: 'p209-02', next: 'p209-03: 결과 화면 공간', aiRequests: 0};
};
