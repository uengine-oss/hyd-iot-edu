// 통합 2회차 06-1편 구간 03(첫 페이지 — 웹 VS Code): VS Code 화면의 네 군데 · 새 터미널 · 랩 폴더(app · data · AGENTS.md · run.py) · 현장 메모 · 설비 대장(CSV와 행).
// 시작: wv-reset.mjs가 만든 화면(ontology-lab 폴더가 열리고 신뢰됨, 탐색기 접힘, 편집기 없음, 터미널 없음, 빈 Codex 새 대화, output/ 없음). 2장(사용자 녹화) 뒤라 앞 take를 주지 않는다.
// 끝: 탐색기에 data가 펴지고 app은 접힘, 편집기에 field_notes.md · equipment.csv(앞), 터미널이 열려 프롬프트만 있음, output/ 없음. 다음은 wv-04a(첫 실행 명령).
// 화살표 자리: 탐색기 행은 이름 왼쪽 접기 화살표 쪽(이름 위에 두면 경로 풍선이 아래 행을 가린다 — 촬영준비 함정), 편집기 글 조각은 줄 번호 칸 옆(gutter — 글을 덮지 않는다).
import {labUi, atPhrase, em, exists, newTerminal, termWait, afterResult} from './lab-common.mjs';
import {LAB, PROMPT, label, twistie, fold, openFile, tabName, lineNo, lines, piece, area, codexInput, gutter, faint, snap} from './wv-common.mjs';
const eqLine = n => 'HYD-0' + n + ',';   // equipment.csv 2~6행(HYD-01 · 02 · 03 · 04 · 07)

