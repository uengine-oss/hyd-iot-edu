import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 12i(첫 페이지): 열 → 속성 짝 표(답)와 update.cypher의 쿼리 넷을 읽고 python run.py update. 찾는 글은 FIND.wg1215~1219(Codex가 쓴 쿼리에 맞춘다).
// 시작: wg-12h 끝. 끝: 터미널에 update 출력. 랩 DB: 넣음 → 수정본 반영.
const t = F.wg1215, a = F.wg1216, b = F.wg1217, c4 = F.wg1218, w = F.wg1219;
export default seg({name: 'wg-12i', page: 0, kind: 'view', next: 'wg-12j: 결과 화면 F5',
 cues: [
  {id: 'wg1215', at: '먼저 짝지은 표가', steps: [[null, X(t.table, 'box')], ['설비코드 열은 설비 노드를', X(t.rows[0])], ['설비명은 name으로', X(t.rows[1])], ['상태는 status로', X(t.rows[2])], ['센서는 설비코드와 태그를', X(t.rows[3])], ['한계가 limit으로', X(t.rows[4])]]},
  {id: 'wg1216', at: '쿼리는 네 개이고', steps: [[null, open('update.cypher', 3)], [null, L(a.marks[0], 'underline')], [null, L(a.marks[1], 'underline', {keep: true})], [null, L(a.marks[2], 'underline', {keep: true})], [null, L(a.marks[3], 'underline', {keep: true})],
   ['첫 번째는 설비 수정본의', L(a.q1, 'band')], ['그다음 MATCH가', ED(a.key, 'box')], ['SET이 이름과 상태에', ED(a.set)], ['찾을 때 쓴 값이 이름이 아니라', ED(a.key, 'box')]]},
  {id: 'wg1217', at: '두 번째는 센서의 수정 줄', steps: [[null, L(b.q2, 'band')], ['toFloat이라는 낱말이', ED(b.float, 'box')], ['세 번째가 삭제 줄을 받는', L(b.q3, 'band')], ['센서를 찾아서 상태에', ED(b.set3, 'band')], ['적는 자리도 방금 스키마에', EDin(b.set3, b.prop, 'box')]]},
  {id: 'wg1218', at: '네 번째는 추가 줄', steps: [[null, EDL(c4.from, c4.to, 'band')], ['WHERE로 그 표기가', ED(c4.where, 'box')]]},
  {id: 'wg1219', at: '파일 전체를 한 문장으로', steps: [[null, EDL(w.from, w.to, 'band')], ['update로 돌립니다', cmd('python run.py update')], [END, enter], [null, ran()]]},
 ]});
