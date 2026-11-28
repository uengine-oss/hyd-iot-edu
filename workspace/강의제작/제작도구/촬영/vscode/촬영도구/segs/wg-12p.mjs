import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 12p(둘째 페이지 — PAGE=1): 결과 화면 F5 — 질문 1 4/4, 떼어 낸 VS1이 「떼어 냄」으로 남음. 시작: 둘째 페이지에 12n의 결과 화면, output/result.html = sensors. 끝: 같은 화면.
const f = F.wg1226;
export default seg({name: 'wg-12p', page: 1, kind: 'result', next: 'wg-12q: python run.py usage',
 cues: [
  {id: 'wg1226', at: '떼어 낸 진동 센서가', steps: [[null, f5(TITLE.sensors)], ['네 줄 모두 기대 답과', R(f.top, 'underline')], ['HYD-01의 센서는 그대로', R({cmp: f.pair[0], td: 3, css: '.chip', has: f.pair[1]}, 'box')], ['그 센서 옆에 떼어 냄이라는', R({cmp: f.ts[0], td: 3, css: '.chip', has: f.ts[1]}, 'box')]]},
 ]});
