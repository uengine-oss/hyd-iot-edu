import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 08a(첫 페이지 — Codex 요청, 리허설은 WG_NOSEND=1): 질문 1 쿼리 부탁. 답이 늦으면 기다림 말 wg0891.
// 시작: wg-07e 뒤 첫 페이지(wg-07d 끝 화면). 끝: 답이 다 선 화면.
export default seg({name: 'wg-08a', page: 0, kind: 'ask', next: 'wg-08b: query.cypher 읽기 · python run.py sensors',
 cues: [
  {id: 'wg0801', at: '보전팀의 질문을 쿼리로 옮길', steps: [[null, XE('query.cypher', 3)], ['첫 번째 질문만 부탁할게요', ask(ASK.wg0801)], ['정해 둔 약속이죠', send]]},
  {hold: {lines: ['wg0891'], allow: ['query.cypher']}},
 ]});
