import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 08c(둘째 페이지 — PAGE=1): 결과 화면 F5 — 질문 1 대조 표 3/3, 따라간 길, 두 가지 검증(글상자).
// 시작: 둘째 페이지에 07e의 결과 화면(같은 적재 다시 실행), output/result.html = sensors. 끝: 같은 화면(글상자는 걷음).
const f = F.wg0805;
export default seg({name: 'wg-08c', page: 1, kind: 'result', next: 'wg-09a: 질문 2 부탁',
 cues: [
  {id: 'wg0805', at: '맞았습니다', steps: [[null, all(f5(TITLE.sensors), R(f.top, 'underline'))], ['구성 요소와 센서의 짝 열 개가', R({cmp: f.pair}, 'band')], ['물리량 줄과 한계 줄도', R({cmp: f.qty}, 'band', {faint: true})],
   ['한계가 없는 센서는 0이 아니라', R({cmp: f.lim, td: 3, css: '.chip', has: f.none, nth: 0}, 'underline')], ['그 아래 그림에는', R({sec: f.fig, css: '.gbox'}, 'box')]]},
  {id: 'wg0806', at: '방금 한 일을 검증이라고', steps: [[null, note(['설계 때의 검증 — 넣기 전, 기록이 조건을 지켰나', '지금의 검증 — 넣은 뒤, 질문의 답이 맞나'], {at: 'tr'})], [END, noteOff]]},
 ]});
