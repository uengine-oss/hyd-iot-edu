import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
const MAP = P(W.MAP);
// 07편 구간 03a(첫 페이지 — Codex 요청, CODEX_HOME=… ./run.sh rec, 리허설은 WG_NOSEND=1): 모델 파일 두 개를 펴고 살펴 달라고 부탁한다. 답이 오는 동안 그림 석 줄(자르지 않는다). 답이 오면 그림을 걷는다.
// 시작: wg-02c 끝. 끝: Codex 답이 다 선 화면(그 답을 보는 말은 wg-03b).
export default seg({name: 'wg-03a', page: 0, kind: 'ask', next: 'wg-03b: 답 보기',
 cues: [
  {id: 'wg0301', at: '그래서 안도 한번', steps: [[null, unfold('data', 1)], [null, unfold('model', 2)], ['살필 것은', XE('schema.json', 3)], [null, XE('graph.json', 3, 'underline', {keep: true})]]},
  {id: 'wg0302', at: '살피는 일은 Codex에게', steps: [[null, ask(ASK.wg0302)], ['알 수가 없으니까요', send]]},
  {id: 'wg0303', at: '스키마의 클래스 이름은', steps: [[null, MAP.draw('m1')], ['인스턴스는 하나하나가', MAP.draw('m2')], ['관계는 이름과 방향이', MAP.draw('m3')]]},
  {hold: {lines: []}},
  {do: MAP.hide()},
 ]});
