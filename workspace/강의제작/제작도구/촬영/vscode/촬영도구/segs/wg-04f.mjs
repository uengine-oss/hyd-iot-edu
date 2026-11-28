import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 04f(첫 페이지): Codex가 적은 expected.csv를 열어 읽고 python run.py expected. 찾는 글은 FIND.wg0416(Codex가 쓴 줄에 맞춘다).
// 시작: wg-04e 끝. 끝: 터미널에 expected 출력(다음 구간은 둘째 페이지 F5).
const f = F.wg0416;
export default seg({name: 'wg-04f', page: 0, kind: 'view', next: 'wg-04g: 결과 화면 F5',
 cues: [
  {id: 'wg0416', at: '적힌 파일을 열어', steps: [[null, open('expected.csv', 3)], ['한 줄이 물음 하나', EDL(f.first, f.last, 'band')], ['몇 번 질문을, 어떤 값으로', L(f.head, 'underline')], ['볼 열이라는 칸에', LP(f.first, f.both, 'box')],
   ['명령 뒤의 낱말을 expected로', cmd('python run.py expected')], ['돌려 보죠', enter], [null, ran()]]},
 ]});
