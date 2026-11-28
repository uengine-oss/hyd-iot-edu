// 통합 2회차 06-1편 구간 04b(둘째 페이지 — PAGE=1): 첫 실행의 결과 화면 — 결론 줄 · 원자료 표 다섯 상자와 행 수 · 표 사이 화살표 · 출발 그림, 그리고 이 화면을 띄워 두라는 말(wv0405).
// 시작: 녹화 전에 resultView로 output/result.html을 맨 위에서 연다(wv-04a가 만든 결과). 앞 take: wv-04a(화살표가 앞 구간이 끝난 자리에서 시작한다 — 촬영준비 길 6).
// 끝: 같은 결과 화면을 맨 위로 올려 둔 채(굴리기는 wv0404 말이 끝난 뒤 하고 말하지 않는다 — wv0405는 그 화면 위에서 말만 한다), 강조 없음.
// 결과 화면의 그림은 노드 위에 마우스가 서면 속성 풍선이 뜨고 나머지가 흐려진다 — 화살표는 노드가 아닌 자리(freeAt)에 두고, 굴리기 전에는 본문 밖 여백으로 옮긴다. 끝에 풍선이 떠 있으면 멈춘다.
// SVG 글자(상자 이름 · 행 수)는 글자 자리를 잴 수 없어 요소 상자(boxOf)로 짚는다.
import {labUi, atPhrase, resultView} from './lab-common.mjs';
import {LAB, RESULT_TITLE, boxOf, freeAt, faint, speechEnd, snap} from './wv-common.mjs';

const S1 = 'main > section:nth-of-type(1)', S2 = 'main > section:nth-of-type(2)';   // 「원자료 표가 이어지는 칸」 · 「출발 그림 …」
const node = (sec, id, part = 'rect.p') => sec + ' svg.g g.n[data-id="' + id + '"] ' + part;   // rect.p = 상자, text.t = 이름, text.s = 행 수

