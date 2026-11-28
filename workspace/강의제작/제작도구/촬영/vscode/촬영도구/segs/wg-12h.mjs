import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 12h(첫 페이지 — Codex 요청, 리허설은 WG_NOSEND=1): 수정본을 update.cypher에 반영해 달라는 부탁(긴 글이라 붙여 넣고, 말에 맞춰 부탁 글의 조각에 밑줄, wg1213 끝에 보낸다). 답이 오는 동안 당부의 까닭(wg1214), 늦으면 기다림 말 wg1293.
// 시작: wg-12g 끝. 끝: 답이 다 선 화면. Codex가 지우는 범위를 되물으면 대본 제작 확인용대로 그 답을 새 큐로 쓴다.
export default seg({name: 'wg-12h', page: 0, kind: 'ask', next: 'wg-12i: 짝 표 · update.cypher 읽기 · python run.py update',
 cues: [
  {id: 'wg1212', at: '이제 고치는 쿼리를 받습니다', steps: [[null, XE('update.cypher', 3)], ['이번 부탁에서도 알맹이는', ask(ASK.wg1212)], ['여기에 하나를 꼭 붙여요', IU('쿼리에 적지 말고 row의 칸으로')]]},
  {id: 'wg1213', at: '수로 담을 값은', steps: [[null, IU('수로 담을 값은 수로')], ['새 표기는', IU('이미 있으면 다시 더하지 않게')], ['지우는 범위가', IU('쓰기 전에 물어봐')], ['말도 넣었습니다', send]]},
  {id: 'wg1214'},
  {hold: {lines: ['wg1293'], allow: ['update.cypher'], timeout: 600000}},
 ]});
