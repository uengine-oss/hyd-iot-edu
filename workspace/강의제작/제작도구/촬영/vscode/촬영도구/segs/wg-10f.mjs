import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 10f(첫 페이지 — Codex 요청, 리허설은 WG_NOSEND=1): 다른 이름(other_codes)으로도 찾고 없는 품번이면 note 한 줄 — 고쳐 달라는 부탁. 답이 늦으면 기다림 말 wg1092.
// 시작: wg-10e 끝. 끝: 답이 다 선 화면.
export default seg({name: 'wg-10f', page: 0, kind: 'ask', next: 'wg-10g: 넓힌 질문 3 읽기 · python run.py usage',
 cues: [
  {id: 'wg1006', at: '그래서 다른 이름 목록으로도', steps: [[null, ask(ASK.wg1006)], ['기대 답을 적을 때 정해 둔 것입니다', send]]},
  {hold: {lines: ['wg1092'], allow: ['query.cypher']}},
 ]});
