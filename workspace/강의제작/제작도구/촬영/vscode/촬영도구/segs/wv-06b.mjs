// 통합 2회차 06-1편 구간 06b(첫 페이지 — 웹 VS Code): 막연한 부탁의 끝난 답을 위에서부터 보고(제목 · 메모 줄 링크), 보낸 부탁의 「정리」와 답 끝 문장을 짚은 뒤, 블랙박스 펜 그림. Codex를 다시 부르지 않는다(촬영준비 길 9).
// 시작: wv-06a 끝(답이 다 선 화면 — 패널이 답 끝으로 굴러가 있다). 앞 take: wv-06a. 끝: 같은 답(굴린 자리 그대로), 강조 · 펜 그림 없음.
// 답은 녹화할 때마다 다르다 — 아래 표 A만 녹화한 답(wv-06a take의 timing.json result.answer와 그 화면)에 맞춰 고친다. 찾는 꼴은 wv-common.mjs 「Codex 패널」 머리말.
// 답에 그 요소가 없거나 여럿이면 그 큐 id를 대며 멈춘다(건너뛰지 않는다). 대본도 「Codex 답에 맞출 큐」대로 그 답의 사실에 맞춘다(wv0603 · wv0604 — 줄 링크 · 끝 문장이 없는 답이면 그 문장과 이 표의 그 줄을 함께 뺀다).
import {labUi, atPhrase} from './lab-common.mjs';
import {ASK_VAGUE, BLACKBOX, cxBox, cxRects, cxScroll, settle, answerScroll, speechEnd} from './wv-common.mjs';

// ── 녹화 답에 맞출 표(이 표만 고친다). 지금 값은 길뚫기 답(판정/길뚫기/06-1_4-2_막연한부탁.답.md)의 글이다 ──
const A = {
 top: ['h2', '현장 메모 정리'],                                   // 답의 맨 위 제목 — 답을 맨 위로 올리는 자리
 heads: [['h3', '받은 자료', '받은 자료가 뭐고'], ['h3', '설비별로 알아둘 점', '설비마다 알아 둘 점']],   // wv0603 제목들 [CSS, 든 글, 밑줄을 긋는 말]
 link: ['span.break-words', '현장 메모 3–6'],                      // wv0603 「몇째 줄을 보고」 — 문단 끝의 메모 줄 링크(첫 것)
 last: ['*', '이번 요청은 메모의 내용 정리로 처리했습니다'],        // wv0604 「답 맨 끝 문장을」 — 그 문장(띠)
};
const SENT = ['*', ASK_VAGUE, 'last'];   // 보낸 부탁 글(패널 위 대화 제목에도 같은 글이 있어 아래쪽 말풍선을 고른다)

export default async ctx => {
 const c = await labUi(ctx);
 await cxBox(c, ctx, A.top);   // 시작 화면에 그 답이 있는지 먼저 본다
 await settle(c, ctx, {answer: 'end'});   // 녹화 전: 리허설이 굴린 답을 wv-06a 끝(답 끝까지 내려간 패널)으로 되돌린다
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 await ctx.say('wv0603', async () => {
  await cxScroll(c, ctx, A.top, 0.02);   // 끝난 답을 위에서부터 본다
  for (const [css, has, at] of A.heads) { await atPhrase(ctx, at); await cxScroll(c, ctx, [css, has], 0.3, true); await c.emph(await cxRects(c, ctx, [css, has]), {shape: 'underline'}); }
  await atPhrase(ctx, '몇째 줄을 보고'); await cxScroll(c, ctx, A.link, 0.3, true); await c.emph(await cxRects(c, ctx, A.link), {shape: 'underline'});
 }, {at: '한 줄 보냈는데'});
 await ctx.say('wv0604', async () => {
  await cxScroll(c, ctx, SENT, 0.1, true);   // 보낸 부탁이 보이는 데까지 올린다
  await atPhrase(ctx, '정리라는 말은'); await c.emph(await cxRects(c, ctx, SENT, '정리'), {shape: 'underline'});
  await atPhrase(ctx, '답 맨 끝 문장을'); await cxScroll(c, ctx, A.last, 0.55, true); await c.emph(await cxRects(c, ctx, A.last, A.last[1]), {shape: 'band'});
 }, {at: '제가 한 말은'});
 await ctx.say('wv0605', async () => { await c.clearEmph(); }, {at: '그러니 이게'});
 const box = c.pen(BLACKBOX);
 await ctx.say('wv0606', async () => {
  await box.draw('ask');
  await atPhrase(ctx, '어느 행을 고쳤는지'); await box.draw('in', 'bb');
  await atPhrase(ctx, '엉뚱한 답이 나와도'); await box.draw('ex', 'out');
  await atPhrase(ctx, '블랙박스라고'); await box.draw('name');
  await speechEnd(ctx); await box.hide();
 }, {at: '표를 알아서'});
 return {segment: 'wv-06b', next: 'wv-07: AI를 어디에 두고 일할까', aiRequests: 0, answerScroll: await answerScroll(c, ctx)};
};
