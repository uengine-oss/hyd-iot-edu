import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 11f(첫 페이지): Codex가 적은 decisions.csv 두 줄 → python run.py changes. 찾는 글은 FIND.wg1112.
// 시작: wg-11e 끝. 끝: 터미널에 changes 출력.
const f = F.wg1112;
export default seg({name: 'wg-11f', page: 0, kind: 'view', next: 'wg-11g: 결과 화면 F5',
 cues: [
  {id: 'wg1112', at: '결정 표의 두 줄에', steps: [[null, open('decisions.csv', 3)], [null, L(f.a, 'band')], [null, L(f.b, 'band', {keep: true})], ['changes를 한 번 더', cmd('python run.py changes')], ['볼게요', enter], [null, ran()]]},
 ]});
