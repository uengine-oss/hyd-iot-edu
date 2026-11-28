// 06-2 구간 01(첫 페이지 — 웹 VS Code): 여는 말과 설계 흐름 — 세 걸음 그림(06-1 wv0109와 같은 세 칸) → 다섯 칸 설계 흐름 그림 → 작게 남기는 길잡이. Codex 부탁 없음.
// 시작: 06-1이 끝난 화면 그대로(같은 촬영 폴더, Codex 답이 남은 대화, 터미널 열림, output/ 있음) — 06-1 마지막 구간 바로 뒤에 찍는다. 끝: 같은 화면에 길잡이(탐색기 아래)가 떠 있다(합성 때 걷는 모습은 cut에서 자른다).
import {atPhrase} from './lab-common.mjs';
import {ui, LAB, guideDef, guideShow, seamOut, keepEnd, unfold, label, STEPS2, FLOW} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const v = await c.serial(() => ctx.p.evaluate(() => ({terminal: !!document.querySelector('.terminal-wrapper')?.checkVisibility(), root: document.querySelector('.pane-header[aria-label^="Explorer Section:"]')?.innerText ?? ''})));
 const t = await c.serial(() => ctx.p.text());
 if (!v.terminal || !v.root.toLowerCase().includes('ontology-lab') || t.includes('Ask Codex anything') || !(await ctx.fs.stat(LAB + '/output/result.html').then(() => true, () => false)))
  throw Error('06-1이 끝난 화면이 아님(터미널 · 06-1 Codex 대화 · output/) — 06-1 마지막 구간 바로 뒤에 찍는다: ' + JSON.stringify(v));
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 const S = c.pen(STEPS2), F = c.pen(FLOW);
 await ctx.say('wo0101', async () => {
  await S.draw('s1', 'a12', 's2', 'a23', 's3');
  await atPhrase(ctx, '이제 둘째 걸음으로'); await S.ring('s2');
  await atPhrase(ctx, '보전팀이 물으면'); await S.draw('goal');
 }, {at: '세 걸음 가운데 첫 걸음'});
 await ctx.say('wo0102', async () => {
  await S.hide();
  await atPhrase(ctx, '역량 질문을 세웁니다'); await F.draw('f1');
  await atPhrase(ctx, '낱말을 클래스와 속성'); await F.draw('a12', 'f2');
  await atPhrase(ctx, '가른 것을 표에 적어요'); await F.draw('a23', 'f3');
  await atPhrase(ctx, '그 표에 맞춰 봅니다'); await F.draw('a34', 'f4');
  await atPhrase(ctx, '실제로 물어봅니다'); await F.draw('a45', 'f5');
  await atPhrase(ctx, '물었는데 막히면'); await F.draw('back', 'backT');
  await atPhrase(ctx, '표를 적을 자리는'); await unfold(c, ctx, 'app', 1); await c.emph(label('features'), {shape: 'box'});
 }, {at: '그림으로 그리면 이래요'});
 const G = {where: 'vs', items: [], ring: null, def: guideDef('vs'), g: c.pen(guideDef('vs')), shown: false};
 await ctx.say('wo0103', async () => {
  await F.ring('f5');   // ⑤ 칸을 「점선으로 바꿔」 — 그림 층에 점선이 없어 「지금 여기」 동그라미로 짚는다(판정 문서 「조작 칸대로 하기 어려운 큐」)
  await atPhrase(ctx, '파일로 먼저 해 봅니다'); await F.draw('fileT');
  await atPhrase(ctx, '이 그림은 화면 위에 작게'); await F.hide(); await guideShow(G, false);   // 「화면 위쪽에 작게」 — 길잡이는 탐색기 아래 빈 곳에 둔다(판정 문서)
 }, {at: '넣어서 물어보기는'});
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '01');
 return {segment: 'wo-01', page: 0, cut, next: 'wo-02a: 역량 질문 · 기대 답 자리 · 첫 부탁(R1)', aiRequests: 0};
};
