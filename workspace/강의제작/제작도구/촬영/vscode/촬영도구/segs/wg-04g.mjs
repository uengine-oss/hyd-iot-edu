import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 04g(둘째 페이지 — PAGE=1): 결과 화면 F5 — 기대 답 카드.
// 시작: 둘째 페이지에 02d의 결과 화면(랩 DB 준비), output/result.html = expected. 끝: 같은 화면.
const f = F.wg0417;
export default seg({name: 'wg-04g', page: 1, kind: 'result', next: 'wg-05a: 유일 제약',
 cues: [
  {id: 'wg0417', at: '질문마다 카드가', steps: [[null, all(f5(TITLE.expected), R(f.top, 'underline'))], ['한 장씩 생겼습니다', R({sec: f.sec, card: f.cards[0]}, 'box')], [null, R({sec: f.sec, card: f.cards[1]}, 'box', {keep: true})], [null, R({sec: f.sec, card: f.cards[2]}, 'box', {keep: true})]]},
 ]});
