// 실전 2회차 08편 구간 03: 결과 화면 공간(SPACE='통합02 결과화면 20261111', VP='{width:1843,height:1037,dsf:1.25}') — 원자료와 모델 개수.
// 모델 개수 표는 첫 화면 아래로 이어지므로 휠로 내린 뒤 짚는다.
import {labUi, atPhrase, resultView, heading, inView, tableCell, scrollPageTo} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.p208.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에

export default async ctx => {
 const c = await labUi(ctx);
 const view = await resultView(c, ctx, LAB, '원자료와 모델');
 const at = key => tableCell(c, ctx, key, 1, 2);
 await c.installPointer({x: 1300, y: 160});
 await ctx.begin();
 await ctx.say('p208-0301', async () => {
  const a = await heading(c, ctx, '원자료 파일과 행 수'); await c.move(a.x, a.y); await atPhrase(ctx, '그 아래 사용할');
  const b = inView(await heading(c, ctx, '사용할 모델')); await c.move(b.x, b.y);
 }, {at: '위 표는'});
 await ctx.say('p208-0302', async () => {
  await scrollPageTo(c, ctx, () => at('종류 Supplier'), view.h, 70);   // 표 끝 줄이라 페이지 끝까지 내려도 아래쪽에 남는다
  const a = inView(await at('종류 Supplier')); await c.move(a.x, a.y); await atPhrase(ctx, 'SUPPLIES가');
  const b = inView(await at('관계 SUPPLIES')); await c.move(b.x, b.y);
 }, {at: '아래로 내려'});
 await ctx.say('p208-0303', async () => {
  const a = inView(await at('노드')); await c.move(a.x, a.y); await atPhrase(ctx, '관계 326개가');
  const b = inView(await at('관계')); await c.move(b.x, b.y);
 }, {at: '여기 노드'});
 return {segment: 'p208-03', view, next: 'p208-04: 웹 VS Code 공간에서 랩 DB 준비', aiRequests: 0};
};
