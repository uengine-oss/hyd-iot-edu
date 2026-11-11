// 통합 2회차 07편 구간 03: 결과 화면 공간(SPACE='통합02 결과화면 20261111', VP='{width:1843,height:1037,dsf:1.25}') — 원자료와 모델.
// 모델 개수 표는 첫 화면 아래로 이어지므로 Sensor 줄이 화면 안에 올 때까지 휠로 내린 뒤 짚는다.
import {labUi, atPhrase, resultView, heading, cell, inView, scrollPageTo} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.i207.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에

export default async ctx => {
 const c = await labUi(ctx);
 const view = await resultView(c, ctx, LAB, '원자료와 모델');
 await c.installPointer({x: 1300, y: 160});
 await ctx.begin();
 await ctx.say('i207-0301', async () => {
  const a = await heading(c, ctx, '원자료 파일과 행 수'); await c.move(a.x, a.y); await atPhrase(ctx, '그 아래 사용할 모델');
  const b = inView(await heading(c, ctx, '사용할 모델')); await c.move(b.x, b.y);
 }, {at: '위의 표는'});
 await ctx.say('i207-0302', async () => {
  await scrollPageTo(c, ctx, () => cell(c, ctx, '종류 Sensor', 1), view.h, 80);   // 끝까지 내려도 Sensor 줄이 y≈925(1037 높이)라 기본 여백 160 안에 오지 않는다
  for (const k of ['Asset', 'Component', 'Part', 'Quantity', 'Sensor']) { await atPhrase(ctx, k + ','); const q = inView(await cell(c, ctx, '종류 ' + k, 1)); await c.move(q.x, q.y); }
 }, {at: '아래로 내려'});
 await ctx.say('i207-0303', async () => { const q = inView(await cell(c, ctx, '노드', 1)); await c.move(q.x, q.y); }, {at: '위 원자료'});
 return {segment: 'i207-03', view, next: 'i207-04: 웹 VS Code 공간에서 랩 DB 준비', aiRequests: 0};
};
