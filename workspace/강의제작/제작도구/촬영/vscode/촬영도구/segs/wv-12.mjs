// 통합 2회차 06-1편 구간 12(첫 페이지 — 웹 VS Code): 맺음 — AGENTS.md를 닫고 Codex 답으로 돌아와, 스키마를 정하며 풀 것 셋을 글상자로 짚는다. Codex를 부르지 않는다.
// 시작: wv-11 끝(앞 탭 AGENTS.md, app이 펴짐, 갖춘 부탁의 답이 남은 Codex 대화). 앞 take: wv-11.
// 끝(06-1 끝 프레임 = 06-2 첫 화면): Codex 답이 남은 VS Code, 앞 탭은 AGENTS.md를 닫은 뒤의 탭, 글상자 없음, 둘째 페이지에는 첫 실행 결과 화면이 맨 위로 열려 있다.
// 대본 wv1201 「Codex가 되물은 것도 결국 이 이야기였죠」는 녹화 답이 되묻지 않았으면 빠진다 — 이 구간은 그 문장에 기대지 않는다.
import {labUi, atPhrase} from './lab-common.mjs';
import {closeTab, note, noteAll, toAnswer, settle} from './wv-common.mjs';

export default async ctx => {
 const c = await labUi(ctx);
 await settle(c, ctx, {active: 'AGENTS.md', top: true, answer: ctx.prev?.answerScroll});   // 녹화 전: 리허설이 닫은 AGENTS.md · 굴린 답을 wv-11 끝으로 되돌린다
 const on = await c.serial(() => ctx.p.evaluate(() => document.querySelector('.tabs-container .tab.active .label-name')?.textContent));
 if (on !== 'AGENTS.md') throw Error('wv-12 시작 상태가 아님 — 앞 탭이 AGENTS.md가 아니라 ' + on + ' (segs/wv-12.mjs)');
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 await ctx.say('wv1201', async () => {
  await closeTab(c, ctx, 'AGENTS.md'); await toAnswer(c, ctx);
  await atPhrase(ctx, '또 하나는'); await note(c, 'todo');
  await atPhrase(ctx, '이 세 군데'); await c.emph(await noteAll(c, ctx), {shape: 'box'});
 }, {at: '이렇게 해서 맨 아래층의'});
 await ctx.say('wv1202', async () => { await c.clearEmph(); }, {at: '그리고 여기까지'});   // 글상자를 둔 채 조작 없음 — 말이 다음 화제로 넘어가 테두리만 걷는다
 await ctx.say('wv1203', async () => { await c.note(null); await toAnswer(c, ctx); }, {at: 'VS Code와 결과 화면은'});
 return {segment: 'wv-12', next: '06-1 끝 — 06-2(wo-*)가 이 화면에서 잇는다', aiRequests: 0};
};
