import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 10e(첫 페이지): 까닭 답(other_codes) → graph.json의 P-RTN-FLT 노드(1289행 근처)의 other_codes를 열어 보이고 닫는다. 찾는 글은 FIND.wg1005.
// 시작: wg-10d 끝. 끝: graph.json을 닫은 화면.
const f = F.wg1005;
export default seg({name: 'wg-10e', page: 0, kind: 'view', next: 'wg-10f: 다른 이름으로도 찾게 고치기',
 cues: [
  {id: 'wg1005', at: 'RF-10은 사내 품번이 아니라', steps: [[null, X(f.why, 'band')], ['다른 이름을 모아 둔 목록 속성에', all(open('graph.json', 3), gotoLine(f.line, f.seen))], [null, ED(f.codes[0])], [null, ED(f.codes[1], 'underline', {keep: true})], ['원인을 알았으니', closeTab('graph.json')]]},
 ]});
