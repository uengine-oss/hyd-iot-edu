import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 11d(첫 페이지): 견줌 답(남길 때 · 지울 때 · 스키마에 더할 것 · 추천) → 수정본 두 줄과 스키마를 열어 근거를 본다. 찾는 글은 FIND.wg1106(녹화 답에 맞춘다) · 1107~1109.
// 시작: wg-11c 끝. 끝: equipment_changes.csv · sensor_changes.csv가 열린 화면(schema.json은 닫는다).
const f = F.wg1106, a = F.wg1107, b = F.wg1108, s = F.wg1109;
export default seg({name: 'wg-11d', page: 0, kind: 'view', next: 'wg-11e: 결정을 적어 달라는 부탁',
 cues: [
  {id: 'wg1106', at: '먼저 HYD-07이에요', steps: [[null, X(f.keep7, 'band')], ['지우면 그 줄이 답에서', X(f.drop7, 'band')], ['센서 쪽은, 남기면', X(f.keepS, 'band')], ['지우면 열 개가 아홉 개가', X(f.dropS, 'band')], ['센서를 남기려면 스키마에', X(f.schema)], ['추천과 이유도 적어 줬어요', X(f.pick)]]},
  {id: 'wg1107', at: 'HYD-07부터 보죠', steps: [[null, open('equipment_changes.csv', 3)], ['변경 칸을 보면', LP(a.line, a.how, 'box')], ['매각 예정이라는 말은', LP(a.line, a.state)], [null, LP(a.line, a.memo, 'underline', {keep: true})]]},
  {id: 'wg1108', at: '센서는 변경 칸이 삭제라서', steps: [[null, open('sensor_changes.csv', 3)], [null, LP(b.line, b.how, 'box')], ['비고를 읽어 봐도', LP(b.line, b.memo)]]},
  {id: 'wg1109', at: '우리 스키마의 센서에는', steps: [[null, open('schema.json', 3)], [null, ED(s.asset)], ['상태 속성이 없어요', EDL(s.from, s.to, 'box')], ['스키마도 그만큼 넓혀야', closeTab('schema.json')]]},
  {id: 'wg1110'},
 ]});
