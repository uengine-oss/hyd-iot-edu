import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 12m(첫 페이지): python run.py repeat(고친 값이 살아 있는지). 시작: wg-12k 끝 화면. 끝: 터미널에 repeat 출력.
export default seg({name: 'wg-12m', page: 0, kind: 'run', next: 'wg-12n: 결과 화면 F5',
 cues: [
  {id: 'wg1223', at: 'repeat로 확인해', steps: [[null, cmd('python run.py repeat')], [END, enter], [null, ran()]]},
 ]});
