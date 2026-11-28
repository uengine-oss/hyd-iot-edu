import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 12a(첫 페이지 — Codex 요청, 리허설은 WG_NOSEND=1): 넣기를 다시 돌려서는 고쳐지지 않는 까닭(load.cypher의 ON CREATE SET) → 반영 뒤 기대 답과 개수를 부탁(말에 맞춰 부탁 글의 조각에 밑줄, wg1203 끝에 보낸다). 답이 늦으면 기다림 말 wg1291.
// 시작: wg-11g 뒤 첫 페이지(wg-11f 끝 화면). 끝: 답이 다 선 화면(load.cypher 탭은 닫음).
export default seg({name: 'wg-12a', page: 0, kind: 'ask', next: 'wg-12b: 고친 기대 답 보기',
 cues: [
  {id: 'wg1201', at: '넣는 쿼리는 값을 처음 만들 때만', steps: [[null, tab('load.cypher')], [null, ED(F.wg1201.set)], ['그렇다고 DB를 다 지우고', closeTab('load.cypher')]]},
  {id: 'wg1202', at: '고치기 전에 기준부터', steps: [[null, ask(ASK.wg1202)], ['새로 등록된 표기로 묻는', IU('새로 등록된 표기로 물은 질문 3 줄')], ['처음부터 HYD-01로', IU('목록에서 빠진 센서가 붙은 설비로 물은 줄')]]},
  {id: 'wg1203', at: '센서와 상태를 짝지은', steps: [[null, IU('볼_열이 tag+status인 줄')], ['종류마다 몇 개여야', IU('종류마다 있어야 할 개수')], ['세어 달라고 했습니다', send]]},
  {id: 'wg1204'},
  {hold: {lines: ['wg1291'], allow: ['expected.csv']}},
 ]});
