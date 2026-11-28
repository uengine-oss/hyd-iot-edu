// 통합 2회차 06-1편 구간 09b(첫 페이지 — 웹 VS Code): 답이 적은 TS1의 행 번호를 센서 표에서 직접 찾아가 맞춰 보고(행 · 값), 답 끝의 되물음을 짚는다. Codex를 다시 부르지 않는다(촬영준비 길 9).
// 시작: wv-09a 끝(갖춘 부탁의 답이 남은 화면, 편집기 앞 탭 sensors.csv — 맨 위). 앞 take: wv-09a.
// 끝: sensors.csv 탭을 닫은 화면(앞 탭 components.csv), 답 끝이 보이고 Codex 입력칸은 비어 있다, 글상자 없음.
// 원자료의 행(TS1이 실제로 있는 행 · 그 행의 태그 · 센서명 · 재는것 · 같은 설비의 탱크 센서 행)은 data/sensors.csv에서 읽는다 — 손으로 옮겨 적지 않는다.
// 답은 녹화할 때마다 다르다 — 아래 표 A만 녹화한 답에 맞춰 고친다. 대본 wv0908 ~ wv0911의 행 번호 · 「한 줄 밀려」 · 「나머지 두 군데」도 그 답에 맞춘다(「Codex 답에 맞출 큐」).
// 답의 행이 모두 맞으면(실패를 꾸미지 않는다) 대본이 네 큐를 「열어 보니 맞다」로 고쳐 쓰므로 이 구간도 그 말에 맞춰 다시 짠다 — 지금 짠 것은 길뚫기 답처럼 둘째 행부터 어긋난 답이다(아래에서 확인하고 아니면 멈춘다).
import {labUi, atPhrase} from './lab-common.mjs';
import {NOTE, openFile, closeTab, rows, editorShow, dataLines, faint, codexInput, cxBox, cxRects, cxScroll, toAnswer, settle, answerScroll, speechEnd} from './wv-common.mjs';

// ── 녹화 답에 맞출 표(이 표만 고친다). 지금 값은 길뚫기 답(판정/길뚫기/06-1_4-4_갖춘부탁.답.md)의 글이다 ──
const A = {
 rowsLink: ['span.break-words', 'sensors.csv 2행, 11행, 20행'],   // wv0908 답이 적은 TS1 행 번호 링크
 rows: [2, 11, 20, 29],                                            // 그 링크가 적은 행(차례대로)
 atWrong: '다음은 11행',                                           // wv0909 처음 어긋난 행을 부르는 말(대본 글)
 wrongValue: ['li', '오일 탱크 온도'], wrongPhrase: '오일 탱크 온도',   // wv0910 답이 HYD-02 TS1에 적은 값
 lastAsk: ['strong', '이 두 기준은 어떻게 볼까요?'],                // wv0912 되묻는 문장(띠)
 criteria: ['p', '이 두 기준은 어떻게 볼까요?'], criteriaPhrases: ['구성품 이름과 센서 부착 위치가 달라도 같은 실물로 볼 기준', '이름이 다른 측정 항목의 정상값을 서로 비교해도 되는 기준'],   // 그 위의 두 기준(밑줄 — 읽지 않는다)
};

