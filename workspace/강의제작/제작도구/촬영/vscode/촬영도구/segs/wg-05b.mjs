import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 05b(첫 페이지): constraints.cypher를 열어 첫 줄을 절마다 읽고 python run.py constraints. 찾는 글은 FIND.wg0505~0507(Codex가 쓴 쿼리에 맞춘다 — 제약 이름 · // 메모 줄).
// 시작: wg-05a 끝. 끝: 터미널에 constraints 출력.
const f = F.wg0505, g = F.wg0506;
export default seg({name: 'wg-05b', page: 0, kind: 'view', next: 'wg-05c: 결과 화면 F5',
 cues: [
  {id: 'wg0505', at: '파일에 쿼리가 여섯 줄', steps: [[null, open('constraints.cypher', 3)], [null, EDL(f.first, f.last, 'band', {faint: true})], ['슬래시 두 개로 시작하는', LS(f.memo, 'underline')], ['첫 줄 하나만', L(f.first, 'band')]]},
  {id: 'wg0506', at: '맨 앞의 CREATE CONSTRAINT', steps: [[null, ED(g.create)], ['바로 뒤의 낱말은', ED(g.name, 'underline', {faint: true})], ['그다음 IF NOT EXISTS', ED(g.ifnot, 'box')], ['FOR 뒤에는', ED(g.forNode)], ['괄호가 노드이고', EDin(g.forNode, g.paren, 'underline')],
   ['쌍점 뒤가 레이블', EDin(g.forNode, g.label, 'underline')], ['끝의 REQUIRE 뒤에는', ED(g.req)], ['그 노드의 아이디가', EDin(g.req, g.prop, 'underline')], [null, EDin(g.req, g.uniq, 'underline')]]},
  {id: 'wg0507', at: '이 쿼리는, Asset 레이블이', steps: [[null, L(f.first, 'band')], ['나머지 다섯 줄은', EDL(F.wg0507.second, f.last, 'band', {faint: true})], ['constraints로', cmd('python run.py constraints')], ['볼게요', enter], [null, ran()]]},
 ]});
