import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 09c(둘째 페이지 — PAGE=1): 결과 화면 F5 — 질문 2 1/1, 접힌 쿼리 결과 표의 구동 모터 「없음」 · 사내 품번, 따라간 길.
// 시작: 둘째 페이지에 08c의 결과 화면(설비별 센서), output/result.html = parts. 끝: 같은 화면.
const f = F.wg0904, row = (k, td) => ({sec: f.table, row: k, ...(td == null ? {} : {td})});
export default seg({name: 'wg-09c', page: 1, kind: 'result', next: 'wg-10a: 질문 3 부탁',
 cues: [
  {id: 'wg0904', at: '이번에도 기대 답과 같습니다', steps: [[null, all(f5(TITLE.parts), R(f.top, 'underline'))], ['결과 표를 펼쳐 보면', all(W.openMore, R(row(f.none), 'box'))], ['부품 자리는 없음이에요', R(row(f.none, 1), 'box')],
   ['그런데 답에는 전부 사내 품번으로', R(row(f.fan, 1), 'underline')], [null, R(row(f.flt, 1), 'underline', {keep: true})], ['그림에는 설비에서 구성 요소를', R({sec: f.fig, css: '.gbox'}, 'box')]]},
 ]});
