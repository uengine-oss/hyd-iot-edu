import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 02a(첫 페이지): 폴더 짜임을 짚고 첫 python run.py — 결과 줄이 뜬 직후 0.7초에 끝낸다(다음 구간 02b가 저절로 열린 결과 화면처럼 잇는다 — 촬영준비 길 6).
// 시작: wg-01 끝. output/이 없어야 한다(첫 실행만 결과 화면을 띄운다). 끝: 터미널에 「결과: output/result.html」.
export default seg({name: 'wg-02a', page: 0, kind: 'run', next: 'wg-02b: 결과 화면(PAGE=1)',
 check: async (c, ctx) => { if (await ctx.fs.stat(W.LAB + '/output/result.html').then(() => true, () => false)) throw Error('wg-02a: output/result.html이 이미 있음 — 첫 실행이 아니다(SEG=wg-02a ./run.sh reset wg-reset.mjs)'); },
 cues: [
  {id: 'wg0201', at: '안쪽 graph-lab 폴더를', steps: [[null, rootE('underline')], ['이번에도 우리가 채울 곳은', unfold('app', 1)], ['features 폴더 하나뿐', XE('features', 2, 'box')], ['자, 그래프 DB에', fold('app', 1)],
   ['터미널에 python run.py를', cmd('python run.py')], ['보여 줍니다', enter], [null, ran({after: 700})]]},
 ]});
