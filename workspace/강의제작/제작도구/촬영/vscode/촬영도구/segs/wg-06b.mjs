import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 06b(첫 페이지): Codex의 예측(흐린 띠 — 읽지 않는다) → python run.py probe. 찾는 글은 FIND.wg0605.
// 시작: wg-06a 끝. 끝: 터미널에 probe 출력.
export default seg({name: 'wg-06b', page: 0, kind: 'view', next: 'wg-06c: 결과 화면 F5',
 cues: [
  {id: 'wg0605', at: '다섯 가지마다', steps: [[null, X(F.wg0605.list, 'band', {faint: true})], ['probe라는 명령이', cmd('python run.py probe')], ['그대로 남습니다', enter], [null, ran()]]},
 ]});
