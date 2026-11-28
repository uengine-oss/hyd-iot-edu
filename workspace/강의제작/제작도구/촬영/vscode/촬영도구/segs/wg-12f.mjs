import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 12f(첫 페이지 — Codex 요청, 리허설은 WG_NOSEND=1): 질문 1이 센서의 상태도 돌려주게 고쳐 달라는 부탁. 답이 늦으면 기다림 말 wg1292.
// 시작: wg-12e 끝. 끝: 답이 다 선 화면.
export default seg({name: 'wg-12f', page: 0, kind: 'ask', next: 'wg-12g: 고친 RETURN 보기',
 cues: [
  {id: 'wg1210', at: '상태도 한 열로 돌려 달라고', steps: [[null, ask(ASK.wg1210)], ['status입니다', send]]},
  {hold: {lines: ['wg1292'], allow: ['query.cypher']}},
 ]});
