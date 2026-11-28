import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 13d(둘째 페이지 — PAGE=1): 결과 화면 F5 — 구조 검사 통과와 맞춰 본 것 넷. 시작: 둘째 페이지에 13b의 결과 화면, output/result.html = check. 끝: 같은 화면.
const f = F.wg1304, chk = i => ({sec: f.sec, card: f.checks[i], css: '.ch b'});
export default seg({name: 'wg-13d', page: 1, kind: 'result', next: 'wg-13e: 맺음(VS Code)',
 cues: [
  {id: 'wg1304', at: '구조 검사 통과입니다', steps: [[null, all(f5(TITLE.check), R(f.top, 'underline'))], ['식별자가 겹치는 노드가 없는지', R(chk(0))], ['관계의 양 끝 노드가 실제로', R(chk(1))], ['관계의 시작과 끝이 스키마와', R(chk(2))], ['스키마에 없는 속성이', R(chk(3))]]},
 ]});
