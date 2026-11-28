import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 11e(첫 페이지 — Codex 요청, 리허설은 WG_NOSEND=1): 고른 두 길과 이유 · 근거 줄 · 바뀌는 답을 결정 표에 적게 한다(긴 글이라 붙여 넣는다).
// 시작: wg-11d 끝. 끝: 답이 다 선 화면.
export default seg({name: 'wg-11e', page: 0, kind: 'ask', next: 'wg-11f: decisions.csv · python run.py changes',
 cues: [
  {id: 'wg1111', at: '고른 것은 결정 표에', steps: [[null, ask(ASK.wg1111)], ['Codex가 적게 해요', send]]},
  {hold: {lines: [], allow: ['decisions.csv']}},
 ]});
