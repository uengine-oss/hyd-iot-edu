import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
const THREE = P(W.THREE);
// 07편 구간 12r(둘째 페이지 — PAGE=1): 결과 화면 F5 — HYD-07의 불용(매각 예정), 새 표기 줄, 6/6, 세 칸을 다 채움(그림).
// 시작: 둘째 페이지에 12p의 결과 화면, output/result.html = usage. 끝: 같은 화면(그림은 걷음).
const f = F.wg1228;
export default seg({name: 'wg-12r', page: 1, kind: 'result', next: 'wg-13a: 폴더 닫고 다시 열기 · python run.py db',
 cues: [
  {id: 'wg1228', at: 'HYD-07이 이제 불용', steps: [[null, all(f5(TITLE.usage), R({cmp: f.cpl[0], td: 3, css: '.chip', has: f.cpl[1]}, 'box'))], ['새로 등록된 표기로 물은 줄도', R({cmp: f.fb}, 'band')], ['모든 줄이 기대 답과 같습니다', R(f.top, 'underline')],
   ['이것으로 세 칸을 다', all(clr, THREE.show('s1', 's2', 's3', 'd1', 'd2'), THREE.draw('d3'))], [END, THREE.hide()]]},
 ]});
