import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 13b(둘째 페이지 — PAGE=1): 결과 화면 F5 — 랩 DB 막대가 0으로 돌아가지 않음. 시작: 둘째 페이지에 12r의 결과 화면, output/result.html = db. 끝: 같은 화면.
export default seg({name: 'wg-13b', page: 1, kind: 'result', next: 'wg-13c: export · check',
 cues: [
  {id: 'wg1302', at: '랩 DB 쪽 막대가', steps: [[null, all(f5(TITLE.db), R(F.wg1302.top, 'underline'))], ['아까 그 개수 그대로', R(F.wg1302.lab, 'box')]]},
 ]});
