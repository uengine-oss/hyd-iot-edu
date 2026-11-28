import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 13c(첫 페이지): python run.py export → 꺼낸 두 파일과 스키마의 Sensor status → python run.py check. 찾는 글은 FIND.wg1303.
// 시작: wg-13a 끝 화면. 끝: 터미널에 check 출력.
const f = F.wg1303;
export default seg({name: 'wg-13c', page: 0, kind: 'run', next: 'wg-13d: 결과 화면 F5',
 cues: [
  {id: 'wg1303', at: 'export가 랩 DB의 그래프를', steps: [[null, cmd('python run.py export')], ['꺼내 줍니다', enter], [null, ran()], [null, T(f.saved, 'underline', {phrase: f.savedPhrase})],
   ['설계에서 만든 모델 파일과', unfold('output', 1)], [null, XE('schema.json', 2)], [null, XE('graph.json', 2, 'underline', {keep: true})],
   ['꺼낸 스키마에는 우리가 더한', open('schema.json', 2)], [null, edSee(f.sensor)], [null, ED(f.status, 'underline', {after: f.sensor})],
   ['이어서 check로', all(closeTab('schema.json'), cmd('python run.py check'))], ['검사해 볼게요', enter], [null, ran()]]},
 ]});
