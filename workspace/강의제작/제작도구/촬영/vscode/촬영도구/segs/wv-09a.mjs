// 통합 2회차 06-1편 구간 09a(첫 페이지 — 웹 VS Code): 갖춘 부탁의 답에서 물은 것 넷의 답을 차례로 찾는다 — 다섯 파일 · 행 수 표(결과 화면과 나란히) · 이어지는 칸(세 표를 열어 설비코드) ·
// 공통 식별자 펜 그림 · 교체부품 ↔ 품번 · 엇갈린 곳 셋. Codex를 다시 부르지 않는다(촬영준비 길 9).
// 시작: wv-08 끝(답이 다 선 화면 — 패널이 답 끝으로 굴러가 있다, 편집기에 field_notes.md · equipment.csv, data가 펴짐, 터미널에 첫 실행 출력). 앞 take: wv-08.
// 끝: 답이 남은 화면, 편집기 탭 field_notes.md · equipment.csv · components.csv · sensors.csv(앞), 글상자 · 펜 그림 · 결과 화면 그림 없음.
// wv0902 「결과 화면을 옆에 띄워」: 한 큐 안에서 답 → 결과 화면 → 답으로 오가므로 둘째 페이지로 넘어가지 않고, 녹화 전에 그 결과 화면의 그림 칸을 찍어 두었다가 VS Code 위에 띄운다(wv-common.mjs resultInset).
// 답은 녹화할 때마다 다르다(2026-11-28 본 촬영 답 wv08-b2에 맞춤) — 아래 표 A만 녹화한 답(wv-08 take의 timing.json result.answer와 그 화면)에 맞춰 고친다. 찾는 꼴은 wv-common.mjs 「Codex 패널」 머리말.
// 답에 그 요소가 없거나 여럿이면 그 큐 id를 대며 멈춘다(건너뛰지 않는다). 대본도 「Codex 답에 맞출 큐」대로 그 답의 사실(제목 · 행 수 · 항목 차례 · 이름)에 맞춘다.
import {labUi, atPhrase, em} from './lab-common.mjs';
import {LINKS, MIXED, NOTE, note, openFile, piece, gutter, between, resultInset, penTexts, cxBox, cxRects, cxScroll, toAnswer, settle, answerScroll, speechEnd} from './wv-common.mjs';

// ── 녹화 답에 맞출 표(이 표만 고친다). 지금 값은 본 촬영 take wv08-b2(2026-11-28)의 답이다 — 큰 제목 넷(h2), 행 수 표는 결과 화면과 같음 ──
const A = {
 heads: [['h2', '파일 확인', '어디 있는지만'], ['h2', '표끼리 이어지는 칸', '참고로 여러분이'], ['h2', '표기가 달라 보이는', '그래도 이 네 가지는'], ['h2', '같은 이름으로 보여도', '같이 찾아보죠']],   // wv0901 큰 제목 [CSS, 든 글, 밑줄을 긋는 말]
 allThere: ['p', '다섯 파일은 모두'], allPhrase: '다섯 파일은 모두 data/에 있습니다',   // wv0902 「맨 위에 모두 있다고」
 table: 'equipment.csv',                                    // wv0902 행 수 표를 고르는 글(그 표에 든 글)
 files: ['equipment.csv', 'components.csv', 'sensors.csv', 'spare_parts.csv', 'part_aliases.csv'],   // 표의 행 차례(위에서 아래) — 결과 화면 상자와 견줄 차례
 countCol: 1,                                               // 행 수 칸 번호(0부터)
 meaningHead: ['파일', 2],                                  // 「한 행의 뜻」 머리 칸 [머리 줄 첫 칸 글, 칸 번호]
 sensorRow: 'sensors.csv',                                  // 「센서 표라면」 — 그 행(띠)
 key: ['li', '설비별 구성 요소와 센서 행을'], keyWord: 'equipment.csv의 설비코드',   // wv0903 「답이 맨 먼저 꼽은 게」 — 첫 항목과 그 안의 낱말(설비코드는 그 항목에 두 번 나와 앞 구절까지 짚는다)
 part: ['li', '예비품 표기는 괄호 안에'], spare: '예비품',   // wv0904 교체부품 ↔ 품번 항목과 그 안의 「예비품」(「답에는 예비품이라는 말이」)
 sameTag: ['li', 'HYD-01부터 HYD-04까지 반복'], tag: 'TS1',   // wv0905 이름은 같은데 물건이 다른 곳
 aliases: ['p', 'P-PMP-SEAL의 다른 표기는'], numbers: ['P-PMP-SEAL', 'PS-4510', 'P_PMP_SEAL', 'HI-SK-45A'], codeCss: 'span.inline-markdown',   // 답의 `글`은 이 Codex 판에서 code가 아니라 span.inline-markdown으로 그려진다(wv09a-bd1)
    // wv0906 그 문단과 그 안의 번호들(code — PMP-SEAL은 같은 문단에 두 번 나와 뺀다)
 cooler: ['p', '냉각 장치도'], coolerText: '냉각 장치도 오일 쿨러(2행), 쿨러(11행), 열교환기(21행), 수냉 열교환기(30행)로 적혀 있습니다',   // wv0982 띠
 unsureEl: ['p', '표현이 다른 행을 같은 것으로 묶을지'], unsure: '표현이 다른 행을 같은 것으로 묶을지',   // wv0982 「자료만으로 확정되지 않는다고」 — 답 끝 문단의 그 구절(밑줄)
};

