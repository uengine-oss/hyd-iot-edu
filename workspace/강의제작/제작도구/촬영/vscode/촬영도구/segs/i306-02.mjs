// 통합 3회차 06편 구간 02: data 펼침 → criteria(제공 조건표 · SOP 구조, 자기 결과는 선택) → 원천 기록 넷 · 수집 설명 → 경보 기록(2 · 3행) → metrics → run.py → 새 터미널 → 첫 실행. AI 요청 없음.
// 시작: i306-01 끝(README.md 탭, 폴더 접힘, 빈 Codex). output/ 없음, 터미널 없음.
import {labUi, atPhrase, afterResult, termLine, termWait, lineAt, row, rowSeen, exists, newTerminal, waitRun} from './lab-common.mjs';

// 편집기에서 글이 text로 시작하는 줄의 글 끝(누르지 않고 짚기만 한다 — ui.mjs lineEnd는 누른다)
const lineTail = (c, ctx, text) => c.serial(() => ctx.p.evaluate(text => {
 const l = [...document.querySelectorAll('.editor-instance .view-lines .view-line')].find(e => e.textContent.replace(/ /g, ' ').startsWith(text));
 if (!l) throw Error('줄 없음: ' + text);
 const r = document.createRange(); r.selectNodeContents(l); const b = [...r.getClientRects()].pop();
 return {x: b.right - 8, y: b.y + b.height / 2};
}, text));

const LAB = (await import('./lab-common.mjs')).LABS.i306.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에

export default async ctx => {
 const c = await labUi(ctx);
 if (await exists(ctx, LAB + '/output')) throw Error('output/이 이미 있음 — i306-reset.mjs로 지우고 시작');
 if (await c.serial(() => ctx.p.evaluate(() => !!document.querySelector('.terminal-wrapper')?.checkVisibility()))) throw Error('터미널이 이미 열려 있음');
 await c.installPointer(ctx.prev ? null : {x: 120, y: 200});
 await ctx.begin();
 await ctx.say('i306-0201', async () => {
  const d = await c.explorerRow('data', 1); await c.clickAt(d.x, d.y);
  await rowSeen(ctx, 'criteria', 2);
  const m = await row(c, 'criteria', 2); await c.move(m.x, m.y);
 }, {at: '데이터 폴더를 펼치면'});
 await ctx.say('i306-0218', async () => {
  const k = await c.explorerRow('criteria', 2); await c.clickAt(k.x, k.y);
  await rowSeen(ctx, 'sop.json', 3);
  const a = await row(c, 'condition_table.csv', 3); await c.move(a.x, a.y); await atPhrase(ctx, 'SOP 구조가');
  const b = await row(c, 'sop.json', 3); await c.move(b.x, b.y);
 }, {at: '기준 폴더를 열어 보면'});
 await ctx.say('i306-0202', async () => { const q = await row(c, 'criteria', 2); await c.move(q.x, q.y); }, {at: '직접 만든 표'});
 await ctx.say('i306-0203', async () => {
  for (const [name, at] of [['alarms.csv', '경보 기록'], ['fan_counter.csv', '팬 운전 카운터'], ['forecasts.csv', '예측 결과'], ['plc_status.csv', 'PLC에서']]) { await atPhrase(ctx, at); const q = await row(c, name, 2); await c.move(q.x, q.y); }
 }, {at: '경보 기록,'});
 await ctx.say('i306-0204', async () => { const q = await row(c, 'collection_notes.md', 2); await c.move(q.x, q.y); }, {at: '수집 설명에는'});
 await ctx.say('i306-0205', async () => { const q = await c.explorerRow('alarms.csv', 2); await c.clickAt(q.x, q.y); await c.key('Enter'); }, {at: '경보 기록을'});
 await ctx.waitFor(() => document.querySelector('.tabs-container .tab.active .label-name')?.textContent === 'alarms.csv');
 await afterResult(ctx);
 await ctx.say('i306-0206', async () => {
  const a = await lineAt(c, ctx, 'ALT-hyd03-0280-beaf,HYD-03,COOLER_DEGRADATION,RAISE'); await c.move(a.x, a.y); await atPhrase(ctx, '풀리면');
  const b = await lineAt(c, ctx, 'ALT-hyd03-0280-beaf,HYD-03,COOLER_DEGRADATION,CLEAR'); await c.move(b.x, b.y); await atPhrase(ctx, '판정 요청 시각은');
  const e = await lineTail(c, ctx, 'ALT-hyd03-0280-beaf,HYD-03,COOLER_DEGRADATION,RAISE'); await c.move(e.x, e.y);   // 끝 칸 판정_요청_시각
 }, {at: '경보 하나가'});
 await ctx.say('i306-0214', async () => { const q = await lineTail(c, ctx, 'ALT-hyd03-0280-beaf,HYD-03,COOLER_DEGRADATION,RAISE'); await c.move(q.x, q.y); }, {at: '시각 끝의 Z는'});
 await ctx.say('i306-0207', async () => {
  const k = await c.explorerRow('metrics', 2); await c.clickAt(k.x, k.y);
  await rowSeen(ctx, 'metric_definitions.md', 3);
  const a = await row(c, 'metric_definitions.md', 3); await c.move(a.x, a.y); await atPhrase(ctx, '그 산식에 넣을');
  const b = await row(c, 'business_values.json', 3); await c.move(b.x, b.y);
 }, {at: '비교 지표 폴더를 펼치면'});
 await ctx.say('i306-0215', async () => { const q = await row(c, 'contract.md', 2); await c.move(q.x, q.y); }, {at: '계약 파일에는'});
 await ctx.say('i306-0208', async () => { const q = await row(c, 'run.py', 1); await c.move(q.x, q.y); }, {at: '맨 아래 run.py', gap: 2300});   // 화제가 바뀌는 큐(영상 V-14 구간 전환 쉼, 2회차부터 2.3초)
 await ctx.say('i306-0209', () => newTerminal(c, ctx), {at: '왼쪽 위 줄 세 개 메뉴의'});
 await termWait(ctx, 'judgement-lab>');
 await afterResult(ctx);
 await ctx.say('i306-0210', async () => { const q = await termLine(c, ctx, 'judgement-lab>'); await c.move(q.x, q.y); }, {at: '글자 앞 경로가'});
 // 학생 명령 · 웹판 덧붙임 · Enter는 말하는 문장마다 큐를 나눈다(본보기 i206-0211~0213). 터미널 초점 확인은 공용 lab-common이 맡는다.
 await ctx.say('i306-0211', () => c.typeKeys('python run.py'), {at: 'python run.py를'});
 await ctx.say('i306-0216', () => c.typeKeys(' --no-open'), {at: '빼기 두 개와 no-open을'});
 await ctx.say('i306-0217', () => c.key('Enter'), {at: 'Enter를 눌러'});
 await waitRun(ctx, LAB);
 await ctx.say('i306-0212', async () => { const q = await termLine(c, ctx, '60행'); await c.move(q.x, q.y); }, {at: '터미널에'});
 await ctx.say('i306-0213', async () => { const q = await termLine(c, ctx, '결과: output/result.html'); await c.move(q.x, q.y); }, {at: '여러분 PC에서는'});
 return {segment: 'i306-02', next: 'i306-03: 결과 화면 공간', aiRequests: 0};
};
