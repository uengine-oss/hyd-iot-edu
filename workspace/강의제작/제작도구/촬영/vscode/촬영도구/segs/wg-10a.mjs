import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 10a(첫 페이지 — Codex 요청, 리허설은 WG_NOSEND=1): 질문 3을 사내 품번으로만 찾는 작은 쿼리부터. 답이 늦으면 기다림 말 wg1091.
// 시작: wg-09c 뒤 첫 페이지(wg-09b 끝 화면). 끝: 답이 다 선 화면.
export default seg({name: 'wg-10a', page: 0, kind: 'ask', next: 'wg-10b: 작은 질문 3 읽기 · python run.py usage',
 cues: [
  {id: 'wg1001', at: '가장 작은 것부터 만들겠습니다', steps: [[null, ask(ASK.wg1001)], ['찾는 쿼리입니다', send]]},
  {hold: {lines: ['wg1091'], allow: ['query.cypher']}},
 ]});
