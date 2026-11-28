import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
const THREE = P(W.THREE);
// 07편 구간 10h(둘째 페이지 — PAGE=1): 결과 화면 F5 — 질문 3 5/5, RF-10의 길, 없는 품번 한 줄, 커플링 부품을 쓰는 HYD-07의 예비(보관), 세 칸 가운데 둘째 칸 끝(그림).
// 시작: 둘째 페이지에 10c의 결과 화면(작은 쿼리의 usage), output/result.html = usage(넓힌 쿼리). 끝: 같은 화면(그림은 걷음).
const f = F.wg1009, g = F.wg1010;
export default seg({name: 'wg-10h', page: 1, kind: 'result', next: 'wg-11a: python run.py changes',
 cues: [
  {id: 'wg1009', at: '이번에는 모든 줄이', steps: [[null, all(f5(TITLE.usage), R(f.top, 'underline'))], ['아까 0줄이던 RF-10이', R({cmp: f.rf, td: 0}, 'band')], ['그림에도 물은 값에서 부품으로', R({sec: f.fig, css: '.gbox'}, 'box')],
   ['없는 품번으로 물은 줄에는', R({cmp: f.noteRow, td: 3}, 'underline')]]},
  {id: 'wg1010', at: '커플링 부품을 쓰는 설비', steps: [[null, R({cmp: g.row, td: 3, css: '.chip', has: g.chip}, 'box')], ['둘째 칸까지', all(clr, THREE.show('s1', 's2', 's3', 'd1'), THREE.draw('d2'))], [END, THREE.hide()]]},
 ]});
