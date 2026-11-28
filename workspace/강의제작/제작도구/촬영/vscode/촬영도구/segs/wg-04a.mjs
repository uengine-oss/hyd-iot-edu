import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
const REL = P(W.REL), ANS = P(W.ANS);
// 07편 구간 04a(첫 페이지 — Codex 요청, 리허설은 WG_NOSEND=1): 기대 답을 적을 곳 · 세 질문(글상자) · 질문이 지나가는 화살표 · 정해 둘 약속 넷 · 수정본 폴더, 그리고 설비마다 줄 수를 묻는 부탁.
// 시작: wg-03b 끝. 끝: 그 답이 다 선 화면. 글상자 · 그림은 wg0408에서 걷는다.
export default seg({name: 'wg-04a', page: 0, kind: 'ask', next: 'wg-04b: 줄 수 표 보기',
 cues: [
  {id: 'wg0401', at: '설계 때도 적어 본 기대 답이에요', steps: [[null, unfold('app', 1)], [null, unfold('features', 2)], ['적을 곳은', XE('expected.csv', 3)]]},
  {id: 'wg0402', at: '이번에 물을 질문은', steps: [[null, note(W.QNOTE, {at: W.QNOTE_AT})]]},
  {id: 'wg0403', at: '셋 다 설계 때', steps: [[null, REL.show(...W.REL_ALL)], ['첫 번째 질문은', PE('has')], [null, PE('mon', 'box', {keep: true})], [null, PE('obs', 'box', {keep: true})],
   ['두 번째와 세 번째 질문은', PE('uses')], ['실물로 가는 화살표만', PE('inst', 'box', {faint: true})], [null, REL.draw('chk')], [END, REL.hide()]]},
  {id: 'wg0404', at: '원자료에 없는 품번으로 물었을 때', steps: [[null, N('없는 품번으로 물으면')], ['그래서 없는 품번으로 물으면', ANS.draw('a1')]]},
  {id: 'wg0405', at: '다음은 교체 부품이 없는', steps: [[null, N('② 구성 요소마다')], ['부품 자리를 없음으로', ANS.draw('a2')], ['센서의 한계도', N('① 설비의')], ['이것도 없음으로', ANS.draw('a3')]]},
  {id: 'wg0406', at: '첫 번째 질문의 답을', steps: [[null, N('① 설비의')], ['이걸 막으려고 답을 짝으로', ANS.draw('a4')]]},
  {id: 'wg0407', at: '두 번째 질문에서는', steps: [[null, N('② 구성 요소마다')], ['그래프에서는 부품을 사내 품번 하나로', ANS.draw('a5')]]},
  {id: 'wg0408', at: '세 번째 질문에는', steps: [[null, all(noteOff, ANS.hide())], ['changes라는 폴더가', unfold('changes/2026-10-20', 2, true)],
   ['바뀐 내용만 모아서', XE('equipment_changes.csv', 3)], [null, XE('notes.md', 3, 'underline', {keep: true})], [null, XE('part_alias_changes.csv', 3, 'underline', {keep: true})], [null, XE('sensor_changes.csv', 3, 'underline', {keep: true})]]},
  {id: 'wg0409', at: '마지막으로 정할 게', steps: [[null, ask(ASK.wg0409)], ['몇 개씩 있는지부터', send]]},
  {hold: {lines: []}},
 ]});
