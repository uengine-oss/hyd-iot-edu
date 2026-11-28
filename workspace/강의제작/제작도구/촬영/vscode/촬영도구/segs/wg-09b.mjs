import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 09b(첫 페이지): 질문 2 쿼리의 OPTIONAL MATCH를 읽고 python run.py parts. 찾는 글은 FIND.wg0902 · 0903.
// 시작: wg-09a 끝. 끝: 터미널에 parts 출력.
const f = F.wg0902;
export default seg({name: 'wg-09b', page: 0, kind: 'view', next: 'wg-09c: 결과 화면 F5',
 cues: [
  {id: 'wg0902', at: '쿼리가 왔네요', steps: [[null, tab('query.cypher')], ['MATCH가 설비에서 구성 요소까지만', ED(f.match, 'underline', {after: f.after})], ['부품으로 가는 화살표는 아랫줄에', L(f.opt, 'band')], ['앞에 OPTIONAL이라는', EDin(f.opt, f.word, 'box')]]},
  {id: 'wg0903', at: '한 문장으로 하면', steps: [[null, EDL(F.wg0903.from, F.wg0903.to, 'band')], ['parts로', cmd('python run.py parts')], ['돌립니다', enter], [null, ran()]]},
 ]});
