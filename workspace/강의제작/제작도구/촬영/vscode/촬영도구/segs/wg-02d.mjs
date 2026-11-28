import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 02d(둘째 페이지 — PAGE=1): 결과 화면 F5 — 빈 랩 DB와 모델 파일의 막대.
// 시작: 둘째 페이지에 02b의 결과 화면(원자료와 모델), output/result.html = db. 끝: 같은 화면.
export default seg({name: 'wg-02d', page: 1, kind: 'result', next: 'wg-03a: 모델 살피기 부탁',
 cues: [
  {id: 'wg0206', at: '막대가 두 줄씩', steps: [[null, all(f5(TITLE.db), R(F.wg0206.top, 'underline'))], ['한 줄은 모델 파일에', R(F.wg0206.model, 'box')], ['다른 한 줄은 랩 DB에', R(F.wg0206.lab, 'box')], ['랩 DB 쪽은 전부 0', R(F.wg0206.zero, 'underline')]]},
 ]});
