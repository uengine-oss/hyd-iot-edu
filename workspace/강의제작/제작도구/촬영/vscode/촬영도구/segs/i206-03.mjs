// 통합 2회차 06편 구간 03: 결과 화면 공간(SPACE='통합02 결과화면 20261111', VP='{width:1843,height:1037,dsf:1.25}')에서 첫 결과 화면.
// 시작: i206-02가 만든 output/result.html(원자료 표). 녹화 전에 그 파일로 이동해 둔다. AI 요청 없음.
// i206-02 끝(0215)에서 「다른 탭에 열어 두었다 · 넘어가 본다」고 말한 뒤 이 공간으로 이어 붙인다.
import {labUi, atPhrase, resultView, heading, cell, inView} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.i206.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에

export default async ctx => {
 const c = await labUi(ctx);
 const view = await resultView(c, ctx, LAB, '원자료');
 await c.installPointer({x: 1300, y: 160});
 await ctx.begin();
 await ctx.say('i206-0301', async () => {
  const h = await heading(c, ctx, '원자료', 'h1'); await c.move(h.x, h.y); await atPhrase(ctx, '원자료 파일마다');
  const t = inView(await heading(c, ctx, '원자료 파일과 행 수')); await c.move(t.x, t.y);
 }, {at: '여러분 PC에서'});
 await ctx.say('i206-0302', async () => {
  for (const [name, phrase] of [['equipment.csv', '설비 대장은'], ['sensors.csv', '센서 목록은'], ['components.csv', '구성 요소는']]) { await atPhrase(ctx, phrase); const q = inView(await cell(c, ctx, name)); await c.move(q.x, q.y); }
 }, {at: '설비 대장은'});
 await ctx.say('i206-0303', async () => { await c.move(view.w - 260, 200); }, {at: 'F5를'});
 return {segment: 'i206-03', view, next: 'i206-04: 웹 VS Code 공간에서 Codex에게 설비 하나의 자료 위치 묻기(가이드 2단계)', aiRequests: 0};
};
