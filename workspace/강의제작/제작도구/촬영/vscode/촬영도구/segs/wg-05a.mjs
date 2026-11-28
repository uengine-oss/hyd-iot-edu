import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
const MAP = P(W.MAP);
// 07편 구간 05a(첫 페이지 — Codex 요청, 리허설은 WG_NOSEND=1): 조건은 따라 들어가지 않는다(그림) → 유일 제약을 거는 쿼리 부탁. 답이 오는 동안 당부의 까닭(wg0504, 자르지 않는다).
// 시작: wg-04g 뒤 첫 페이지(wg-04f 끝 화면). 끝: 답이 다 선 화면.
export default seg({name: 'wg-05a', page: 0, kind: 'ask', next: 'wg-05b: constraints.cypher 읽기',
 cues: [
  {id: 'wg0501', at: '이론에서 본 대로', steps: [[null, MAP.show('m1', 'm2', 'm3')], ['조건은 따라 들어가지 않습니다', MAP.draw('m4')]]},
  {id: 'wg0502', at: 'DB에 직접 걸어 둬야', steps: [[null, MAP.draw('m5')], [END, MAP.hide()]]},
  {id: 'wg0503', at: '이 제약 쿼리 파일에', steps: [[null, XE('constraints.cypher', 3)], ['써 달라고 했어요', ask(ASK.wg0503)], ['당부를 두 가지 붙였습니다', send]]},
  {id: 'wg0504'},
  {hold: {lines: [], allow: ['constraints.cypher']}},
 ]});
