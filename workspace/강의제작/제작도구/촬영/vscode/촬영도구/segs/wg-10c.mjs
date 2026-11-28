import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 10c(둘째 페이지 — PAGE=1): 결과 화면 F5 — 질문 3 1/5, 다른 표기는 다름 · 없는 품번은 견줄 수 없음, RF-10 0줄과 「맞는 노드 없음」 카드.
// 시작: 둘째 페이지에 09c의 결과 화면(설비별 교체 부품), output/result.html = usage(작은 쿼리). 끝: 같은 화면.
const f = F.wg1003;
export default seg({name: 'wg-10c', page: 1, kind: 'result', next: 'wg-10d: 왜 0줄인지 묻기',
 cues: [
  {id: 'wg1003', at: '이번에는 맨 위 글이 다릅니다', steps: [[null, all(f5(TITLE.usage), R(f.top, 'underline'))], ['사내 품번으로 물은 줄은 같음', R({cmp: f.same, td: 0}, 'underline')],
   ['다른 표기로 물은 줄들이 다름', R({cmp: f.diff[0], td: 0}, 'box')], [null, R({cmp: f.diff[1], td: 0}, 'box', {keep: true})], [null, R({cmp: f.diff[2], td: 0}, 'box', {keep: true})],
   ['맨 아래 없는 품번 줄에는', R({cmp: f.noteRow, td: 3, css: '.chip', has: f.noteHas}, 'underline')], ['RF-10으로 물으면 설비 다섯 대가', R({cmp: f.rf}, 'band')], ['아래 카드에도', R(f.card, 'box')]]},
 ]});
