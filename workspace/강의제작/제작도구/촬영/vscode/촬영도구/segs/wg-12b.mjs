import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 12b(첫 페이지): Codex가 고친 expected.csv(반영 뒤 답)와 답의 개수 표. 찾는 글은 FIND.wg1205 · 1206.
// 시작: wg-12a 끝. 끝: 같은 화면(expected.csv 탭).
const f = F.wg1205;
export default seg({name: 'wg-12b', page: 0, kind: 'view', next: 'wg-12c: 상태 속성을 물어 달라는 부탁',
 cues: [
  {id: 'wg1205', at: '고친 줄을 보면', steps: [[null, tab('expected.csv')], [null, LP(f.cpl, f.status)], ['첫 번째 질문의 짝들은', LP(f.pairRow, f.pair)], ['그 밑에 센서와 상태를', LP(f.tsRow, f.ts, 'box')], ['맨 아래에는 새 표기로', L(f.added, 'band')]]},
  {id: 'wg1206', at: '세어 준 개수는', steps: [[null, X(F.wg1206.table, 'box')]]},
 ]});
