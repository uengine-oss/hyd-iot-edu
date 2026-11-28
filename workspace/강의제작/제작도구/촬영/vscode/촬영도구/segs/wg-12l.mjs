import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 12l(둘째 페이지 — PAGE=1): 결과 화면 F5 — 랩 DB와 모델 파일의 개수가 같다. 시작: 둘째 페이지에 12j의 결과 화면, output/result.html = status. 끝: 같은 화면.
export default seg({name: 'wg-12l', page: 1, kind: 'result', next: 'wg-12m: python run.py repeat',
 cues: [
  {id: 'wg1222', at: '엉뚱한 노드는', steps: [[null, all(f5(TITLE.status), R(F.wg1222.top, 'underline'))], ['Codex가 세어 준 수와도', R(F.wg1222.lab, 'box')]]},
 ]});
