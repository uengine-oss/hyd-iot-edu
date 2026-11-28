import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 04c(첫 페이지 — Codex 요청, 리허설은 WG_NOSEND=1): 정한 것을 모두 담은 기대 답 후보 부탁(긴 글이라 붙여 넣는다). 답이 늦으면 기다림 말 wg0491.
// 시작: wg-04b 끝. 끝: 후보 표가 다 선 화면.
export default seg({name: 'wg-04c', page: 0, kind: 'ask', next: 'wg-04d: 후보 표 · 근거 줄 열기',
 cues: [
  {id: 'wg0411', at: '이제 지금까지 정한 것을 모두', steps: [[null, ask(ASK.wg0411)], ['파일은 바꾸지 말라고 적었어요', send]]},
  {hold: {lines: ['wg0491']}},
 ]});
