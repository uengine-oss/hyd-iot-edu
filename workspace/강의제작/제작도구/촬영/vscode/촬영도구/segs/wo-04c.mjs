// 06-2 구간 04c(첫 페이지): 구성 요소 표 13 · 14행(설비 · 이름 · 일련번호 · 비고) → 펌프 자리와 그 자리를 거쳐 간 펌프 두 대(펜 그림) → 두 길 → R8(읽기 — 겹친 까닭 · 일련번호를 넣으면 · 두 길의 답 · 추천)을 보내고 답이 끝날 때까지.
// 시작: 첫 페이지는 wo-04a 끝 화면(사이에 둘째 페이지 wo-04b) — 앞 take wo-04a. 끝: R8 답이 선 화면.
import {atPhrase} from './lab-common.mjs';
import {ui, RESUME, QE, guideIn, guideHide, guideShow, seamOut, keepEnd, open, mark, note, speechEnd, SEAT, paste, send, answer, waitSay, askOf} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm2'});
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 let since = RESUME;
 if (since == null) {
  const both = async (o, first = true) => { await mark(c, ctx, 13, {...o, point: first, keep: !first}); await mark(c, ctx, 14, {...o, keep: true, point: false}); };
  await ctx.say('wo0402', async () => {
   await open(c, ctx, 'data/components.csv'); await both({});
   await atPhrase(ctx, '설비도 같고 이름도'); await both({cell: 0, shape: 'underline'}); await both({cell: 2, shape: 'underline'}, false);
   await atPhrase(ctx, '뒤쪽 일련번호가'); await both({cell: 4, shape: 'underline'});
   await atPhrase(ctx, '우리 식별자에'); await note(c, 'idf'); await c.emph({note: 3}, {shape: 'underline'});
   await atPhrase(ctx, '일련번호까지 넣어서'); await note(c, 'idf2');
   await atPhrase(ctx, '13행은 3월 11일에'); await both({cell: 6, shape: 'underline'});
   await speechEnd(ctx); await c.note(null);
  }, {at: '둘 다 HYD-02의'});
  const S = c.pen(SEAT);
  await ctx.say('wo0403', async () => {
   await guideHide(G); await S.draw('seat');
   await atPhrase(ctx, '그 자리에 실제로 달린 펌프'); await S.draw('line', 'old', 'oldT');
   await atPhrase(ctx, '사람이 이사를 가도'); await S.draw('now', 'nowT');
   await atPhrase(ctx, '센서가 바로 그 초인종'); await S.draw('as1', 's1', 'as2', 's2');
   await atPhrase(ctx, 'decisions 첫째 줄에'); await note(c, 'dec4');
   await speechEnd(ctx); await c.note(null);
  }, {at: '하나는 펌프가 놓이는 자리고'});
  await ctx.say('wo0404', async () => {
   await S.draw('p1');
   await atPhrase(ctx, '둘째는 실물이라는'); await S.draw('p2');
  }, {at: '첫째는 클래스를'});
  await ctx.say('wo0407', async () => {
   await S.hide(); await guideShow(G);
   await paste(c, ctx, askOf('wo0407'));
   since = await send(c, ctx, '손해 볼 게 없거든요');
  }, {at: '부탁 맨 앞에는'});
 }
 await ctx.say('wo0408', async () => {
  await note(c, 'more8');
  await speechEnd(ctx); await c.note(null);
 }, {at: '둘째 길은 공짜가'});
 const waited = [];
 if (await waitSay(c, ctx, since, 'wo0491')) waited.push('wo0491');
 const r = await answer(c, ctx, since);
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '04c');
 return {segment: 'wo-04c', page: 0, cut, ask: 'R8', aiRequests: since == null ? 0 : 1, answer: r.message, codexMs: r.ms, used: r.used, waitLines: waited, next: 'wo-04d: R8 답 보기 · 고르기 · R9(파일 여섯)'};
};
