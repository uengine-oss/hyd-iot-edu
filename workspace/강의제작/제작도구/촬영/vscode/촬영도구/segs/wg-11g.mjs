import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 11g(둘째 페이지 — PAGE=1): 결과 화면 F5 — 내가 정할 것 두 곳 모두 「정함」.
// 시작: 둘째 페이지에 11b의 결과 화면(수정본 살펴보기 — 정하기 전), output/result.html = changes(정한 뒤). 끝: 같은 화면.
const f = F.wg1113;
export default seg({name: 'wg-11g', page: 1, kind: 'result', next: 'wg-12a: 기대 답 고치기 부탁',
 cues: [
  {id: 'wg1113', at: '내가 정할 것 두 곳이 모두', steps: [[null, all(f5(TITLE.changes), R(TOPS(f.done), 'underline'))], ['고른 것과 근거가 카드에', R({sec: f.sec, card: f.points[0], css: '.badge'}, 'box')], [null, R({sec: f.sec, card: f.points[1], css: '.badge'}, 'box', {keep: true})]]},
 ]});
