import * as W from './wg-common.mjs';
const {seg, END, E, N, P, PE, XE, rootE, open, closeTab, tab, unfold, fold, ED, EDin, LP, L, LS, EDL, edSee, gotoLine, cmd, enter, ran, T, termEnsure, closeFolder, reopenFolder, ask, send, IU, X, XK, codexE, R, see, pin, f5, openMore, note, noteOff, all, clr, TOP, TOPS, TITLE, ASK, FIND: F} = W;
const THREE = P(W.THREE), LAYER = P(W.LAYER);
// 07편 구간 13e(첫 페이지): 맺음 — 세 칸과 식별자(그림), AI가 쓴 쿼리에서 볼 곳 · 스스로 설명해 볼 두 가지(글상자), 층 그림(06-1과 같은 그림). 끝 프레임은 graph-lab 폴더가 열린 VS Code.
// 시작: wg-13d 뒤 첫 페이지(wg-13c 끝 화면). 끝: 같은 화면(그림 · 글상자는 걷음).
export default seg({name: 'wg-13e', page: 0, kind: 'say', next: '끝',
 cues: [
  {id: 'wg1305', at: '세 칸으로 되짚어', steps: [[null, THREE.show('s1', 's2', 's3')], ['넣을 때는 식별자에', PE('s1')], ['물을 때는 질문을', PE('s2')], ['고칠 때는 식별자로', PE('s3')], ['세 번 모두 기댄 것은', THREE.draw('key', 'k1', 'k2', 'k3')]]},
  {id: 'wg1306', at: '쿼리는 처음부터 끝까지', steps: [[null, all(THREE.hide(), note(['화살표 방향', 'MERGE 괄호 안', '찾을 때 쓰는 값과 레이블', '속성 이름'], {title: 'AI가 쓴 쿼리에서 볼 곳', at: [470, 140]}))], [END, noteOff]]},
  {id: 'wg1307', at: '여기서 두 가지를', steps: [[null, note(['다시 넣어도 왜 노드가 늘지 않았나', '고친 값이 왜 옛 값으로 돌아가지 않았나'], {at: [470, 140]})], ['이제 보전팀이 물으면', noteOff]]},
  {id: 'wg1308', at: '맨 아래에 설비와', steps: [[null, LAYER.draw('L1', 'L1t')], ['그 위에 작업 절차와', LAYER.draw('L2')], ['맨 위에 문서에서', LAYER.draw('L3')], ['올린다고 했습니다', LAYER.draw('r2', 'r3', 'r4')],
   ['그 맨 아래층이 이걸로', LAYER.draw('ok')], ['위에 올릴 것들은', PE('L2', 'box', {faint: true})], [null, PE('L3', 'box', {faint: true, keep: true})], ['이 식별자를 붙잡고', all(clr, LAYER.draw('v1', 'v2', 'v3', 'v4', 'v5'))], [END, LAYER.hide()]]},
 ]});
