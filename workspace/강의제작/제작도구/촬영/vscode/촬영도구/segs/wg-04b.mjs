import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 04b(첫 페이지): 설비마다 줄 수 표에서 물을 설비를 고른다. 찾는 글은 FIND.wg0410(녹화 답에 맞춘다 — 대본 「Codex 답에 맞출 큐」: 더 나은 설비를 가리키면 4 · 8 · 9장의 설비 · 행 번호 · 개수를 그 설비로).
// 시작: wg-04a 끝. 끝: 같은 화면.
const f = F.wg0410;
export default seg({name: 'wg-04b', page: 0, kind: 'view', next: 'wg-04c: 기대 답 후보 부탁',
 cues: [
  {id: 'wg0410', at: '첫 번째 질문은 HYD-01로', steps: [[null, X(f.hyd01)], ['두 번째 질문은 HYD-02로', X(f.hyd02a)], ['부품 번호도 예전 품번이나', XK(f.hyd02b)]]},
 ]});
