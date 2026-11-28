import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 10d(첫 페이지 — Codex 요청, 리허설은 WG_NOSEND=1): 고쳐 달라기 전에 왜 0줄인지부터 묻는다(파일은 바꾸지 말라고).
// 시작: wg-10c 뒤 첫 페이지(wg-10b 끝 화면). 끝: 답이 다 선 화면.
export default seg({name: 'wg-10d', page: 0, kind: 'ask', next: 'wg-10e: 까닭 보기 · graph.json',
 cues: [
  {id: 'wg1004', at: '왜 0줄인지부터 물어요', steps: [[null, ask(ASK.wg1004)], ['파일은 아직 바꾸지 말라고 하고요', send]]},
  {hold: {lines: []}},
 ]});
