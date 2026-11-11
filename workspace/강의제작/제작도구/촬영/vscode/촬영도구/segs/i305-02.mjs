// 통합 3회차 05편 구간 02: data 펼침 → 모델 · 매뉴얼 두 판 · 결정표 · 사건 메모 → 매뉴얼 원문(47 · 49 · 45행) → run.py → 새 터미널 → 첫 실행. AI 요청 없음.
// 시작: i305-01 끝(README.md 탭, 폴더 접힘, 빈 Codex). output/ 없음, 터미널 없음.
import {labUi, atPhrase, afterResult, termLine, termWait, lineAt, row, rowSeen, exists, inView, newTerminal, waitRun, scrollEditorTo} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.i305.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에
const L49 = '2. 팬 속도를 100 %로 올린다. 100 %';

export default async ctx => {
 const c = await labUi(ctx);
 if (await exists(ctx, LAB + '/output')) throw Error('output/이 이미 있음 — i305-reset.mjs로 지우고 시작');
 if (await c.serial(() => ctx.p.evaluate(() => !!document.querySelector('.terminal-wrapper')?.checkVisibility()))) throw Error('터미널이 이미 열려 있음');
 await c.installPointer(ctx.prev ? null : {x: 120, y: 200});
 await ctx.begin();
 await ctx.say('i305-0201', async () => {
  const d = await c.explorerRow('data', 1); await c.clickAt(d.x, d.y);
  await rowSeen(ctx, 'model', 2);
  const m = await row(c, 'model', 2); await c.move(m.x, m.y);
 }, {at: '데이터 폴더를'});
 await ctx.say('i305-0202', async () => {
  const a = await row(c, 'hm8_manual.md', 2); await c.move(a.x, a.y); await atPhrase(ctx, '예전 판');
  const b = await row(c, 'hm8_manual_v1_0.md', 2); await c.move(b.x, b.y);
 }, {at: '근거가 될'});
 await ctx.say('i305-0203', async () => {
  const a = await row(c, 'decision_table_export.txt', 2); await c.move(a.x, a.y); await atPhrase(ctx, '사건 메모는');
  const b = await row(c, 'incident_hyd02_1027.md', 2); await c.move(b.x, b.y);
 }, {at: '판단 시스템 결정표는'});
 await ctx.say('i305-0204', async () => { const q = await row(c, 'data', 1); await c.move(q.x, q.y); }, {at: '이 자료들은'});
 await ctx.say('i305-0205', async () => { const q = await c.explorerRow('hm8_manual.md', 2); await c.clickAt(q.x, q.y); await c.key('Enter'); }, {at: '매뉴얼 원문을'});
 await ctx.waitFor(() => document.querySelector('.tabs-container .tab.active .label-name')?.textContent === 'hm8_manual.md');
 await afterResult(ctx);
 // 앞 take가 이 파일을 내려 둔 채 닫았으면 VS Code가 그 스크롤 자리로 다시 연다 — 첫 줄(제목)이 편집기 안에 보이지 않으면 멈춘다
 inView(await lineAt(c, ctx, '# 유압 파워유닛 쿨러 팬 정비 매뉴얼'));

 await ctx.say('i305-0206', async () => {
  await scrollEditorTo(c, ctx, '### SOP-COOL-11');
  const a = inView(await lineAt(c, ctx, '### SOP-COOL-11')); await c.move(a.x, a.y); await atPhrase(ctx, '팬을 끝까지');
  const b = inView(await lineAt(c, ctx, L49)); await c.move(b.x, b.y);
 }, {at: '조금 내려'});
 await ctx.say('i305-0207', async () => { const q = inView(await lineAt(c, ctx, '원격 조치는 PLC')); await c.move(q.x, q.y); }, {at: '바로 위 문단'});
 await ctx.say('i305-0208', async () => { const q = inView(await lineAt(c, ctx, L49)); await c.move(q.x, q.y); }, {at: '이렇게 해야'});
 await ctx.say('i305-0209', async () => { const q = await row(c, 'run.py', 1); await c.move(q.x, q.y); }, {at: '맨 아래 run.py', gap: 2300});   // 화제가 바뀌는 큐(영상 V-14 구간 전환 쉼, 2회차부터 2.3초)
 await ctx.say('i305-0210', () => newTerminal(c, ctx), {at: '왼쪽 위 줄 세 개 메뉴에서'});
 await termWait(ctx, 'action-criteria-lab>');
 await afterResult(ctx);
 await ctx.say('i305-0211', async () => { const q = await termLine(c, ctx, 'action-criteria-lab>'); await c.move(q.x, q.y); }, {at: '글자 앞 경로가'});
 // 학생 명령 · 웹판 덧붙임 · Enter는 말하는 문장마다 큐를 나눈다(본보기 i206-0211~0213). 터미널 초점 확인은 공용 lab-common이 맡는다.
 await ctx.say('i305-0212', () => c.typeKeys('python run.py'), {at: 'python run.py를'});
 await ctx.say('i305-0215', () => c.typeKeys(' --no-open'), {at: '빼기 두 개와 no-open을'});
 await ctx.say('i305-0216', () => c.key('Enter'), {at: 'Enter를 눌러'});
 await waitRun(ctx, LAB);
 await ctx.say('i305-0213', async () => { const q = await termLine(c, ctx, '냉각 계통 SOP 7'); await c.move(q.x, q.y); }, {at: '터미널에'});
 await ctx.say('i305-0214', async () => { const q = await termLine(c, ctx, '결과: output/result.html'); await c.move(q.x, q.y); }, {at: '여러분 PC에서는'});
 return {segment: 'i305-02', next: 'i305-03: 결과 화면 공간', aiRequests: 0};
};
