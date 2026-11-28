import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
const THREE = P(W.THREE);
// 07편 구간 11a(첫 페이지): 세 칸에서 셋째 칸(그림) → python run.py changes. 대본은 세 칸을 결과 화면에서 짚고 「VS Code로 돌아와」 명령을 치지만, 한 큐가 두 페이지에 걸칠 수 없어 세 칸을 이 VS Code 화면에서 다시 띄운다.
// 시작: wg-10h 뒤 첫 페이지(wg-10g 끝 화면). 끝: 터미널에 changes 출력.
export default seg({name: 'wg-11a', page: 0, kind: 'run', next: 'wg-11b: 결과 화면 F5',
 cues: [
  {id: 'wg1101', at: '남은 칸은 하나', steps: [[null, THREE.show('s1', 's2', 's3', 'd1', 'd2')], [null, PE('s3')], ['기대 답을 적을 때 잠깐', THREE.hide()], ['changes라는 명령이', cmd('python run.py changes')], ['보여 줍니다', enter], [null, ran()]]},
 ]});
