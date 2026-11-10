// 통합 2회차 07편 구간 03: 결과 화면 공간(SPACE='통합02 결과화면 20261111', VP='{width:1843,height:1037,dsf:1.25}') — 원자료와 모델.
// 모델 개수 표는 첫 화면 아래(1843×1037에서 Asset 줄 y≈1009)에 있으므로 휠로 내린 뒤 짚는다.
import {vscode} from '../ui.mjs';
import {PAGE, cell} from './i207-common.mjs';

export default async ctx => {
 const c = await vscode(ctx);
 await c.serial(() => ctx.p.goto(PAGE)); await ctx.sleep(800);   // 녹화 전: 같은 주소여도 방금 쓴 결과 파일을 다시 읽는다(앞 판 화면이 남아 있었다)
 await c.serial(() => ctx.p.evaluate(() => scrollTo(0, 0)));
 const view = await c.serial(() => ctx.p.evaluate(() => ({w: innerWidth, h: innerHeight, dpr: devicePixelRatio, title: document.title, sw: document.documentElement.scrollWidth})));
 if (view.w !== 1843 || Math.abs(view.dpr - 1.25) > 0.01 || view.sw > view.w || !view.title.startsWith('원자료와 모델')) throw Error('결과 화면 조건 불일치: ' + JSON.stringify(view));
 const h3 = text => c.serial(() => ctx.p.evaluate(text => { const e = [...document.querySelectorAll('h3')].find(x => x.textContent.startsWith(text)); if (!e) throw Error('제목 없음: ' + text); const b = e.getBoundingClientRect(); return {x: b.x + 40, y: b.y + b.height / 2}; }, text));
 const inView = q => { if (q.y < 0 || q.y > view.h - 10) throw Error('화면 밖 대상: ' + JSON.stringify(q)); return q; };
 await c.installPointer({x: 1300, y: 160});
 await ctx.begin();
 await ctx.say('i207-0301', async () => {
  const a = await h3('원자료 파일과 행 수'); await c.move(a.x, a.y); await ctx.sleep(2600);
  const b = inView(await h3('사용할 모델')); await c.move(b.x, b.y);
 }, {at: '위의 표는'});
 await ctx.say('i207-0302', async () => {
  await c.gate(); await c.serial(() => ctx.p.mouse.wheel(0, 360)); await ctx.sleep(700);
  for (const name of ['종류 Asset', '종류 Component', '종류 Part', '종류 Quantity', '종류 Sensor']) { const q = inView(await cell(c, ctx, name, 1)); await c.move(q.x, q.y); await ctx.sleep(1300); }
 }, {at: '아래로 내려'});
 await ctx.say('i207-0303', async () => { const q = inView(await cell(c, ctx, '노드', 1)); await c.move(q.x, q.y); }, {at: '위 원자료'});
 return {segment: 'i207-03', next: 'i207-04: 웹 VS Code 공간에서 랩 DB 준비', aiRequests: 0};
};
