// 통합 2회차 06-1편 구간 11(첫 페이지 — 웹 VS Code): 폴더가 이렇게 나뉜 까닭 — AGENTS.md를 열어 1 · 3 · 4 · 6 · 7행을 짚고, app/features 행을 보인다. Codex를 부르지 않고 답에 기대지 않는다.
// 시작: wv-10 끝(갖춘 부탁의 답이 남은 화면, app 접힘, data 펴짐, 편집기 앞 탭은 wv-09b가 sensors.csv를 닫은 뒤의 탭). 앞 take: wv-10.
// 끝: 편집기 앞 탭 AGENTS.md(맨 위), 탐색기에 app이 펴져 features가 보인다, 강조 없음.
// AGENTS.md는 Markdown이라 긴 줄이 화면에서 꺾여 여러 줄로 보인다 — 줄은 파일의 줄 번호로 짚는다(wv-common.mjs rows: 꺾인 화면 줄을 모두, 구절은 꺾인 자리를 넘어도).
import {labUi, atPhrase} from './lab-common.mjs';
import {label, twistie, fold, openFile, lineNo, rows, gutter, faint, answerScroll, snap} from './wv-common.mjs';

// 줄 안 구절의 밑줄 — 화살표는 줄 번호 칸 옆(글 아래에 두면 다음 줄 글을 덮는다, wv11-dry1)
const under = async (c, ctx, n, phrase, o = {}) => { const t = await rows(c, ctx, n, n, phrase); await c.emph(t, {shape: 'underline', at: await gutter(c, ctx, t), ...o}); };

export default async ctx => {
 const c = await labUi(ctx);
 const st = await c.serial(() => ctx.p.evaluate(() => ({tabs: [...document.querySelectorAll('.tabs-container .tab .label-name')].map(e => e.textContent), app: [...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].find(e => e.getAttribute('aria-level') === '1' && e.querySelector('.label-name')?.textContent.trim() === 'app')?.getAttribute('aria-expanded')})));
 if (st.tabs.includes('AGENTS.md') || st.app !== 'false') throw Error('wv-11 시작 상태가 아님(AGENTS.md가 이미 열렸거나 app이 펴짐): ' + JSON.stringify(st) + ' (segs/wv-11.mjs)');
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 await ctx.say('wv1101', async () => {
  { const q = await twistie(c, ctx, 'AGENTS.md', 1); await c.move(q.x, q.y); }
  await atPhrase(ctx, '열어 보죠'); await openFile(c, ctx, 'AGENTS.md', 1);
 }, {at: 'AGENTS.md가 바로'});
 await ctx.say('wv1102', async () => {
  await under(c, ctx, 1, 'AI 작업 경계');
  await atPhrase(ctx, '왼쪽 숫자로 6행'); await c.emph(lineNo(6), {shape: 'box'});
  await snap(ctx, 'wv1102-no');
  await atPhrase(ctx, '사람이 자료를 물으면'); await c.emph(await rows(c, ctx, 6), {shape: 'band'});
  await atPhrase(ctx, '실제 줄을 예로'); await c.emph(await rows(c, ctx, 6, 6, '실제 예 줄(파일:줄)과 개수'), {shape: 'underline', keep: true, point: false});
  await snap(ctx, 'wv1102-6');
  await atPhrase(ctx, '그 아래 7행은'); await c.emph(await rows(c, ctx, 7), {shape: 'band'});
  await atPhrase(ctx, '사람이 정한다는'); await c.emph(await rows(c, ctx, 7, 7, '사람이 정한다'), {shape: 'underline', keep: true, point: false});
  await snap(ctx, 'wv1102-7');
 }, {at: '이 파일은 AI에게'});
 await ctx.say('wv1103', async () => { await c.emph(await rows(c, ctx, 6), {shape: 'band'}); }, {at: '행을 예로 들어 달라는 말은'});
 await ctx.say('wv1181', async () => {
  await faint(c, ctx, await rows(c, ctx, 3, 5), {shape: 'band'});   // 흐린 띠(대본) — 「어디는 손대지 말고 어디에 만들라」는 규칙도 있음을 보인다(읽지 않는다)
  await snap(ctx, 'wv1181');
 }, {at: '또 지금 내가'});
 await ctx.say('wv1104', async () => {
  await under(c, ctx, 3, '`data/`, `app/ui/`, `app/utils/`, `run.py`는 제공 파일이다');
  await atPhrase(ctx, 'features에만 만든다'); await under(c, ctx, 4, '`app/features/`에서 구현한다');
  await snap(ctx, 'wv1104-4');
  await atPhrase(ctx, '그 features를 채우는'); await fold(c, ctx, 'app', 1, true);
  await c.emph(label('features'), {shape: 'box', at: await twistie(c, ctx, 'features', 2)});
  await snap(ctx, 'wv1104-features');
 }, {at: 'data의 원자료와'});
 return {segment: 'wv-11', next: 'wv-12: 맺음', aiRequests: 0, answerScroll: await answerScroll(c, ctx)};
};
