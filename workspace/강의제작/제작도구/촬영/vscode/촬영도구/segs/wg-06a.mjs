import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
const EXP = P(W.EXP);
// 07편 구간 06a(첫 페이지 — Codex 요청, 리허설은 WG_NOSEND=1): 넣기 전 실험 다섯 가지와 강사의 예측(그림), Codex에게도 예측을 받는다. 답이 늦으면 기다림 말 wg0691.
// 시작: wg-05c 뒤 첫 페이지(wg-05b 끝 화면). 끝: 예측 답이 다 선 화면.
export default seg({name: 'wg-06a', page: 0, kind: 'ask', next: 'wg-06b: 예측 · python run.py probe',
 cues: [
  {id: 'wg0601'},
  {id: 'wg0602', at: '같은 노드를 CREATE로', steps: [[null, EXP.draw('e1')], ['MERGE의 괄호 안에', EXP.draw('e2')], ['속성 이름을 소문자', EXP.draw('e3')], ['관계의 화살표를 거꾸로', EXP.draw('e4')], ['끝 노드가 아직 없는', EXP.draw('e5')]]},
  {id: 'wg0603', at: '첫 번째는', steps: [[null, EXP.draw('g1')], ['화살표를 거꾸로', EXP.draw('g4')]]},
  {id: 'wg0604', at: 'Codex에게도 예측을', steps: [[null, all(EXP.hide(), ask(ASK.wg0604))], ['파일은 바꾸지 말라고 하고요', send]]},
  {hold: {lines: ['wg0691']}},
 ]});
