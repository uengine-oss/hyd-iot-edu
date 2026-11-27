// 5분 예시 구간 01f(첫 페이지): Codex가 고친 표 셋을 열어 보고, 터미널에서 python run.py names를 돌린다. Codex를 부르지 않는다.
// 시작: ws-01e 끝(두 번째 답이 다 선 화면, 편집기에 components.csv). 끝: 터미널에 「결과: output/result.html」이 뜬 화면(다음 구간은 둘째 페이지 결과 화면).
// 짚는 줄은 그 take에서 Codex가 고친 실제 줄이다(ws01e-r1 — 식별자 {설비코드}+{구성요소}+{일련번호}, 관계 HAS_UNIT). 다시 찍어 줄이 바뀌면 맞춘다.
import {labUi, atPhrase, em, row, rowSeen, newTerminal, termWait, waitRun, LABS} from './lab-common.mjs';

// 폴더가 접혀 있을 때만 눌러 편다 — 펼쳐진 폴더를 누르면 접힌다(리허설이 남긴 펼침 상태로 ws01f-dry2가 features를 접어 멈췄다).
const unfold = async (c, ctx, name, level) => {
 const open = await c.serial(() => ctx.p.evaluate(({name, level}) => [...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].find(e => e.getAttribute('aria-level') === String(level) && e.innerText.trim() === name)?.getAttribute('aria-expanded'), {name, level}));
 if (open === 'true') { const q = await row(c, name, level); await c.move(q.x, q.y); return; }
 const q = await c.explorerRow(name, level); await c.clickAt(q.x, q.y);
};
const open = async (c, ctx, name, level) => {
 await rowSeen(ctx, name, level);
 const f = await row(c, name, level); await c.clickAt(f.x, f.y); await c.key('Enter');
 await ctx.waitFor('document.querySelector(".tabs-container .tab.active .label-name")?.textContent === ' + JSON.stringify(name));
};

export default async ctx => {
 const c = await labUi(ctx);
 if (await c.serial(() => ctx.p.evaluate(() => !!document.querySelector('.terminal-wrapper')?.checkVisibility()))) throw Error('터미널이 이미 열려 있음 — 이 구간이 연다');
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 await ctx.say('ws0113', async () => {
  await unfold(c, ctx, 'app', 1); await rowSeen(ctx, 'features', 2); await unfold(c, ctx, 'features', 2);
  await atPhrase(ctx, '결정 표에'); await open(c, ctx, 'decisions.csv', 3);
  await c.emph(em.line('구성 요소 자리와 그 실물'), {shape: 'band', phrase: '구성 요소 자리와 그 실물,실물을 클래스로 따로 둔다'});   // 줄이 화면보다 길어(약 1,970px) 줄 전체에 띠를 그으면 화면 밖이다(ws01f-dry1) — 고른 것까지만
  await atPhrase(ctx, '식별자 표에는'); await open(c, ctx, 'design.csv', 3);
  await c.emph(em.line('실물,'), {shape: 'band', phrase: '실물,{설비코드}+{구성요소}+{일련번호}'});
  await atPhrase(ctx, '일련번호를 붙여'); await c.emph(em.line('실물,'), {shape: 'underline', phrase: '{일련번호}'});
  await atPhrase(ctx, '관계 표에도'); await open(c, ctx, 'relations.csv', 3);
  await c.emph(em.line('구성 요소-실물'), {shape: 'band', phrase: '구성 요소-실물,HAS_UNIT,구성 요소,1:N'});
 }, {at: '말만 믿지 말고'});
 await ctx.say('ws0114', async () => {
  await newTerminal(c, ctx);
  await termWait(ctx, 'ontology-lab>');
  await atPhrase(ctx, 'python run.py names를'); await c.typeKeys('python run.py names');
  await atPhrase(ctx, '돌리고'); await c.key('Enter');
 }, {at: '터미널에서'});
 await waitRun(ctx, LABS.ws.dir);
 return {segment: 'ws-01f', next: 'ws-01g: 결과 화면(PAGE=1)', aiRequests: 0};
};
