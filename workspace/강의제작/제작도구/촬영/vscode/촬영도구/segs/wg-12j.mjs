import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 12j(둘째 페이지 — PAGE=1): 결과 화면 F5 — 값이 바뀐 노드 다섯(말의 차례대로 카드를 짚는다), 한 번 더 해도 그대로.
// 시작: 둘째 페이지에 11g의 결과 화면(수정본 살펴보기 — 정한 뒤), output/result.html = update. 끝: 같은 화면.
const f = F.wg1220, card = k => ({sec: f.sec, card: f.cards[k]});
export default seg({name: 'wg-12j', page: 1, kind: 'result', next: 'wg-12k: python run.py status',
 cues: [
  {id: 'wg1220', at: '값이 바뀐 노드가 다섯 개', steps: [[null, all(f5(TITLE.update), R(f.top, 'underline'))], ['HYD-02는 이름이', R(card('name'), 'box')], ['HYD-07은 상태가', R(card('h7'), 'box')], ['HYD-04의 압력 센서는', R(card('ps1'), 'box')],
   ['HYD-01의 진동 센서는', R(card('vs1'), 'box')], ['팬 베어링에는', R(card('fb'), 'box')], ['맨 위에는 같은 수정을', R(TOPS(f.again), 'underline')]]},
 ]});
