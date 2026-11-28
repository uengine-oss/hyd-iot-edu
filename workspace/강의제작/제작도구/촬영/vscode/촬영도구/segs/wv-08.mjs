// 통합 2회차 06-1편 구간 08(첫 페이지 — 웹 VS Code): 갖춘 부탁 — 새 대화를 열고, 부탁을 세 대목으로 붙여 넣으며 대목마다 밑줄로 짚고, 보낸 뒤 답이 끝날 때까지 끝에 붙인 말의 까닭을 말한다(자르지 않는다 — 영상 V-14).
// 시작: wv-07 끝(막연한 부탁의 답이 남은 대화). 앞 take: wv-07. 끝: 갖춘 부탁의 답이 다 선 화면(그 답을 보는 말은 다음 구간 wv-09a).
// 실제 요청을 보낸다 — 리허설도 같다(CODEX_HOME=… ./run.sh dry|rec …, 촬영준비 길 9). 끝난 답은 돌려주는 값 answer로 timing.json result에 남고, wv-09a · wv-09b 머리의 표와 대본 9장 「Codex 답에 맞출 큐」를 그 답으로 맞춘다.
// wv0806이 끝났는데 답이 아직이면 기다림 말 wv0891 · wv0892를 차례로 하고(waitLines), 그래도 남는 기다림은 말 없이 둔다. 답이 먼저 끝나면 wv0806을 마친 뒤 끝낸다.
// 보낸 뒤 끝에 붙인 말은 편집기 위 글상자로 짚는다 — Codex가 답을 쓰는 동안 패널이 저절로 굴러가, 보낸 말풍선을 짚은 띠가 엉뚱한 줄 위에 남았다(wv08-b1).
import {labUi, atPhrase, em, codexEl, codexFocus, codexSubmit, codexWait, waitLines} from './lab-common.mjs';
import {ASK1, ASK2, ASK3, PART, codexPaste, cxRects, note, speechEnd} from './wv-common.mjs';

const INPUT = ['[contenteditable=true]', ASK1.slice(0, 12)];   // 글을 넣은 입력칸

export default async ctx => {
 const c = await labUi(ctx);
 await codexEl(c, ctx, {label: 'New chat'});   // 새 대화 단추가 보이는지 먼저 본다
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 let since = 0;
 await ctx.say('wv0801', async () => {
  const b = await codexEl(c, ctx, {label: 'New chat'});
  await c.emph(em.box({x: b.x - b.w / 2, y: b.y - b.h / 2, w: b.w, h: b.h}), {shape: 'box'});
  await atPhrase(ctx, '대화를 새로 열게요'); await c.clickAt(b.x, b.y);
  const blank = t => t.includes('Ask Codex anything') && !t.includes('Worked for');   // 빈 새 대화: 입력칸 안내 글이 있고 앞 답의 「Worked for Ns」 줄이 없다
  for (let k = 0; !blank(await c.serial(() => ctx.p.text())); k++) { if (k >= 20) throw Error('wv0801: 새 대화를 눌러도 빈 대화가 뜨지 않음 (segs/wv-08.mjs)'); await ctx.sleep(500); }
 }, {at: '새 대화 단추를'});
 await ctx.say('wv0802', async () => {
  await codexFocus(c, ctx); await codexPaste(c, ctx, ASK1);
  await atPhrase(ctx, '보전팀이 자주 묻는 것에'); await c.emph(await cxRects(c, ctx, INPUT, PART.use), {shape: 'underline'});
 }, {at: '맨 먼저 뭘 하려는지부터'});
 await ctx.say('wv0803', async () => {
  await codexPaste(c, ctx, ' ' + ASK2);
  for (const [k, at] of [['files', '메모에 적힌 파일들이'], ['rows', '표마다 몇 행이고'], ['links', '표끼리는 어떤 칸으로']]) { await atPhrase(ctx, at); await c.emph(await cxRects(c, ctx, INPUT, PART[k]), {shape: 'underline'}); }
  await atPhrase(ctx, '아까 결과 화면에서 이미 봤죠');   // 첫째 · 둘째 대목 밑줄을 한 번 더 켠다
  await c.emph(await cxRects(c, ctx, INPUT, PART.files), {shape: 'underline'}); await c.emph(await cxRects(c, ctx, INPUT, PART.rows), {shape: 'underline', keep: true, point: false});
  await atPhrase(ctx, '엇갈리게 적힌 곳도'); await c.emph(await cxRects(c, ctx, INPUT, PART.mixed), {shape: 'underline'});
 }, {at: '이어서 알고 싶은 걸'});
 await ctx.say('wv0804', async () => {
  await codexPaste(c, ctx, ' ' + ASK3);
  for (const [k, at] of [['form', '어느 표의 몇 행이'], ['keep', '파일은 바꾸지 말 것'], ['ask', '먼저 물어볼 것']]) { await atPhrase(ctx, at); await c.emph(await cxRects(c, ctx, INPUT, PART[k]), {shape: 'underline'}); }
  await atPhrase(ctx, '보내겠습니다'); since = await codexSubmit(c, ctx);
 }, {at: '여기에 답을 어떤 꼴로'});
 // 끝에 붙인 말은 보낸 말풍선이 아니라 편집기 위 글상자(NOTE.tail)로 짚는다 — Codex가 답을 쓰는 동안 패널이 저절로 굴러가 말풍선 위 띠가 엉뚱한 줄에 남았다(wv08-b1).
 await ctx.say('wv0805', async () => {
  await atPhrase(ctx, '끝에 붙인 말들을'); await note(c, 'tail');
  await atPhrase(ctx, '행을 예로 들고 개수를'); await c.emph({note: 1}, {shape: 'band'});
 }, {at: '이번에는 표 다섯 개를'});
 await ctx.say('wv0806', async () => {
  await c.emph({note: 2}, {shape: 'band'});
  await atPhrase(ctx, '모르는 것은 먼저'); await c.emph({note: 3}, {shape: 'band'});
  await speechEnd(ctx); await c.clearEmph(); await c.note(null);
 }, {at: '파일을 바꾸지 말라고'});
 const waited = await waitLines(ctx, since, ['wv0891', 'wv0892']);
 const r = await codexWait(ctx, since);
 if (ctx.rehearsal) { await c.serial(() => ctx.p.screenshot({path: ctx.out + '/답.png'})); await ctx.fs.writeFile(ctx.out + '/답.md', r.message ?? ''); }
 return {segment: 'wv-08', next: 'wv-09a: 답을 원자료와 맞춰 보기', aiRequests: 1, answer: r.message, codexMs: r.ms, used: r.used, waitLines: waited};
};
