import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 02b(둘째 페이지 — PAGE=1, 앞 구간 이름을 준다): 저절로 열린 첫 결과 화면(원자료와 모델). 녹화 전에 결과 화면을 연다(first).
// 시작: wg-02a 끝(output/result.html = sources). 끝: 같은 결과 화면.
export default seg({name: 'wg-02b', page: 1, kind: 'result', first: TITLE.sources, next: 'wg-02c: python run.py db',
 cues: [
  {id: 'wg0202', at: '맨 위에 우리가 쓸 모델이', steps: [[null, R(F.wg0202.top, 'underline')], ['아래 그림에서는', R(F.wg0202.map, 'box')]]},
 ]});
