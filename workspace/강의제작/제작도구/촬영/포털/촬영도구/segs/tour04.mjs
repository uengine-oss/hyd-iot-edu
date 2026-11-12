// 통합 1회차 04 포털 둘러보기(다시 찍을 판) 구간 모듈. 큐는 ../통합_01_04_포털둘러보기_큐.json, 조작은 map.mjs가 한다.
// 구간 1(이어 찍기가 아닐 때)만 녹화 밖에서 실시간 모니터링을 한 번 열어 그래프를 데워 둔다(4단계에서 빈 틀이 오래 보이지 않게).
// 그 뒤 map.mjs가 포털 홈을 새로 열고 「나」를 비운다.
import {seg as mapSeg} from './map.mjs';

const PORTAL = 'http://127.0.0.1:8088/';

export async function seg(ctx, n) {
 if (String(n) === '1' && !ctx.resuming) {
  const p = ctx.p, q = (fn) => ctx.serial(fn);
  await q(() => p.goto(PORTAL, {waitUntil: 'domcontentloaded', timeout: 30000}));
  await q(() => p.waitForSelector('.rail nav button[data-tab="trends"]', {timeout: 30000}));
  await q(() => p.evaluate(() => document.querySelector('.rail nav button[data-tab="trends"]').click()));
  await ctx.sleep(10000);
 }
 return mapSeg(ctx, n);
}
