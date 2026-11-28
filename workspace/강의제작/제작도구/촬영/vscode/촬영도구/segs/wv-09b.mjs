// 통합 2회차 06-1편 구간 09b(첫 페이지 — 웹 VS Code): 답이 적은 TS1의 행 번호를 센서 표에서 직접 찾아가 맞는 것을 보고, 답이 댄 메모 줄을 현장 메모에서 찾아가 번지수가 어긋난 것을 보인 뒤, 답 끝의 「판단이 필요하다」를 짚는다. Codex를 다시 부르지 않는다(촬영준비 길 9).
// 시작: wv-09a 끝(갖춘 부탁의 답이 남은 화면, 편집기 앞 탭 sensors.csv — 맨 위). 앞 take: wv-09a.
// 끝: 편집기 탭 넷 그대로(앞 탭 field_notes.md — 27행 근처), 답 끝이 보이고 Codex 입력칸은 비어 있다, 글상자 없음.
// 이 짜임은 본 촬영 답 wv08-b2(2026-11-28)에 맞춘 것이다: 센서 표의 TS1 행(2 · 12 · 22 · 32)은 모두 맞고, 메모를 댄 줄(4 · 12 · 15 · 17행)은 모두 몇 줄씩 어긋났다(실제 13~14 · 20 · 26 · 27행).
// 대본 wv0909 · wv0983 · wv0911 · wv0912가 그 답의 사실로 고쳐졌고(「Codex 답에 맞출 큐」), 값이 틀린 곳이 없어 wv0910은 대본에서 뺐다.
// 원자료의 행은 data/sensors.csv · data/field_notes.md에서 읽어 확인한다 — 답이 적은 행과 실제 행이 아래 표와 다르면 녹화 전에 멈춘다(손으로 옮겨 적은 값을 믿지 않는다).
import {labUi, atPhrase} from './lab-common.mjs';
import {NOTE, openFile, rows, lineNo, editorShow, dataLines, faint, codexInput, cxBox, cxRects, cxScroll, toAnswer, settle, answerScroll, speechEnd} from './wv-common.mjs';

// ── 녹화 답에 맞출 표(이 표만 고친다). 지금 값은 본 촬영 take wv08-b2의 답이다 ──
const A = {
 tsItem: ['li', 'HYD-01부터 HYD-04까지 반복'],      // wv0908 · wv0983 TS1 항목
 tsRows: '센서 표 2, 12, 22, 32행', rows: [2, 12, 22, 32],   // 그 항목이 적은 센서 표 행(밑줄 — 읽지 않는다)
 memoCite: '메모 17행', memoSaid: 17,                 // wv0983 그 항목이 태그 이름의 근거로 댄 메모 줄
 memoReal: [27, '모두 같은 이름을 씁니다'],            // 그 말이 실제로 있는 메모 줄과 그 안의 구절
 lastP: ['p', '표현이 다른 행을 같은 것으로 묶을지'],   // wv0912 답 끝 문단
 lastBand: '표현이 다른 행을 같은 것으로 묶을지, 단위가 다른 측정값을 어떤 기준으로 비교할지는 자료만으로 확정되지 않아 판단이 필요합니다',
};

