import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 12n(둘째 페이지 — PAGE=1): 결과 화면 F5 — 다시 넣어도 그대로. 시작: 둘째 페이지에 12l의 결과 화면, output/result.html = repeat. 끝: 같은 화면.
export default seg({name: 'wg-12n', page: 1, kind: 'result', next: 'wg-12o: python run.py sensors',
 cues: [
  {id: 'wg1224', at: '고친 값이 살아 있습니다', steps: [[null, all(f5(TITLE.repeat), R(F.wg1224.top, 'underline'))]]},
 ]});
