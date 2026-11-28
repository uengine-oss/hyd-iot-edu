import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 05c(둘째 페이지 — PAGE=1): 결과 화면 F5 — 종류마다 걸린 자물쇠, Asset 카드의 DB 답.
// 시작: 둘째 페이지에 04g의 결과 화면(기대 답), output/result.html = constraints. 끝: 같은 화면.
const f = F.wg0508;
export default seg({name: 'wg-05c', page: 1, kind: 'result', next: 'wg-06a: 넣기 전 실험',
 cues: [
  {id: 'wg0508', at: '종류 여섯 개 모두', steps: [[null, all(f5(TITLE.constraints), R(f.top, 'underline'))], ['레이블마다 자물쇠가', R({sec: f.sec, css: '.cards'}, 'box')], ['설비 카드를 보면', R({sec: f.sec, card: f.card, css: 'p'}, 'band')],
   ['그 밑의 영어 문장은', R({sec: f.sec, card: f.card, css: 'li', phrase: f.said}, 'underline')], ['시험하느라 만든 노드는', R({sec: f.sec, css: 'p.note', phrase: f.back}, 'underline')]]},
 ]});