export default async ctx => {
 const c = await labUi(ctx);
 await cxBox(c, ctx, A.allThere);   // 시작 화면에 그 답이 있는지 먼저 본다
 // 녹화 전: 0903에서 여는 표 둘을 1행으로 열었다 닫아 둔다 — VS Code는 닫은 파일의 굴린 자리를 기억해, 리허설이 굴린 sensors.csv가 아래쪽에서 열려 1행을 못 찾았다(wv09a-bd2)
 for (const f of ['components.csv', 'sensors.csv']) await settle(c, ctx, {tabs: ['field_notes.md', 'equipment.csv', f], active: f, top: true});
 await settle(c, ctx, {tabs: ['field_notes.md', 'equipment.csv'], active: 'equipment.csv', answer: 'end'});   // 녹화 전: 리허설이 연 탭 · 굴린 답을 wv-08 끝으로 되돌린다
 const inset = await resultInset(c, ctx);   // 녹화 전: 결과 화면의 그림 칸을 찍어 둔다(임시 페이지 — 화면에 남지 않는다)
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 await ctx.say('wv0901', async () => {
  await cxScroll(c, ctx, A.heads[0], 0.03);   // 끝난 답을 맨 위로 올린다
  await atPhrase(ctx, '우리가 물은 게 네 가지'); await note(c, 'asked');   // 「물은 것 넷」 — wv0907 끝에서 걷는다
  for (const [css, has, at] of A.heads) { await atPhrase(ctx, at); await cxScroll(c, ctx, [css, has], 0.3, true); await c.emph(await cxRects(c, ctx, [css, has]), {shape: 'underline'}); }
 }, {at: '아까보다 훨씬 길죠'});
 await ctx.say('wv0902', async () => {
  await cxScroll(c, ctx, A.allThere, 0.12); await c.emph(await cxRects(c, ctx, A.allThere, A.allPhrase), {shape: 'underline'});
  await atPhrase(ctx, '행 수는 표로'); const t = await cxScroll(c, ctx, ['table', A.table], 0.2, true); await c.emph(em.box(t), {shape: 'box'});
  await atPhrase(ctx, '결과 화면의 상자에'); await inset.show(t.y - 40);
  const tick = between(ctx, '결과 화면의 상자에', '프로그램이 센', A.files.length);   // 다섯 줄에 차례로 밑줄 — 숫자는 읽지 않는다
  for (const [i, f] of A.files.entries()) {
   await tick(i);
   await c.emph(await cxRects(c, ctx, {cell: [A.table, f, A.countCol]}), {shape: 'underline'});
   await c.emph(inset.count(f), {shape: 'underline', keep: true, point: false});
  }
  await atPhrase(ctx, '옆 칸에는'); await inset.hide(); await c.emph(await cxRects(c, ctx, {cell: [A.table, ...A.meaningHead]}), {shape: 'underline'});
  await atPhrase(ctx, '센서 표라면'); await c.emph(em.box(await cxBox(c, ctx, {row: [A.table, A.sensorRow]})), {shape: 'band'});
 }, {at: '맨 위에 모두 있다고'});
 await ctx.say('wv0903', async () => {
  await cxScroll(c, ctx, A.key, 0.3, true); await c.emph(await cxRects(c, ctx, A.key, A.keyWord), {shape: 'underline'});
  for (const [f, at] of [['equipment.csv', '설비 대장에도'], ['components.csv', '구성 요소 표에도'], ['sensors.csv', '센서 표에도']]) {
   await atPhrase(ctx, at); await openFile(c, ctx, f, 2);
   const h = await piece(c, ctx, '설비코드,', '설비코드');
   await c.emph(h, {shape: 'box', at: await gutter(c, ctx, h)});   // 1행의 「설비코드」 칸
   await c.emph(await piece(c, ctx, 'HYD-01,', 'HYD-01'), {shape: 'underline', keep: true, point: false});   // 그 아래 HYD-01
  }
  await atPhrase(ctx, '그래서 설비 코드가 같은'); { const b = await cxBox(c, ctx, A.key); await c.move(b.x + Math.min(60, b.w / 3), b.y + b.h + 8); }   // 답으로 돌아온다
 }, {at: '답이 맨 먼저 꼽은 게'});
 const links = c.pen(LINKS);
 await ctx.say('wv0981', async () => {
  await links.draw('eq', 'co', 'se');
  await atPhrase(ctx, '설비 코드만큼은'); await links.draw('e_c', 'e_s', 'code');
 }, {at: '공통 식별자가'});
 await ctx.say('wv0904', async () => {
  await atPhrase(ctx, '구성 요소 표의 교체부품'); await cxScroll(c, ctx, A.part, 0.3, true); await c.emph(await cxRects(c, ctx, A.part), {shape: 'underline'});
  await atPhrase(ctx, '부품 표의 품번'); await links.draw('sp', 'c_p', 'pn');
  await atPhrase(ctx, '답에는 예비품이라는'); await c.emph(await cxRects(c, ctx, A.part, A.spare), {shape: 'underline'});
  await atPhrase(ctx, '품번 표기 표도'); await links.draw('al', 'p_a');
  await speechEnd(ctx); await links.hide();
 }, {at: '부품 쪽도'});
 const mixed = c.pen(MIXED);
 await ctx.say('wv0905', async () => {
  await cxScroll(c, ctx, A.sameTag, 0.3, true); await c.emph(await cxRects(c, ctx, A.sameTag), {shape: 'band'});
  await atPhrase(ctx, 'TS1이 설비 한 대에만'); await c.emph(await cxRects(c, ctx, A.sameTag, A.tag), {shape: 'underline', keep: true, point: false});
  await atPhrase(ctx, '네 대에 저마다'); await mixed.draw('m1');
 }, {at: '이름은 같은데 물건이 다른'});
 await ctx.say('wv0906', async () => {
  await cxScroll(c, ctx, A.aliases, 0.55); await c.emph(await cxRects(c, ctx, A.aliases), {shape: 'band'});   // 답에서 열교환기 항목이 위에 있으면 함께 보이게 아래쪽에 둔다
  await mixed.draw('m2');
  await atPhrase(ctx, '부품 하나에 번호가');
  for (const [i, n] of A.numbers.entries()) await c.emph(await cxRects(c, ctx, {within: A.aliases, css: A.codeCss, eq: n}), {shape: 'underline', keep: true, ...(i ? {point: false} : {})});   // 읽지 않는다
 }, {at: '물건은 같은데 이름이 여러'});
 await ctx.say('wv0982', async () => {
  await cxScroll(c, ctx, A.cooler, 0.3, true); await c.emph(await cxRects(c, ctx, A.cooler, A.coolerText), {shape: 'band'});
  await atPhrase(ctx, '그 자리에 열교환기라고'); await mixed.draw('m3');
  await atPhrase(ctx, '자료만으로 확정되지'); await cxScroll(c, ctx, A.unsureEl, 0.6, true); await c.emph(await cxRects(c, ctx, A.unsureEl, A.unsure), {shape: 'underline'});
 }, {at: '장치 이름에도'});
 await ctx.say('wv0907', async () => {
  await c.emph(await penTexts(c, ctx, 'm1', 'm2', 'm3'), {shape: 'box'});   // 석 줄에 함께 테두리
  await atPhrase(ctx, '그런데 그 전에'); await mixed.hide(); await c.note(null);   // 「물은 것 넷」 글상자도 함께 걷는다
  await toAnswer(c, ctx);
 }, {at: '이론에서 세 시스템의'});
 if (await inset.on()) throw Error('wv-09a 끝에 결과 화면 그림이 떠 있음 (segs/wv-09a.mjs)');
 return {segment: 'wv-09a', next: 'wv-09b: 답의 TS1 행을 센서 표에서 열어 보기', aiRequests: 0, notePos: NOTE.asked.at, answerScroll: await answerScroll(c, ctx)};
};
