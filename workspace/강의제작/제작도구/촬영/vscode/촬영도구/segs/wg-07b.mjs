import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
const ROWS = P(W.ROWS), SEEK = P(W.SEEK), REL = P(W.REL);
// 07편 구간 07b(첫 페이지): Codex가 쓴 load.cypher의 쿼리 셋을 절마다 읽고 python run.py load. 찾는 글은 FIND.wg0704~0714(Codex가 쓴 쿼리에 맞춘다 — 한 줄 쿼리는 옆으로 굴려 짚는다).
// 시작: wg-07a 끝(load.cypher 탭 — Codex가 고친 글이 다시 읽혀 있다). 끝: 터미널에 load 출력. 랩 DB: 유일 제약 → 넣음.
const a = F.wg0704, b = F.wg0705, c6 = F.wg0706, s = F.wg0707, r = F.wg0710, k = F.wg0711, m = F.wg0712, u = F.wg0714;
const pairs = s.pairs.flatMap((p, i) => [[null, ED(p)], [null, N(i + 1, 'underline', {keep: true})]]);
export default seg({name: 'wg-07b', page: 0, kind: 'view', next: 'wg-07c: 결과 화면 F5',
 cues: [
  {id: 'wg0704', at: '파일에 쿼리가 셋', steps: [[null, tab('load.cypher')], ['맨 위 설비 쿼리부터', L(a.mark, 'underline')], ['달러 표시가 붙은 rows', ED(a.rows, 'box')], ['쿼리를 돌릴 때 run.py가', ROWS.draw('list', 'slot', 'give')]]},
  {id: 'wg0705', at: '그 앞의 UNWIND는', steps: [[null, ED(b.unwind)], ['뒤의 AS row는', ED(b.asRow)], ['명단을 받아서 한 줄씩', ROWS.draw('out', 'r1', 'r2', 'r3', 'r4', 'r5', 'row')]]},
  {id: 'wg0706', at: '그 뒤는 아는 것입니다', steps: [[null, all(ROWS.hide(), ED(c6.merge))], ['Asset 레이블과 아이디 하나만', EDin(c6.merge, c6.label, 'underline')], [null, EDin(c6.merge, c6.key, 'underline')],
   ['속성 이름도 소문자예요', EDin(c6.key, c6.id, 'box')], ['row에 점을 찍고 설비코드라고', EDin(c6.key, c6.val, 'box')]]},
  {id: 'wg0707', at: '마지막의 SET은', steps: [[null, ED(s.set)], ['이름 속성에는 설비명 칸을', ED(s.name, 'box')], ['상태 속성에는', ED(s.status, 'box', {keep: true})],
   ['스키마에 적힌 짝과', note(W.SRC8, {title: 'schema.json — Asset의 source', at: W.SRC8_AT})], ...pairs,
   ['설치일만은 date라는', ED(s.date, 'box')], ['SET 앞을 보면 ON CREATE가', all(noteOff, ED(s.on, 'box'))]]},
  {id: 'wg0708', at: '값을 처음 만들 때만', steps: [[null, L(F.wg0708.line, 'band')], ['그래서 넣는 쿼리에는', note(['넣기 — 없는 것만 채운다', '고치기 — 따로, 수정 쿼리로'], {at: W.SRC8_AT})], [END, noteOff]]},
  {id: 'wg0709', at: '이 쿼리도 한 문장으로', steps: [[null, EDL(F.wg0709.from, F.wg0709.to, 'band')]]},
  {id: 'wg0710', at: '관계 쿼리도 첫머리는', steps: [[null, EDL(r.from, r.to, 'band')], ['row 뒤의 a가', ED(r.a)], ['b가 끝 쪽', ED(r.b)], ['달라지는 곳은 가운데의 MATCH', ED(r.match)], ['쉼표를 사이에 두고', ED(r.comma, 'box')]]},
  {id: 'wg0711', at: '괄호마다 아이디 앞에', steps: [[null, EDin(k.la, k.a, 'box')], [null, EDin(k.lb, k.b, 'box', {keep: true})], ['아이디만 적어도 찾기는', SEEK.draw('scan')], ['레이블을 같이 적어 주면', SEEK.draw('seek')], [END, SEEK.hide()]]},
  {id: 'wg0712', at: '양 끝을 찾았으면 MERGE가', steps: [[null, ED(m.merge)], ['화살표 머리가', EDin(m.merge, m.head, 'box')], ['그림과 같은 방향', all(REL.show(...W.REL_ALL), PE('has'))], ['그러니까 이 관계 쿼리는', EDL(r.from, r.to, 'band')], [END, REL.hide()]]},
  {id: 'wg0713', at: '이 쿼리가 설비 쿼리보다', steps: [[null, L(F.wg0713.marks[1], 'underline')], ['쿼리는 위에서부터 차례로', L(F.wg0713.marks[0], 'underline')], [null, L(F.wg0713.marks[1], 'underline', {keep: true})], [null, L(F.wg0713.marks[2], 'underline', {keep: true})]]},
  {id: 'wg0714', at: '세 번째 쿼리도 꼴은', steps: [[null, EDL(u.from, u.to, 'band')], ['구성 요소와 부품을 찾아서', EDin(u.la, u.a, 'underline')], [null, EDin(u.lb, u.b, 'underline', {keep: true})], ['USES_PART 화살표를', ED(u.rel)],
   ['다른 곳은 끝에 붙은 ON CREATE SET', ED(u.set, 'box')], ['같은 팬 베어링을', open('components.csv', 2)], [null, LP(u.l3, u.p3)], [null, LP(u.l12, u.p12, 'underline', {keep: true})], ['그런데 이 글자는', closeTab('components.csv')],
   ['한 문장으로 하면', EDL(u.from, u.to, 'band')]]},
  {id: 'wg0715', at: '넣는 명령은 load', steps: [[null, cmd('python run.py load')], [END, enter], [null, ran()]]},
 ]});
