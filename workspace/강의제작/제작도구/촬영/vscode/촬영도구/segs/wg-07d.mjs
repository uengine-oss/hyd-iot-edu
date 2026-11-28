import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 07d(첫 페이지): 같은 적재 한 번 더 — python run.py repeat.
// 시작: wg-07b 끝 화면(터미널에 load 출력). 끝: 터미널에 repeat 출력.
export default seg({name: 'wg-07d', page: 0, kind: 'run', next: 'wg-07e: 결과 화면 F5',
 cues: [
  {id: 'wg0717', at: '명령 뒤의 낱말을 repeat로', steps: [[null, cmd('python run.py repeat')], ['다시 돕니다', enter], [null, ran()]]},
 ]});
