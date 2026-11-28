import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
// 07편 구간 11b(둘째 페이지 — PAGE=1): 결과 화면 F5 — 수정본 다섯 줄의 카드(말의 차례대로 짚는다), 「삭제」의 뜻, 내가 정할 것 둘, 두 길(글상자).
// 시작: 둘째 페이지에 10h의 결과 화면(부품의 사용 설비), output/result.html = changes(정하기 전). 끝: 같은 화면(글상자는 걷음).
const f = F.wg1102, g = F.wg1103;
export default seg({name: 'wg-11b', page: 1, kind: 'result', next: 'wg-11c: 두 길 견주기 부탁',
 cues: [
  {id: 'wg1102', at: '수정본은 모두 다섯 줄', steps: [[null, all(f5(TITLE.changes), R(f.top, 'underline'))], ['HYD-02는 설비 이름이', R({card: f.name[0], css: 'li', has: f.name[1]}, 'underline')], ['이동식 예비 설비인 HYD-07은', R({card: f.h7[0], css: 'li', has: f.h7[1]}, 'band')],
   ['센서 쪽은 한계가 바뀐 줄이', R({card: f.ps1[0], css: 'li', has: f.ps1[1]}, 'underline')], ['삭제라고 적힌 줄이 하나', R({card: f.vs1, css: '.badge'}, 'box')], ['나머지 한 줄은 부품에', R({card: f.fb, css: '.badge'}, 'underline')]]},
  {id: 'wg1103', at: '카드 아래 글을 보면', steps: [[null, R({sec: g.sec, css: 'p.note', phrase: g.note}, 'underline')], ['화면 아래쪽에도 내가 정할 것', R({sec: g.decide, card: g.points[0], css: '.badge'}, 'box')], [null, R({sec: g.decide, card: g.points[1], css: '.badge'}, 'box', {keep: true})],
   ['어느 쪽을 고르느냐에 따라', note(g.ways, {at: 'tr'})], [END, noteOff]]},
 ]});
