import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 10g(첫 페이지): 넓힌 질문 3의 WHERE … OR … · OPTIONAL · CASE를 읽고 python run.py usage. 찾는 글은 FIND.wg1007 · 1008(「// 질문 3」 아래에서만).
// 시작: wg-10f 끝. 끝: 터미널에 usage 출력.
const f = F.wg1007, q = {after: f.after};
export default seg({name: 'wg-10g', page: 0, kind: 'view', next: 'wg-10h: 결과 화면 F5',
 cues: [
  {id: 'wg1007', at: '달라진 곳을 보죠', steps: [[null, all(tab('query.cypher'), edSee(f.where, q))], ['부품을 찾는 줄에 WHERE가', ED(f.where, 'band', q)], ['OR 앞은', ED(f.left, 'underline', q)], ['OR 뒤는', ED(f.right, 'underline', q)],
   ['OR는 또는이라는', ED(f.or, 'box', {...q, inside: f.where})], ['찾는 줄 앞에 OPTIONAL이', ED(f.word, 'box', {...q, inside: f.opt})], ['그 줄에 원자료에 없는 품번이라는', ED(f.when, 'band', {...q, faint: true})]]},
  {id: 'wg1008', at: '그러니까 이 쿼리는', steps: [[null, EDL(F.wg1008.from, F.wg1008.to, 'band')], ['다시 usage예요', cmd('python run.py usage')], [END, enter], [null, ran()]]},
 ]});
