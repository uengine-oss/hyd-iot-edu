import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 04e(첫 페이지 — Codex 요청, 리허설은 WG_NOSEND=1): 열어 본 줄이 맞았다고 말하고 expected.csv에 적게 한다. 승인 창이 뜨면 그 편에서 처음일 때 wg0415를 말하며 Allow once(창의 글이 expected.csv일 때만 — 아니면 멈춘다).
// 시작: wg-04d 끝. 끝: 답이 다 선 화면.
export default seg({name: 'wg-04e', page: 0, kind: 'ask', next: 'wg-04f: expected.csv 열기 · python run.py expected',
 cues: [
  {id: 'wg0414', at: '먼저 제가 열어 본 줄이', steps: [[null, ask(ASK.wg0414)], ['다른 파일은 바꾸지 말라고 붙이죠', send]]},
  {hold: {lines: [], allow: ['expected.csv'], approveCue: true}},
 ]});
