import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 13a(첫 페이지): 폴더를 닫았다가 다시 열고(File → Close Folder → Open Recent의 graph-lab) python run.py db — 같은 랩 DB가 다시 켜진다. 메뉴 글자는 UI 표(미검증 — Codex 요청이 없으니 리허설로 먼저 본다).
// 시작: wg-12r 뒤 첫 페이지(wg-12q 끝 화면). 끝: 다시 연 폴더의 터미널에 db 출력. 터미널에 새 랩 DB를 만들었다는 글이 나오면 대본대로 constraints → load → update 큐를 새 id로 더한다.
export default seg({name: 'wg-13a', page: 0, kind: 'run', next: 'wg-13b: 결과 화면 F5',
 cues: [
  {id: 'wg1301', at: '폴더를 닫았다가', steps: [[null, closeFolder], ['다시 열고', reopenFolder], ['db로 랩 DB를 다시', all(termEnsure, cmd('python run.py db'))], [END, enter], [null, ran({timeout: 120000})]]},
 ]});
