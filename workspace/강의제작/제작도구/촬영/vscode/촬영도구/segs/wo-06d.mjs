// 06-2 구간 06d(첫 페이지): R14 답의 근거 줄(메모 22행) → 메모 22행 뒤 문장 → relations.csv 구성 요소 → 부품의 「없음」 → output 폴더의 모델 파일 둘(schema.json의 Sensor required · optional의 limit, graph.json 첫 노드) · 길잡이 ③. Codex 부탁 없음.
// 시작: wo-06c 끝(R14 답이 선 화면, 앞 take를 준다). 끝: graph.json이 열린 화면. 답을 짚는 글은 FIND.r14Line, 속성 이름은 PICK.limit.
import {atPhrase} from './lab-common.mjs';
import {ui, LAB, QE, PICK, guideIn, guideRing, seamOut, keepEnd, open, mark, unfold, label, lineHas, cx, cxMark} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const s = (await ctx.fs.readFile(LAB + '/output/schema.json', 'utf8')).replace(/\r/g, '').split('\n');
 const sensor = s.findIndex(x => x.trim() === '"Sensor": {') + 1;
 if (!sensor) throw Error('output/schema.json에 "Sensor" 클래스가 없음 — wo-06a의 python run.py parts를 본다');
 const req = s.findIndex((x, i) => i >= sensor && x.trim() === '"required": {') + 1, opt = s.findIndex((x, i) => i >= sensor && x.trim() === '"optional": {') + 1;
 const lim = s.findIndex((x, i) => i >= opt && x.trim().startsWith('"' + PICK.limit + '":')) + 1;
 if (!req || !opt || !lim) throw Error('schema.json의 Sensor에서 required · optional · "' + PICK.limit + '"를 찾지 못함 — PICK.limit을 Codex가 지은 이름으로');
 await cx(c, ctx, 'r14Line');
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm2'});
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 await ctx.say('wo0604', async () => {
  await cxMark(c, ctx, 'r14Line', 'underline');
  await atPhrase(ctx, '열어 보면'); await open(c, ctx, 'data/field_notes.md'); await mark(c, ctx, 22, {sub: '구동 모터는 교체 부품을 따로 두지 않아 교체부품 칸이 비어 있습니다', shape: 'underline'});
  await atPhrase(ctx, '관계 표에 일단 둔'); await open(c, ctx, 'app/features/relations.csv'); await mark(c, ctx, await lineHas(ctx, 'app/features/relations.csv', PICK.relPart), {cell: 5, shape: 'underline'});
 }, {at: '메모 22행을'});
 await ctx.say('wo0605', async () => {
  await unfold(c, ctx, 'output', 1); await c.emph(label('schema.json'), {shape: 'box'}); await c.emph(label('graph.json'), {shape: 'box', keep: true, point: false});
  await atPhrase(ctx, 'schema에는'); await open(c, ctx, 'output/schema.json');
  await atPhrase(ctx, '센서 쪽을 보면'); await mark(c, ctx, req, {to: opt - 1});
  await atPhrase(ctx, '비워도 되는 속성 쪽에'); await mark(c, ctx, lim, {shape: 'underline'});
  await atPhrase(ctx, 'graph에는'); await open(c, ctx, 'output/graph.json');
  const g = (await ctx.fs.readFile(LAB + '/output/graph.json', 'utf8')).replace(/\r/g, '').split('\n');
  const a = g.findIndex(x => x.trim() === '"id": "HYD-01",') + 1, b = g.findIndex((x, i) => i >= a && x.trim().startsWith('"status":')) + 1;
  if (!a || !b) throw Error('wo0605: graph.json 첫 노드의 "id": "HYD-01" ~ "status"를 찾지 못함 (segs/wo-06d.mjs)');
  await atPhrase(ctx, '맨 위에 HYD-01 한 대가'); await mark(c, ctx, a, {to: b});
  await atPhrase(ctx, '이론에서 나눠 본'); await guideRing(G, 'm3');
 }, {at: 'output 폴더에'});
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '06d');
 return {segment: 'wo-06d', page: 0, cut, aiRequests: 0, next: 'wo-07a: 넣기 전 검증 python run.py check'};
};
