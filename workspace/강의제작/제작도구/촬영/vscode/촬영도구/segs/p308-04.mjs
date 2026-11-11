// 실전 3회차 08편 구간 04: app → features → build_record.md를 열어 적재 수 표 첫 줄에 노드 253 · 관계 449를 적고 저장한다. AI 요청 없음.
// 시작: p308-02 끝(웹 VS Code 공간, 터미널 열림). 이 구간은 학생 파일을 고치므로 다시 찍을 때는 p308-reset.mjs가 build_record.md를 ZIP에서 다시 꺼낸다.
import {labUi, afterResult, row, rowSeen, inView, scrollEditorTo} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.p308.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에
const ROW = '| 설비 모델 · 조치 기준 적재 뒤 |';
const WANT = '| 설비 모델 · 조치 기준 적재 뒤 | 253 | 449 | |';

export default async ctx => {
 const c = await labUi(ctx);
 const before = (await ctx.fs.readFile(LAB + '/app/features/build_record.md', 'utf8')).split(/\r?\n/);
 if (!before.includes('| 설비 모델 · 조치 기준 적재 뒤 | | | |')) throw Error('build_record.md가 ZIP 원본이 아님 — p308-reset.mjs로 되돌린다');
 const endOf = () => c.serial(() => ctx.p.evaluate(text => {
  const l = [...document.querySelectorAll('.editor-instance .view-lines .view-line')].find(e => e.textContent.replace(/\u00a0/g, ' ').startsWith(text));
  if (!l) throw Error('줄 없음: ' + text);
  const sp = [...l.querySelectorAll('span span')].filter(s => s.textContent.length).pop() || l; const b = sp.getBoundingClientRect(); return {x: b.right + 8, y: b.y + b.height / 2};
 }, ROW));
 // 터미널이 열린 채 시작하는 구간 — 화면 크기를 다시 걸면 뜨는 터미널 크기 표시(.terminal-resize-overlay, 「125 x 22」)가 사라진 뒤 녹화한다(촬영준비 함정)
 await ctx.waitFor(() => ![...document.querySelectorAll('.terminal-resize-overlay')].some(e => getComputedStyle(e).opacity !== '0'), 5000);
 await c.installPointer(ctx.prev ? null : {x: 120, y: 200});
 await ctx.begin();
 await ctx.say('p308-0401', async () => {
  const a = await c.explorerRow('app', 1); await c.clickAt(a.x, a.y);
  await rowSeen(ctx, 'features', 2);
  const f = await c.explorerRow('features', 2); await c.clickAt(f.x, f.y);
  await rowSeen(ctx, 'build_record.md', 3);
  const b = await c.explorerRow('build_record.md', 3); await c.clickAt(b.x, b.y); await c.key('Enter');
 }, {at: '앱, features 폴더를'});
 await ctx.waitFor(() => document.querySelector('.tabs-container .tab.active .label-name')?.textContent === 'build_record.md');
 await afterResult(ctx);
 await ctx.say('p308-0402', async () => {
  await scrollEditorTo(c, ctx, '## 적재 수', 360);
  const q = inView(await endOf()); await c.clickAt(q.x, q.y);
  await c.key('End');
  for (let n = 0; n < 5; n++) await c.key('ArrowLeft');   // 줄 끝에서 다섯 칸 왼쪽 = 노드 수 칸의 「| 」 뒤(여섯은 한 칸 앞에 들어갔다)
  await c.type('253 ');
  for (let n = 0; n < 2; n++) await c.key('ArrowRight');
  await c.type('449 ');
 }, {at: '적재 수 표의 첫 줄'});
 await ctx.say('p308-0403', async () => { await c.key('Control+s'); }, {at: 'Ctrl+S로'});
 await ctx.waitFor(() => !document.querySelector('.tabs-container .tab.active')?.classList.contains('dirty'));
 const after = (await ctx.fs.readFile(LAB + '/app/features/build_record.md', 'utf8')).split(/\r?\n/);
 if (!after.includes(WANT)) throw Error('적재 수 줄이 기대와 다름: ' + JSON.stringify(after.find(l => l.startsWith(ROW))));
 await ctx.say('p308-0404', async () => { const q = await c.codexPoint(0.5, 0.45); await c.move(q.x, q.y); }, {at: '이름이 달라도', gap: 1500});
 return {segment: 'p308-04', next: 'p308-05: Codex와 핀 세척 근거와 기존 ID 찾기(가이드 2단계)', aiRequests: 0};
};
