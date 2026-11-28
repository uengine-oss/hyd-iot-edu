import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
const FLOW = P(W.FLOW), THREE = P(W.THREE);
// 07편 구간 01(첫 페이지): 여는 말 — 오늘 할 일과 우리 몫(펜 그림 · 세 칸). 조작은 그림뿐이다.
// 시작: SEG=wg-01 ./run.sh reset wg-reset.mjs — graph-lab 폴더가 열린 웹 VS Code, 탐색기 접힘, 편집기 탭 없음, 터미널 열림(빈 프롬프트), Codex 새 대화. 끝: 같은 화면(그림은 모두 걷음).
export default seg({name: 'wg-01', page: 0, kind: 'say', next: 'wg-02a: 첫 python run.py',
 check: async (c, ctx) => {
  const v = await c.serial(() => ctx.p.evaluate(() => ({tabs: document.querySelectorAll('.tabs-container .tab').length, term: !!document.querySelector('.terminal-wrapper')?.checkVisibility(), open: document.querySelectorAll('.explorer-folders-view .monaco-list-row[aria-expanded="true"]').length})));
  if (v.tabs || !v.term || v.open) throw Error('wg-01: 첫 화면이 아님(탭 ' + v.tabs + ' · 터미널 ' + v.term + ' · 펼친 폴더 ' + v.open + ') — SEG=wg-01 ./run.sh reset wg-reset.mjs');
  if (!(await c.serial(() => ctx.p.text())).includes('Ask Codex anything')) throw Error('wg-01: Codex 새 대화 화면이 아님');
 },
 cues: [
  {id: 'wg0101'},
  {id: 'wg0102', at: '하나는 어떤 클래스와', steps: [[null, FLOW.draw('schema')], ['다른 하나는', FLOW.draw('data')], ['보전팀이 궁금할 때마다', FLOW.draw('db', 'a1', 'a2')], ['물어서 답을 받으려면', FLOW.draw('a3', 'ask')]]},
  {id: 'wg0103', at: '그래서 오늘 할 일은', steps: [[null, FLOW.hide()], ['먼저 모델 파일에 든', THREE.draw('s1')], ['그다음에는 보전팀의 질문을', THREE.draw('s2')], ['그래서 마지막에는', THREE.draw('s3')]]},
  {id: 'wg0104', at: 'Codex에게 맡기겠습니다', steps: [[null, codexE('box', {faint: true})]]},
  {id: 'wg0105', at: '쿼리를 받기 전에는', steps: [[null, THREE.draw('l1')], ['쿼리를 받으면', THREE.draw('l2')], ['돌린 다음에는', THREE.draw('l3')], [END, THREE.erase('l1', 'l2', 'l3')]]},
  {id: 'wg0106', at: '넣기 전에 적어 둘 것이', steps: [[null, THREE.draw('pre')], [END, THREE.hide()]]},
 ]});
