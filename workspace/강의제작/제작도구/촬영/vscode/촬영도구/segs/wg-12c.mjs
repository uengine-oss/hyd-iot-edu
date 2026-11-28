import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 12c(첫 페이지 — Codex 요청, 리허설은 WG_NOSEND=1): schema_additions.csv의 칸 이름 → 상태 속성의 이름 · 자료형 · 필수를 나에게 물어보라는 부탁. Codex가 물어 온다(답은 wg-12d가 본다).
// 시작: wg-12b 끝. 끝: Codex의 물음이 다 선 화면(schema_additions.csv 탭).
export default seg({name: 'wg-12c', page: 0, kind: 'ask', next: 'wg-12d: 물음에 답하기',
 cues: [
  {id: 'wg1207', at: '스키마에 더할 속성을 적는 표가', steps: [[null, open('schema_additions.csv', 3)], [null, L(F.wg1207.head, 'underline')], ['속성의 이름과 자료형', ask(ASK.wg1207)], ['물어보라고 하겠습니다', send]]},
  {hold: {lines: [], allow: ['schema_additions.csv']}},
 ]});
