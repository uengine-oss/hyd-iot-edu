import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 12e(첫 페이지): schema_additions.csv의 새 줄. 찾는 글은 FIND.wg1209.
// 시작: wg-12d 끝. 끝: 같은 화면.
export default seg({name: 'wg-12e', page: 0, kind: 'view', next: 'wg-12f: 질문 1에 상태 열 부탁',
 cues: [
  {id: 'wg1209', at: '표에 한 줄이 생겼습니다', steps: [[null, tab('schema_additions.csv')], [null, L(F.wg1209.row, 'band')]]},
 ]});
