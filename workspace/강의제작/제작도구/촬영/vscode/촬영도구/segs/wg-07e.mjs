import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
const THREE = P(W.THREE);
// 07편 구간 07e(둘째 페이지 — PAGE=1): 결과 화면 F5 — 다시 넣어도 그대로, 세 칸 가운데 첫 칸 끝(그림).
// 시작: 둘째 페이지에 07c의 결과 화면(모델 적재), output/result.html = repeat. 끝: 같은 화면(그림은 걷음).
const f = F.wg0718;
export default seg({name: 'wg-07e', page: 1, kind: 'result', next: 'wg-08a: 질문 1 부탁',
 cues: [
  {id: 'wg0718', at: '다시 넣어도 그대로라고', steps: [[null, all(f5(TITLE.repeat), R(f.top, 'underline'))], ['개수도 그대로', R(f.bars, 'box')], ['이것으로 세 칸 가운데', all(clr, THREE.show('s1', 's2', 's3'), THREE.draw('d1'))], [END, THREE.hide()]]},
 ]});
