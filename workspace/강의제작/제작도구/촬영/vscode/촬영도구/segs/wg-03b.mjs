import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
const REL = P(W.REL);
// 07편 구간 03b(첫 페이지): 모델 살피기 답 보기 — 종류 · 관계 표, 41줄 → 40개, components.csv 13 · 14행. Codex를 부르지 않는다. 찾는 글은 FIND.wg0304~0306(녹화 답에 맞춘다).
// 시작: wg-03a 끝(답이 다 서고 패널이 답 끝으로 굴러가 있다). 끝: components.csv를 닫은 화면.
const f = F.wg0304, g = F.wg0305, h = F.wg0306;
export default seg({name: 'wg-03b', page: 0, kind: 'view', next: 'wg-04a: 역량 질문과 정해 둘 것',
 cues: [
  {id: 'wg0304', at: '종류는 여섯 가지', steps: [[null, X(f.table, 'box')], ['Asset이 설비이고', X(f.kinds[0], 'box')], [null, XK(f.kinds[1], 'box')],
   ['개수는 표에 적힌 대로', X(f.kinds[0], 'underline')], [null, X(f.kinds[1], 'underline')], [null, X(f.kinds[2], 'underline')], [null, X(f.kinds[3], 'underline')], [null, X(f.kinds[4], 'underline')], [null, X(f.kinds[5], 'underline')],
   ['식별자는 여섯 종류 모두', X(f.id, 'underline')]]},
  {id: 'wg0305', at: '관계는 다섯 가지', steps: [[null, X(g.table, 'box')], ['설비에서 구성 요소로 가는', X(g.ends[0])], ['구성 요소에서 센서로 가는', X(g.ends[1])], ['구성 요소에서 부품으로 가는', X(g.ends[2])],
   ['센서에서, 그 센서가 재는', X(g.ends[3])], ['구성 요소에서 실물로', X(g.ends[4])], ['그림으로 옮기면', all(clr, REL.draw(...W.REL_ALL))], [END, REL.hide()]]},
  {id: 'wg0306', at: '원자료의 구성 요소 표는', steps: [[null, X(h.why, 'band')], ['그 줄을 직접 열어', open('components.csv', 2)], ['HYD-02의 펌프가 두 줄', L(h.l13, 'band')], [null, L(h.l14, 'band', {keep: true})],
   ['떼어 낸 펌프와 새로 단', LP(h.l13, h.s13, 'underline')], [null, LP(h.l14, h.s14, 'underline', {keep: true})], ['상자를 잃어버린 게 아니라', closeTab('components.csv')]]},
 ]});