export default async ctx => {
 const c = await labUi(ctx);
 const view = await c.serial(() => ctx.p.evaluate(() => ({
  tabs: document.querySelectorAll('.tabs-container .tab').length, terminal: !!document.querySelector('.terminal-wrapper')?.checkVisibility(),
  rows: [...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].map(e => e.innerText.trim()).join(),
 })));
 if (view.tabs || view.terminal || view.rows !== 'app,data,AGENTS.md,run.py' || await exists(ctx, LAB + '/output')) throw Error('06-1 시작 화면이 아님 — ./run.sh reset wv-reset.mjs로 맞추고 시작: ' + JSON.stringify(view));
 if (!(await c.serial(() => ctx.p.text())).includes('Ask Codex anything')) throw Error('빈 Codex 새 대화가 아님 — wv-reset.mjs로 맞추고 시작');
 await c.installPointer({x: 900, y: 460});
 await ctx.begin();

 await ctx.say('wv0301');
 await ctx.say('wv0302', async () => {
  await c.emph(await area(c, ctx, '.part.sidebar'), {shape: 'box'});
  await atPhrase(ctx, '가운데가'); await c.emph(await area(c, ctx, '.part.editor'), {shape: 'box'});
  await atPhrase(ctx, '오른쪽은'); await c.emph(em.codex(0.02, 0.01, 0.98, 0.99), {shape: 'box'});
  await snap(ctx, 'wv0302-codex');
  await atPhrase(ctx, '새 터미널을 눌러'); await newTerminal(c, ctx);
 }, {at: '왼쪽이'});
 await termWait(ctx, PROMPT); await afterResult(ctx);
 await snap(ctx, 'wv0302-terminal');
 await ctx.say('wv0303', async () => {
  await c.emph(em.term(PROMPT), {shape: 'band'});
  await snap(ctx, 'wv0303-term');
  await atPhrase(ctx, '오른쪽 대화 칸'); await c.emph(await codexInput(c, ctx), {shape: 'box'});
  await snap(ctx, 'wv0303-input');
 }, {at: '아래 터미널과'});
 await ctx.say('wv0304', async () => {
  await c.emph(label('app'), {shape: 'band'});
  await atPhrase(ctx, 'data에는'); await c.emph(label('data'), {shape: 'band'});
  await atPhrase(ctx, 'AGENTS.md는'); await c.emph(label('AGENTS.md'), {shape: 'band'});
  await atPhrase(ctx, 'run.py는'); await c.emph(label('run.py'), {shape: 'band'});
  await snap(ctx, 'wv0304');
 }, {at: 'app에는'});
 await ctx.say('wv0305', async () => {
  await fold(c, ctx, 'app', 1, true);
  await atPhrase(ctx, '이 안의 코드는'); await faint(c, ctx, label('ui'), {shape: 'band', at: await twistie(c, ctx, 'ui', 2)}); await faint(c, ctx, label('utils'), {shape: 'band', keep: true, point: false});   // 흐린 띠(대본) — 한데 짚는다
  await atPhrase(ctx, 'features 폴더만'); await c.emph(label('features'), {shape: 'box', at: await twistie(c, ctx, 'features', 2)});
  await snap(ctx, 'wv0305');
  await atPhrase(ctx, '지금 볼 곳은'); await fold(c, ctx, 'app', 1, false); await fold(c, ctx, 'data', 1, true);
 }, {at: 'app을 펼치면'});
 await ctx.say('wv0306', async () => {
  await openFile(c, ctx, 'field_notes.md', 2);
  await atPhrase(ctx, '현장 메모라는 파일이에요'); await c.emph(tabName('field_notes.md'), {shape: 'underline'});
  await atPhrase(ctx, '받는 사람이'); await c.emph(em.line('받는 사람:'), {shape: 'underline'});
  await snap(ctx, 'wv0306-to');
  await atPhrase(ctx, '그 아래 표에는'); await c.emph(await lines(c, ctx, '| 파일 |', '| `part_aliases.csv`', true), {shape: 'box'});
  await snap(ctx, 'wv0306-table');
  await atPhrase(ctx, '세로 막대로 칸을 나눠 적은'); await c.emph(await piece(c, ctx, '| 파일 |', '|', 'all'), {shape: 'underline'});
  await snap(ctx, 'wv0306-bar');
  await atPhrase(ctx, '나온 곳이 다 다릅니다');
  await c.emph(em.line('| `equipment.csv`'), {shape: 'underline', phrase: 'CMMS 설비 대장', at: await gutter(c, ctx, await lines(c, ctx, '| `equipment.csv`'))});
  for (const [l, p] of [['| `components.csv`', '설비별 담당자 작성'], ['| `sensors.csv`', 'SCADA 태그 목록 + 점검표'], ['| `spare_parts.csv`', 'ERP 자재'], ['| `part_aliases.csv`', '구매팀']]) await c.emph(em.line(l), {shape: 'underline', phrase: p, keep: true, point: false});
  await snap(ctx, 'wv0306-from');
 }, {at: '메모부터 열어 보죠'});
 await ctx.say('wv0307', async () => {
  await openFile(c, ctx, 'equipment.csv', 2);
  await atPhrase(ctx, '쉼표가 칸을'); { const t = await piece(c, ctx, eqLine(1), ',', 'all'); await c.emph(t, {shape: 'underline', at: await gutter(c, ctx, t)}); }
  await snap(ctx, 'wv0307-comma');
  await atPhrase(ctx, 'CSV라고'); await c.emph(tabName(), {shape: 'underline', phrase: '.csv'});
  await snap(ctx, 'wv0307-csv');
 }, {at: '표를 하나 열어 볼게요'});
 await ctx.say('wv0308', async () => {
  await c.emph(em.line('설비코드,설비명'), {shape: 'band'});
  await atPhrase(ctx, '가로 한 줄이 설비 한 대'); await c.emph(em.line(eqLine(1)), {shape: 'band'});
  await atPhrase(ctx, '왼쪽 끝에 붙은 숫자'); await c.emph(lineNo(2), {shape: 'box'});
  await snap(ctx, 'wv0308-no');
  await atPhrase(ctx, '2행부터 6행까지'); await c.emph(await lines(c, ctx, eqLine(1), eqLine(7)), {shape: 'band'});
  await snap(ctx, 'wv0308-rows');
 }, {at: '맨 윗줄은'});
 await ctx.say('wv0381', async () => {
  await faint(c, ctx, label('components.csv'), {shape: 'band', at: await twistie(c, ctx, 'components.csv', 2)});   // 흐린 띠(대본) — 하나씩 부르지 않는다
  for (const n of ['part_aliases.csv', 'sensors.csv', 'spare_parts.csv']) await faint(c, ctx, label(n), {shape: 'band', keep: true, point: false});
  await snap(ctx, 'wv0381-csv');
  await atPhrase(ctx, '이름이 json으로 끝나는 파일이'); await faint(c, ctx, label('relationships.json'), {shape: 'band', at: await twistie(c, ctx, 'relationships.json', 2)});
  await snap(ctx, 'wv0381-json');
 }, {at: '나머지 표들도'});
 return {segment: 'wv-03', next: 'wv-04a: 첫 실행 명령', aiRequests: 0};
};
