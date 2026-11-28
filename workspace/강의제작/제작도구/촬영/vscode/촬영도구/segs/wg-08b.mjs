import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
const REL = P(W.REL);
// 07편 구간 08b(첫 페이지): Codex가 쓴 질문 1 쿼리를 관계 그림 옆에서 읽고(화살표 머리 · RETURN의 열 이름과 기대 답의 볼_열) python run.py sensors. 찾는 글은 FIND.wg0802~0804.
// 시작: wg-08a 끝. 끝: 터미널에 sensors 출력(query.cypher 탭이 앞에 있다).
const f = F.wg0802, g = F.wg0803;
export default seg({name: 'wg-08b', page: 0, kind: 'view', next: 'wg-08c: 결과 화면 F5',
 cues: [
  {id: 'wg0802', at: '쿼리가 왔습니다', steps: [[null, open('query.cypher', 3)], ['첫 줄이 MATCH이고', L(f.match, 'band')], ['화살표 그림을 옆에', REL.show(...W.REL_ALL)], ['맨 앞 괄호가 설비예요', ED(f.asset)], ['달러 표시가 붙은 이름', ED(f.slot, 'box')],
   ['설비에서 HAS_COMPONENT로', ED(f.rels[0])], [null, PE('has', 'box', {keep: true})], ['구성 요소에서 MONITORED_BY로', ED(f.rels[1])], [null, PE('mon', 'box', {keep: true})], ['센서에서 OBSERVES라는', ED(f.rels[2])], [null, PE('obs', 'box', {keep: true})]]},
  {id: 'wg0803', at: '이 화살표의 머리입니다', steps: [[null, EDin(f.rels[0], '->', 'box')], [null, EDin(f.rels[1], '->', 'box', {keep: true})], [null, EDin(f.rels[2], '->', 'box', {keep: true})], ['그 아래 RETURN은', L(g.ret, 'underline')],
   ['AS 뒤에 적힌 이름이', ED(g.as[0], 'box')], [null, ED(g.as[1], 'box')], [null, ED(g.as[2], 'box')], [null, ED(g.as[3], 'box')],
   ['기대 답 파일의 볼 열 칸에', tab('expected.csv')], [null, ED(g.cols[0])], [null, ED(g.cols[1], 'underline', {keep: true})], [null, ED(g.cols[2], 'underline', {keep: true})], ['넷 다 같네요', tab('query.cypher')]]},
  {id: 'wg0804', at: '그러니까 이 쿼리는', steps: [[null, all(REL.hide(), EDL(F.wg0804.from, F.wg0804.to, 'band'))], ['sensors로', cmd('python run.py sensors')], ['봅니다', enter], [null, ran()]]},
 ]});
