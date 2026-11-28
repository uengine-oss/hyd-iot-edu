import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
const REL = P(W.REL);
// 07편 구간 10b(첫 페이지): 작은 질문 3 쿼리를 읽고(화살표 머리는 넣을 때 그은 그대로) python run.py usage. 찾는 글은 FIND.wg1002(「// 질문 3」 아래에서만 찾는다).
// 시작: wg-10a 끝. 끝: 터미널에 usage 출력.
const f = F.wg1002, q = {after: f.after};
export default seg({name: 'wg-10b', page: 0, kind: 'view', next: 'wg-10c: 결과 화면 F5',
 cues: [
  {id: 'wg1002', at: '짧은 쿼리가 왔습니다', steps: [[null, all(tab('query.cypher'), EDL(f.from, f.to, 'band'))], ['사내 품번이 받은 값과 같은', ED(f.part, 'underline', q)], ['사내 품번과 설비 코드, 설비의 상태를', L(f.ret, 'underline')],
   ['화살표 머리도 봐야죠', REL.show(...W.REL_ALL)], ['머리는 넣을 때 그은 그대로', ED('->', 'box', {...q, inside: f.heads[0]})], [null, ED('->', 'box', {...q, inside: f.heads[1], keep: true})], [null, PE('has', 'box', {keep: true})], [null, PE('uses', 'box', {keep: true})],
   ['usage로 돌려', all(REL.hide(), cmd('python run.py usage'))], ['볼게요', enter], [null, ran()]]},
 ]});
