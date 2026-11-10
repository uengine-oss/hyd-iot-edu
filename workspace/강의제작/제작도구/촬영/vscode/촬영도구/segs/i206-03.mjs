// 통합 2회차 06편 구간 03: 결과 화면 공간(SPACE='통합02 결과화면 20261111', VP='{width:1843,height:1037,dsf:1.25}')에서 첫 결과 화면.
// 시작: i206-02가 만든 output/result.html(원자료 표). 녹화 전에 그 파일로 이동해 둔다. AI 요청 없음.
// i206-02 끝(0215)에서 「다른 탭에 열어 두었다 · 넘어가 본다」고 말한 뒤 이 공간으로 이어 붙인다.
import {vscode} from '../ui.mjs';

const PAGE = 'file:///D:/HYD-Practice/i206p-27c52108/ontology-lab/output/result.html';

export default async ctx => {
 const c = await vscode(ctx);
 if (await c.serial(() => ctx.p.url()) !== PAGE) { await c.serial(() => ctx.p.goto(PAGE)); await ctx.sleep(800); }
 const view = await c.serial(() => ctx.p.evaluate(() => ({w: innerWidth, h: innerHeight, dpr: devicePixelRatio, title: document.title, sw: document.documentElement.scrollWidth})));
 if (view.w !== 1843 || Math.abs(view.dpr - 1.25) > 0.01 || view.sw > view.w || !view.title.startsWith('원자료')) throw Error('결과 화면 조건 불일치: ' + JSON.stringify(view));
 const cell = name => c.serial(() => ctx.p.evaluate(name => {
  const td = [...document.querySelectorAll('td')].find(e => e.textContent.trim() === name);
  if (!td) throw Error('표에 없음: ' + name);
  const b = td.getBoundingClientRect(); return {x: b.x + 30, y: b.y + b.height / 2};
 }, name));
 const at = sel => c.serial(() => ctx.p.evaluate(sel => { const b = document.querySelector(sel).getBoundingClientRect(); return {x: b.x + 40, y: b.y + Math.min(b.height / 2, 30)}; }, sel));
 await c.installPointer({x: 1300, y: 160});
 await ctx.begin();
 await ctx.say('i206-0301', async () => {
  const h = await at('h1'); await c.move(h.x, h.y); await ctx.sleep(2500);
  const t = await at('table'); await c.move(t.x, t.y);
 }, {at: '여러분 PC에서'});
 await ctx.say('i206-0302', async () => {
  for (const name of ['equipment.csv', 'sensors.csv', 'components.csv']) { const q = await cell(name); await c.move(q.x, q.y); await ctx.sleep(1400); }
 }, {at: '설비 대장은'});
 await ctx.say('i206-0303', async () => { const q = await at('main'); await c.move(q.x + 400, q.y + 20); }, {at: 'F5를'});
 return {segment: 'i206-03', next: 'i206-04: 웹 VS Code 공간에서 Codex에게 설비 하나의 자료 위치 묻기(가이드 2단계)', aiRequests: 0};
};
