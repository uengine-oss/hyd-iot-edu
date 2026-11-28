import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
const SUM5 = P(W.SUM5), PRED = P(W.predFig());
// 07편 구간 06c(둘째 페이지 — PAGE=1): 결과 화면 F5 — 실험 카드 다섯 장, 정리 다섯 줄(그림), Codex의 예측과 견줌(그림 — FIND.wg0612를 녹화 답에 맞춘다).
// 시작: 둘째 페이지에 05c의 결과 화면(유일 제약 걸기), output/result.html = probe. 끝: 같은 화면(그림은 걷음).
const f = F.wg0606, card = i => ({sec: W.SEC6.sec, card: f.cards[i], cardHas: true});
export default seg({name: 'wg-06c', page: 1, kind: 'result', next: 'wg-07a: 넣는 쿼리 부탁',
 cues: [
  {id: 'wg0606', at: '다섯 가지 가운데', steps: [[null, all(f5(TITLE.probe), R(f.top, 'underline'))], ['첫 번째, CREATE로', R(card(0), 'box')], ['두 번째에서 DB가 거절', R({...card(0), css: '.badge'}, 'underline')],
   ['넣는 쿼리를 CREATE로 쓰면', R({...card(0), css: 'li', has: '해 본 쿼리 1'}, 'underline', {faint: true})], [null, R({...card(0), css: 'li', has: '해 본 쿼리 2'}, 'underline', {faint: true, keep: true})]]},
  {id: 'wg0607', at: '두 번째가 바로', steps: [[null, R(card(1), 'box')], ['DB는 거절했습니다', R({...card(1), css: '.badge'}, 'underline')], ['MERGE는 괄호 안에 적은 것이', R({...card(1), css: 'p', phrase: f.says[1]}, 'band')]]},
  {id: 'wg0608', at: '세 번째는 속성 이름을', steps: [[null, R(card(2), 'box')], ['DB는 그대로 받았고', R({...card(2), css: '.badge'}, 'underline')], ['같은 값을 식별자로 가진', R({...card(2), css: 'p', phrase: f.says[2]}, 'band')]]},
  {id: 'wg0609', at: '네 번째는 화살표를', steps: [[null, R(card(3), 'box')], ['DB는 이것도 받아 줬어요', R({...card(3), css: '.badge'}, 'underline')], ['그런 다음 원래 방향인', R({...card(3), css: 'p', phrase: f.says[3]}, 'band')]]},
  {id: 'wg0610', at: '마지막은 끝 노드가', steps: [[null, R(card(4), 'box')], ['오류 없이 끝났는데', R({...card(4), css: '.badge'}, 'underline')], ['만들어진 관계는 0개', R({...card(4), css: 'p', phrase: f.says[4]}, 'band')]]},
  {id: 'wg0611', at: '정리하면, DB가 막아 주는', steps: [[null, R({sec: W.SEC6.sec, css: 'p.note', phrase: f.note}, 'underline')], ['MERGE로 쓰게 하고', all(pin(W.SEC6), SUM5.draw('t1'))], ['괄호 안에는 식별자만', SUM5.draw('t2')],
   ['노드를 먼저 넣고', SUM5.draw('t3')], ['화살표 방향과 속성 이름은', SUM5.draw('t4')], ['넣은 뒤에는 개수를', SUM5.draw('t5')], [END, SUM5.hide()]]},
  {id: 'wg0612', at: 'Codex의 예측도 카드와', steps: [[null, all(pin(W.SEC6), PRED.show('h', ...F.wg0612.lines.map((_, i) => 'p' + (i + 1))))], ['맞았네요', PRED.draw(...F.wg0612.hit.map(i => 'k' + i))], [END, PRED.hide()]]},
 ]});