export default async ctx => {
 const c = await labUi(ctx);
 const S = await dataLines('sensors.csv'), F = n => S[n].split(',');   // F(n) = [설비코드, 태그, 센서명, 붙은곳, 재는것, …]
 const real = S.map((l, n) => n && l.split(',')[1] === 'TS1' ? n : 0).filter(Boolean);   // TS1이 실제로 있는 행
 const bad = A.rows.findIndex((r, i) => r !== real[i]);
 if (A.rows.length !== real.length || A.rows[0] !== real[0] || bad !== 1) throw Error('wv-09b: 답의 TS1 행 ' + A.rows.join(' · ') + '이 「첫 행은 맞고 둘째 행부터 어긋남」 꼴이 아님(실제 ' + real.join(' · ') + ') — 대본 wv0909 ~ wv0911을 그 답에 맞춰 고친 뒤 이 구간을 다시 짠다 (segs/wv-09b.mjs)');
 const tank = S.findIndex((l, n) => n && F(n)[0] === F(real[1])[0] && F(n)[4].includes('탱크'));   // 같은 설비의 탱크 온도 센서 행(「두 줄 아래에」)
 if (tank !== real[1] + 2) throw Error('wv-09b: ' + F(real[1])[0] + ' 탱크 센서 행이 ' + tank + ' — 대본 wv0910 「두 줄 아래에」와 다름 (segs/wv-09b.mjs)');
 const shown = ls => c.note(['Codex가 적은 행 — ' + A.rows.join(' · '), ...(ls ? ['실제 행 — ' + ls.join(' · ')] : [])], {at: NOTE.rows.at});
 await cxBox(c, ctx, A.rowsLink);   // 시작 화면에 그 답이 있는지 먼저 본다
 await settle(c, ctx, {tabs: ['field_notes.md', 'equipment.csv', 'components.csv', 'sensors.csv'], active: 'sensors.csv', top: true, answer: ctx.prev?.answerScroll});   // 녹화 전: 리허설이 닫은 탭 · 굴린 답을 wv-09a 끝으로 되돌린다
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 await ctx.say('wv0908', async () => {
  await atPhrase(ctx, 'TS1이 있는 행 번호를'); await cxScroll(c, ctx, A.rowsLink, 0.4, true); await c.emph(await cxRects(c, ctx, A.rowsLink), {shape: 'underline'});   // 읽지 않는다
  await shown(null);   // 「Codex가 적은 행」을 구석에 띄운다
  await atPhrase(ctx, '센서 표를 열어서'); await openFile(c, ctx, 'sensors.csv', 2); await editorShow(c, ctx, 1, real[1]);
 }, {at: '이럴 때 쓰려고'});
 await ctx.say('wv0909', async () => {
  await c.emph(await rows(c, ctx, A.rows[0]), {shape: 'band'});
  await atPhrase(ctx, 'TS1이 맞습니다'); await c.emph(await rows(c, ctx, A.rows[0], A.rows[0], 'TS1'), {shape: 'underline', keep: true, point: false});
  await atPhrase(ctx, A.atWrong); await c.emph(await rows(c, ctx, A.rows[1]), {shape: 'band'});
  await atPhrase(ctx, 'TS1이 아니네요');
  await c.emph(await rows(c, ctx, A.rows[1], A.rows[1], F(A.rows[1])[1]), {shape: 'underline', keep: true, point: false});   // 그 행의 태그(VS1)
  await c.emph(await rows(c, ctx, A.rows[1], A.rows[1], F(A.rows[1])[2]), {shape: 'underline', keep: true, point: false});   // 센서명(팬 진동 센서)
  await atPhrase(ctx, '바로 아랫줄에'); await c.emph(await rows(c, ctx, real[1]), {shape: 'band'}); await c.emph(await rows(c, ctx, real[1], real[1], 'TS1'), {shape: 'underline', keep: true, point: false});
  await shown(real.slice(0, 2));   // 글상자의 「11」 아래에 「→ 12」
 }, {at: '먼저 2행'});
 await ctx.say('wv0983', async () => {
  await c.emph(await rows(c, ctx, A.rows[2]), {shape: 'band'});
  await atPhrase(ctx, '가 보면'); await c.emph(await rows(c, ctx, real[2]), {shape: 'band'}); await c.emph(await rows(c, ctx, real[2], real[2], 'TS1'), {shape: 'underline', keep: true, point: false});
  await atPhrase(ctx, '몇 줄씩 어긋나'); await editorShow(c, ctx, A.rows[3], real[3]); await c.emph(await rows(c, ctx, A.rows[3]), {shape: 'band'});
  await atPhrase(ctx, '그렇다고 TS1이'); await c.emph(await rows(c, ctx, real[3]), {shape: 'band'}); await c.emph(await rows(c, ctx, real[3], real[3], 'TS1'), {shape: 'underline', keep: true, point: false});
  await atPhrase(ctx, '번지수만'); await shown(real);   // 「Codex 2 · 11 · 20 · 29행 → 실제 2 · 12 · 22 · 32행」
 }, {at: '나머지 두 군데도'});
 await ctx.say('wv0910', async () => {
  await atPhrase(ctx, '적힌 값도 하나 보죠'); await editorShow(c, ctx, real[1], tank);   // 12행으로 돌아온다
  await c.emph(await rows(c, ctx, real[1]), {shape: 'band'});
  await atPhrase(ctx, '오일 탱크 온도로'); await cxScroll(c, ctx, A.wrongValue, 0.4, true); await c.emph(await cxRects(c, ctx, A.wrongValue, A.wrongPhrase), {shape: 'underline'});
  await atPhrase(ctx, '표에는 오일 온도라고만'); await c.emph(await rows(c, ctx, real[1], real[1], F(real[1])[4]), {shape: 'box'});   // 재는것 칸(오일 온도)
  await atPhrase(ctx, '두 줄 아래에');
  await c.emph(await rows(c, ctx, tank, tank, F(tank)[1]), {shape: 'underline'});   // TS3
  await c.emph(await rows(c, ctx, tank, tank, [F(tank)[4], S[tank].split(F(tank)[4]).length - 2]), {shape: 'underline', keep: true, point: false});   // 재는것 칸(탱크 유온 — 센서명에도 같은 글이 있어 마지막 것)
  await speechEnd(ctx); await c.note(null);
 }, {at: '행 번호만 틀린 게'});
 await ctx.say('wv0911', async () => { await closeTab(c, ctx, 'sensors.csv'); await toAnswer(c, ctx); }, {at: '정리하면 큰 내용은'});
 await ctx.say('wv0912', async () => {
  await cxScroll(c, ctx, A.lastAsk, 0.7); await c.emph(await cxRects(c, ctx, A.lastAsk), {shape: 'band'});
  await atPhrase(ctx, '그 기준을 정해 달라는');
  for (const [i, p] of A.criteriaPhrases.entries()) await c.emph(await cxRects(c, ctx, A.criteria, p), {shape: 'underline', keep: true, ...(i ? {point: false} : {})});
  await atPhrase(ctx, '그대로 두세요'); await faint(c, ctx, await codexInput(c, ctx), {shape: 'box'});   // 비어 있는 Codex 입력칸(흐린 테두리)
 }, {at: '답 맨 끝도'});
 return {segment: 'wv-09b', next: 'wv-10: 이렇게 말하는 대신 이렇게', aiRequests: 0, answerScroll: await answerScroll(c, ctx)};
};
