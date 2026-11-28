import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 04d(첫 페이지): 후보 표의 근거 칸, 질문 1 맨 윗줄을 sensors.csv에서 열어 맞춰 본다. 찾는 글은 FIND.wg0412 · 0413.
// 시작: wg-04c 끝. 끝: sensors.csv가 열린 화면(닫지 않는다 — 대본 조작 칸).
const f = F.wg0413;
export default seg({name: 'wg-04d', page: 0, kind: 'view', next: 'wg-04e: 적어 달라는 부탁',
 cues: [
  {id: 'wg0412', at: '줄마다 끝에 근거가', steps: [[null, X(F.wg0412.basis)]]},
  {id: 'wg0413', at: '먼저 첫 번째 질문의 맨 윗줄', steps: [[null, X(f.pair, 'band')], ['근거라고 한 센서 표를', open('sensors.csv', 2)], ['HYD-01은 2행부터 11행까지', EDL(f.first, f.last, 'band')],
   ['맨 윗줄의 유온 센서는', LP(f.first, f.cell, 'underline')], [null, LP(f.first, f.tag, 'underline', {keep: true})], ['답에도 오일 쿨러와', X(f.one)], ['두 줄 아래는 센서와 한계의 짝', X(f.none)]]},
 ]});
