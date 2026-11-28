import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 12g(첫 페이지): 질문 1의 RETURN 끝에 생긴 s.status AS status, 질문 2 · 3은 그대로(흐린 띠). 찾는 글은 FIND.wg1211.
// 시작: wg-12f 끝. 끝: 같은 화면(query.cypher 탭).
const f = F.wg1211;
export default seg({name: 'wg-12g', page: 0, kind: 'view', next: 'wg-12h: 고치는 쿼리 부탁',
 cues: [
  {id: 'wg1211', at: 'RETURN 줄 끝에 조각이', steps: [[null, tab('query.cypher')], [null, ED(f.status, 'box')], ['다른 곳은 그대로입니다', EDL(f.from, f.to, 'band', {faint: true})]]},
 ]});
