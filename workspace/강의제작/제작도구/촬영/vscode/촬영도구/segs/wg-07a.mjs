import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 07a(첫 페이지 — Codex 요청, 리허설은 WG_NOSEND=1): load.cypher 빈 틀 머리 · 설비 표와 스키마의 짝 → 넣는 쿼리 셋 부탁(긴 글이라 붙여 넣고, 말에 맞춰 부탁 글의 조각에 밑줄). 답이 늦으면 기다림 말 wg0791.
// 시작: wg-06c 뒤 첫 페이지(wg-06b 끝 화면). 끝: 답이 다 선 화면(load.cypher 탭이 앞에 있다).
const f = F.wg0701, g = F.wg0702;
export default seg({name: 'wg-07a', page: 0, kind: 'ask', next: 'wg-07b: load.cypher 읽기 · python run.py load',
 cues: [
  {id: 'wg0701', at: '드디어 넣습니다', steps: [[null, open('load.cypher', 3)], ['여덟 개는 이 폴더에 이미', ED(f.rest, 'underline', {faint: true})], ['비어 있는 것은 꼴이 서로 다른', ED(f.three)]]},
  {id: 'wg0702', at: '설비 쿼리는 원자료인 설비 표의', steps: [[null, ED(g.raw)], ['표를 열어 보면 열 이름이', open('equipment.csv', 2)], [null, L(g.head, 'underline')], ['그래프에 들어갈 속성 이름은', open('schema.json', 3)], [null, ED(g.name, 'box')], [null, ED(g.status, 'box', {keep: true})],
   ['어느 열로 식별자를 짓고', ED(g.id)], ['설계 때 스키마에 적어 둔 것을', closeTab('schema.json')], [null, closeTab('equipment.csv')]]},
  {id: 'wg0703', at: '부탁에는 실험에서 알아낸 것부터', steps: [[null, ask(ASK.wg0703)], ['바뀌지 않는 식별자만', IU('바뀌지 않는 식별자만')], ['노드 쿼리를 관계 쿼리보다 먼저', IU('노드 쿼리를 관계 쿼리보다 먼저')],
   ['날짜로 바꿔 넣어 달라는', IU('date(…)로 바꿔 넣어 줘')], ['처음 만들 때만 넣으라는', IU('처음 만들 때만')], ['레이블과 식별자로 찾으라는', IU('레이블과 식별자로 찾아')], [END, send]]},
  {hold: {lines: ['wg0791'], allow: ['load.cypher']}},
 ]});
