import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 09a(첫 페이지 — Codex 요청, 리허설은 WG_NOSEND=1): 질문 2만 더해 달라는 부탁. 답이 늦으면 기다림 말 wg0991.
// 시작: wg-08c 뒤 첫 페이지(wg-08b 끝 화면). 끝: 답이 다 선 화면.
export default seg({name: 'wg-09a', page: 0, kind: 'ask', next: 'wg-09b: OPTIONAL MATCH 읽기 · python run.py parts',
 cues: [
  {id: 'wg0901', at: '첫 번째 쿼리는 그대로 두고', steps: [[null, ask(ASK.wg0901)], ['그 약속도 함께 적었어요', send]]},
  {hold: {lines: ['wg0991'], allow: ['query.cypher']}},
 ]});
