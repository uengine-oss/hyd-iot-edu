import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 12d(첫 페이지 — Codex 요청, 리허설은 WG_NOSEND=1): Codex의 물음 셋(띠 — 찾는 글은 FIND.wg1208, 12c 답에 맞춘다)에 답해 schema_additions.csv에 적게 한다.
// 시작: wg-12c 끝. 끝: 답이 다 선 화면.
export default seg({name: 'wg-12d', page: 0, kind: 'ask', next: 'wg-12e: schema_additions.csv 보기',
 cues: [
  {id: 'wg1208', at: 'Codex가 세 가지를 물어', steps: [[null, X(F.wg1208.asks, 'band')], ['이름은 status로 할게요', ask(ASK.wg1208)], ['아니오라고 답해요', send]]},
  {hold: {lines: [], allow: ['schema_additions.csv']}},
 ]});