export default async ctx => {
 const c = await labUi(ctx);
 const view = await resultView(c, ctx, LAB, RESULT_TITLE);
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 // 본문 밖 왼쪽 여백(노드가 없는 자리) — 굴리기 전에 화살표를 여기로 옮긴다
 const margin = await c.serial(() => ctx.p.evaluate(() => { const m = document.querySelector('main').getBoundingClientRect(); return {x: Math.max(30, m.x / 2), y: innerHeight * 0.55}; }));
 const scroll = async (dy, done) => {
  await c.move(margin.x, margin.y); await c.gate();
  for (let k = 0; k < 12 && !(await done()); k++) { await c.serial(() => ctx.p.mouse.wheel(0, dy)); await ctx.sleep(450); }
  if (!(await done())) throw Error(ctx.cueId + ': 결과 화면을 굴려도 원하는 자리에 오지 않음 (segs/wv-04b.mjs)');
 };
 // 노드 하나(상자 b)를 짚을 때 화살표 자리 — 그 노드 둘레에서 노드가 아닌 곳
 const nodeAt = async (sec, id) => freeAt(c, ctx, (await boxOf(c, ctx, node(sec, id))).box);
 await ctx.begin();

 await ctx.say('wv0402', async () => {
  const v = await boxOf(c, ctx, '.verdict strong'), left = {x: v.box[0] - 26, y: v.box[1] + v.box[3] / 2 - 6};
  await c.emph({sel: '.verdict strong'}, {shape: 'underline', at: left});
  await atPhrase(ctx, '원자료는 보전팀이'); await c.emph({sel: '.verdict strong'}, {shape: 'box', phrase: '원자료', at: left});
  await snap(ctx, 'wv0402');
 }, {at: '맨 위에 원자료 표'});
 await ctx.say('wv0403', async () => {
  await c.emph(await boxOf(c, ctx, node(S1, 'equipment.csv', 'text.s')), {shape: 'underline', at: await nodeAt(S1, 'equipment.csv')});
  await snap(ctx, 'wv0403');
 }, {at: '설비 대장을 보면'});
 await ctx.say('wv0481', async () => {
  for (const [f, at] of [['components.csv', null], ['sensors.csv', '센서 표'], ['spare_parts.csv', '부품 표예요']]) {
   if (at) await atPhrase(ctx, at);
   await c.emph(await boxOf(c, ctx, node(S1, f)), {shape: 'box', at: await nodeAt(S1, f)});
   await c.emph(await boxOf(c, ctx, node(S1, f, 'text.s')), {shape: 'underline', keep: true, point: false});   // 행 수에도 밑줄(읽지 않는다)
  }
  await snap(ctx, 'wv0481-spare');
  await atPhrase(ctx, '남은 하나는'); await c.emph(await boxOf(c, ctx, node(S1, 'part_aliases.csv')), {shape: 'box', at: await nodeAt(S1, 'part_aliases.csv')});
  await snap(ctx, 'wv0481-alias');
  await atPhrase(ctx, '상자 사이의 화살표는');
  const arrows = await c.serial(() => ctx.p.evaluate(s => ({rects: [...document.querySelectorAll(s + ' svg.g path.l')].map(e => { const b = e.getBoundingClientRect(); return [b.x, b.y, Math.max(b.width, 1), Math.max(b.height, 1)]; })}), S1));
  if (!arrows.rects.length) throw Error('wv0481: 결과 화면 그림에 화살표가 없음 (segs/wv-04b.mjs)');
  const all = arrows.rects.reduce((a, r) => [Math.min(a[0], r[0]), Math.min(a[1], r[1]), Math.max(a[2], r[0] + r[2]), Math.max(a[3], r[1] + r[3])], [Infinity, Infinity, -Infinity, -Infinity]);
  await faint(c, ctx, arrows, {shape: 'box', at: await freeAt(c, ctx, [all[0], all[1], all[2] - all[0], all[3] - all[1]])});   // 흐린 테두리(대본) — 화살표의 글자는 읽지 않는다
  await snap(ctx, 'wv0481-arrows');
 }, {at: '나머지 상자는'});
 await ctx.say('wv0404', async () => {
  // 「출발 그림」 칸이 화면 안에 다 들어올 때까지 내린다
  await scroll(240, () => c.serial(() => ctx.p.evaluate(s => { const b = document.querySelector(s).getBoundingClientRect(); return b.bottom <= innerHeight - 12 || innerHeight + scrollY >= document.documentElement.scrollHeight - 2; }, S2)));
  const h = await boxOf(c, ctx, S2 + ' h3'), hLeft = {x: h.box[0] - 26, y: h.box[1] + h.box[3] / 2 - 6};
  await atPhrase(ctx, '출발 그림이라는'); await c.emph({sel: S2 + ' h3'}, {shape: 'underline', at: hLeft});   // 제목 글자 아래만(요소 상자는 칸 폭 전체다)
  await c.emph(await boxOf(c, ctx, S2 + ' svg.g'), {shape: 'box', keep: true, point: false});
  await snap(ctx, 'wv0404-title');
  await atPhrase(ctx, '그 json 파일을'); await c.emph({sel: S2 + ' h3'}, {shape: 'underline', phrase: 'data/relationships.json', at: hLeft});
  for (const [id, at] of [['n0', '유압 파워팩 한 대에'], ['n1', '오일 쿨러가'], ['n2', '유온 센서가']]) {
   await atPhrase(ctx, at); await c.emph(await boxOf(c, ctx, node(S2, id, 'text.t')), {shape: 'underline', at: await nodeAt(S2, id)});
  }
  await snap(ctx, 'wv0404-sensor');
  await atPhrase(ctx, '표에 있는 설비를 전부'); { const g = await boxOf(c, ctx, S2 + ' svg.g'); await faint(c, ctx, g, {shape: 'box', at: await freeAt(c, ctx, g.box, ['below', 'right', 'left'])}); }   // 흐린 테두리(대본)
  await snap(ctx, 'wv0404-all');
  await speechEnd(ctx);
  await scroll(-480, () => c.serial(() => ctx.p.evaluate(() => scrollY <= 0)));   // 맨 위로 올려 둔다(말하지 않는다)
 }, {at: '화면을 더 내려 보면'});
 await ctx.say('wv0405');   // 「이 결과 화면은 닫지 말고 …」 — 결과 화면 위에서 말만 한다(조작 없음). VS Code로 돌아오는 말은 wv0406(wv-04c)
 const tip = await c.serial(() => ctx.p.evaluate(() => { const t = document.getElementById('tip'); return !!t && getComputedStyle(t).display !== 'none'; }));
 if (tip) throw Error('wv-04b 끝에 결과 화면의 속성 풍선이 떠 있음 — 화살표가 노드 위에 섰다 (segs/wv-04b.mjs)');
 return {segment: 'wv-04b', view, next: 'wv-04c(첫 페이지, 앞 take는 wv-04a): VS Code로 돌아오기', aiRequests: 0};
};
