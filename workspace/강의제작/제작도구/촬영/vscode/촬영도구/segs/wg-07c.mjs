import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 07c(둘째 페이지 — PAGE=1): 결과 화면 F5 — 개수 · 값 · 방향이 모델 파일과 같다, 내 쿼리가 노드를 찾는 법.
// 시작: 둘째 페이지에 06c의 결과 화면(넣기 전 실험), output/result.html = load. 끝: 같은 화면.
const f = F.wg0716, seekCard = i => ({sec: f.seek, card: f.cards[i], css: '.badge'});
export default seg({name: 'wg-07c', page: 1, kind: 'result', next: 'wg-07d: python run.py repeat',
 cues: [
  {id: 'wg0716', at: '들어갔네요', steps: [[null, all(f5(TITLE.load), R(f.top, 'underline'))], ['막대도 짝마다 똑같아졌습니다', R(f.bars, 'box')], ['바로 밑에는 값과 관계의 방향도', R(TOPS(f.same), 'underline')],
   ['그 아래에는 우리가 쓴 쿼리 셋이', R(seekCard(0), 'underline')], [null, R(seekCard(1), 'underline', {keep: true})], [null, R(seekCard(2), 'underline', {keep: true})]]},
 ]});
