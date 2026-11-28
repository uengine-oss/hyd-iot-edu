import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
const DEL = P(W.DEL);
// 07편 구간 11c(첫 페이지 — Codex 요청, 리허설은 WG_NOSEND=1): 남길 때와 지울 때 답이 어떻게 달라지는지 견줘 달라는 부탁. 답이 오는 동안 지운다는 것(그림, 자르지 않는다), 늦으면 기다림 말 wg1191 · wg1192. 답이 오면 그림을 걷는다.
// 시작: wg-11b 뒤 첫 페이지(wg-11a 끝 화면). 끝: 견줌 답이 다 선 화면.
export default seg({name: 'wg-11c', page: 0, kind: 'ask', next: 'wg-11d: 견줌 보기 · 수정본 열기',
 cues: [
  {id: 'wg1104', at: '두 길에서 답이 어떻게', steps: [[null, ask(ASK.wg1104)], ['추천과 이유도 함께요', send]]},
  {id: 'wg1105', at: '지운다는 것이 그래프에서', steps: [[null, DEL.draw(...W.DEL_ALL)], ['설비 노드도 마찬가지', DEL.draw('x')], ['화살표가 같이 사라지고', DEL.erase('a0', 'a1', 'a2', 'a3', 'a4')]]},
  {hold: {lines: ['wg1191', 'wg1192'], timeout: 600000}},
  {do: DEL.hide()},
 ]});