export default async ctx => {
 const c = await labUi(ctx);
 const S = await dataLines('sensors.csv'), M = await dataLines('field_notes.md');
 const real = S.map((l, n) => n && l.split(',')[1] === 'TS1' ? n : 0).filter(Boolean);   // TS1이 실제로 있는 행
 if (real.join() !== A.rows.join()) throw Error('wv-09b: 답의 TS1 행 ' + A.rows.join(' · ') + '이 실제 ' + real.join(' · ') + '과 다름 — 대본 wv0909를 그 답에 맞춘 뒤 이 구간을 다시 짠다 (segs/wv-09b.mjs)');
 if (M[A.memoSaid].trim() !== '') throw Error('wv-09b: 메모 ' + A.memoSaid + '행이 빈 줄이 아님 — 대본 wv0983 「빈 줄입니다」와 다름 (segs/wv-09b.mjs)');
 if (!M[A.memoReal[0]].includes(A.memoReal[1])) throw Error('wv-09b: 메모 ' + A.memoReal[0] + '행에 「' + A.memoReal[1] + '」이 없음 (segs/wv-09b.mjs)');
 const shown = ls => c.note(ls, {at: NOTE.rows.at});
 await cxBox(c, ctx, A.tsItem);   // 시작 화면에 그 답이 있는지 먼저 본다
 await settle(c, ctx, {tabs: ['field_notes.md', 'equipment.csv', 'components.csv', 'sensors.csv'], active: 'sensors.csv', top: true, answer: ctx.prev?.answerScroll});   // 녹화 전: 리허설이 닫은 탭 · 굴린 답을 wv-09a 끝으로 되돌린다
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 await ctx.say('wv0908', async () => {
  await atPhrase(ctx, 'TS1이 있는 행 번호를'); await cxScroll(c, ctx, A.tsItem, 0.4, true); await c.emph(await cxRects(c, ctx, A.tsItem, A.tsRows), {shape: 'underline'});   // 읽지 않는다
  await shown(['Codex가 적은 센서 표 행 — ' + A.rows.join(' · ')]);
  await atPhrase(ctx, '센서 표를 열어서'); await openFile(c, ctx, 'sensors.csv', 2); await editorShow(c, ctx, 1, real[1]);
 }, {at: '이럴 때 쓰려고'});
 await ctx.say('wv0909', async () => {
  await c.emph(await rows(c, ctx, real[0]), {shape: 'band'});
  await atPhrase(ctx, 'TS1이 맞습니다'); await c.emph(await rows(c, ctx, real[0], real[0], 'TS1'), {shape: 'underline', keep: true, point: false});
  for (const [i, at] of [[1, '12행도'], [2, '22행도'], [3, '32행도']]) {
   await atPhrase(ctx, at); await editorShow(c, ctx, real[i]);
   await c.emph(await rows(c, ctx, real[i]), {shape: 'band'}); await c.emph(await rows(c, ctx, real[i], real[i], 'TS1'), {shape: 'underline', keep: true, point: false});
  }
  await atPhrase(ctx, '행 번호는 정확했습니다'); await shown(['Codex가 적은 센서 표 행 — ' + A.rows.join(' · '), '열어 보니 — 네 곳 모두 TS1']);
 }, {at: '먼저 2행'});
 await ctx.say('wv0983', async () => {
  await atPhrase(ctx, '메모 17행을 댔어요'); await toAnswer(c, ctx); await cxScroll(c, ctx, A.tsItem, 0.4, true); await c.emph(await cxRects(c, ctx, A.tsItem, A.memoCite), {shape: 'underline'});
  await atPhrase(ctx, '17행으로 가 보면'); await openFile(c, ctx, 'field_notes.md', 2); await editorShow(c, ctx, A.memoSaid, A.memoReal[0]);
  await c.emph(lineNo(A.memoSaid), {shape: 'box'});   // 빈 줄이라 띠를 그을 글자가 없다 — 줄 번호 칸의 숫자를 두른다
  await atPhrase(ctx, '27행에 있어요'); await c.emph(await rows(c, ctx, A.memoReal[0]), {shape: 'band'}); await c.emph(await rows(c, ctx, A.memoReal[0], A.memoReal[0], A.memoReal[1]), {shape: 'underline', keep: true, point: false});
  await shown(['Codex가 적은 센서 표 행 — ' + A.rows.join(' · '), '열어 보니 — 네 곳 모두 TS1', '메모 — Codex ' + A.memoSaid + '행 → 실제 ' + A.memoReal[0] + '행']);
  await atPhrase(ctx, '번지수만'); await speechEnd(ctx); await c.note(null);
 }, {at: '이번에는 메모 쪽도'});
 await ctx.say('wv0911', async () => { await toAnswer(c, ctx); }, {at: '정리하면 큰 내용은'});   // 메모를 열어 본 채 답으로 돌아온다(탭은 그대로 둔다)
 await ctx.say('wv0912', async () => {
  await cxScroll(c, ctx, A.lastP, 0.7); await c.emph(await cxRects(c, ctx, A.lastP, A.lastBand), {shape: 'band'});
  await atPhrase(ctx, '그대로 두세요'); await faint(c, ctx, await codexInput(c, ctx), {shape: 'box'});   // 비어 있는 Codex 입력칸(흐린 테두리)
 }, {at: '답 맨 끝도'});
 return {segment: 'wv-09b', next: 'wv-10: 이렇게 말하는 대신 이렇게', aiRequests: 0, answerScroll: await answerScroll(c, ctx)};
};
