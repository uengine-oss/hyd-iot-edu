// 통합 2회차 06-1편 구간 06b: 막연한 부탁의 끝난 답을 위에서부터 보며, 말이 짚는 자리(기준일 · 행 수 · 설비 표 · 제목 · 메모 줄 링크)를 차례로 강조한다. Codex를 다시 부르지 않는다(촬영준비 길 9).
// 시작: wv-06a 끝(답이 다 선 화면 — 패널이 답 끝으로 굴러가 있다). 앞 take를 주어 화살표를 잇는다: ./run.sh rec <이름> wv-06b.mjs <06a take>.
// 지금 판은 맛보기(영상 길 14의 대표 구간)라 wv0603까지다. 본 촬영 때 wv0604~0606을 이 구간에 잇는다.
// 답은 웹뷰라 바깥 문서에서 잴 수 없어, 프레임을 따라 들어가 그 자리의 요소를 글로 찾아 잰다(lab-common.mjs codexBoxes). 찾는 글은 이 take의 답(wv06a-r3)에서 골랐고, 답이 바뀌면 그 답에 맞춰 고친다.
import {labUi, atPhrase, codexBoxes, codexScrollInto, em} from './lab-common.mjs';

// 그 글이 든 요소가 정확히 하나여야 한다(여럿이거나 없으면 큐 id를 대며 멈춘다).
const one = async (c, ctx, css, has) => {
 const l = await codexBoxes(c, ctx, css, has);
 if (l.length !== 1) throw Error(ctx.cueId + ': Codex 답에서 「' + has + '」이 든 ' + css + '이 ' + l.length + '개 (segs/wv-06b.mjs)');
 return l[0];
};

export default async ctx => {
 const c = await labUi(ctx);
 await one(c, ctx, 'h2', '현장 메모 정리');   // 시작 화면에 그 답이 있는지 먼저 본다
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 await ctx.say('wv0603', async () => {
  await codexScrollInto(c, ctx, () => one(c, ctx, 'h2', '현장 메모 정리'), 0.02);
  await atPhrase(ctx, '기준일이'); await c.emph(em.box(await one(c, ctx, 'strong', '기준일은')), {shape: 'underline'});
  await atPhrase(ctx, '받은 표가'); await c.emph(em.box(await one(c, ctx, 'li', '원자료 CSV는')), {shape: 'band'});
  await atPhrase(ctx, '설비마다'); await c.emph(em.box(await one(c, ctx, 'table', 'HYD-01')), {shape: 'box'});
  await atPhrase(ctx, '제목까지'); await c.emph(em.box(await one(c, ctx, 'h3', '설비 구성')), {shape: 'underline'});
  await c.emph(em.box(await one(c, ctx, 'h3', '자료와 표기상 주의점')), {shape: 'underline', keep: true});
  await atPhrase(ctx, '몇째 줄을'); await c.emph(em.box(await one(c, ctx, 'span.break-words', '현장 메모 3, 6행')), {shape: 'underline'});
 }, {at: '답이 나왔네요'});
 return {segment: 'wv-06b', next: '맛보기 끝(본 촬영은 wv0604로)', aiRequests: 0};
};
