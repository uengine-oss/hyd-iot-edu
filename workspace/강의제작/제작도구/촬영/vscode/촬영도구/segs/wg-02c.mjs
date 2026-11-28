import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 02c(첫 페이지): 랩 DB 띄우기 — python run.py db. 끝날 때까지 터미널이 조용하다(자르지 않는다). 「랩 DB 준비 완료」가 늦으면 기다림 말 wg0291 · wg0292.
// 시작: wg-02a 끝(터미널에 첫 실행 출력). 끝: 터미널에 db 출력과 빈 프롬프트. 랩 DB: 없음 → 띄움(빈 DB).
export default seg({name: 'wg-02c', page: 0, kind: 'run', next: 'wg-02d: 결과 화면 F5',
 cues: [
  {id: 'wg0203', at: 'python run.py db라고', steps: [[null, cmd('python run.py db')], ['칩니다', enter]]},
  {id: 'wg0204'},
  {hold: {term: '랩 DB 준비 완료', lines: ['wg0291', 'wg0292'], timeout: 180000}},
  {id: 'wg0205', at: '랩 DB 준비 완료라고', steps: [[null, T('랩 DB 준비 완료', 'underline')], [null, ran()]]},
 ]});
