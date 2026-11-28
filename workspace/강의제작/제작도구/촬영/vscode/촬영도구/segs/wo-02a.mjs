// 06-2 구간 02a(첫 페이지): 현장 메모의 물음 셋 → 다듬은 세 역량 질문(길잡이 구석에) → 기대 답을 먼저 적는 까닭 → expected · decisions 빈 틀 → 첫 부탁 R1(읽기, 새 대화)을 보내고 답이 끝날 때까지(자르지 않는다).
// 시작: wo-01 끝(앞 take를 준다). 끝: R1 답이 다 선 화면(편집기 앞 탭은 decisions.csv — 기다림 말 wo0291을 했으면 expected.csv). 그 답을 짚는 말은 wo-02b.
// 실제 요청을 보낸다(리허설은 WO_NOSEND=1로 보내지 않고 해 본다). 요청 뒤에 멈추면 WO_SINCE로 잇는다(판정 문서).
import {atPhrase} from './lab-common.mjs';
import {ui, RESUME, QE, guideIn, guideRing, guideAdd, seamOut, keepEnd, open, tab, closeTab, unfold, mark, ln, reveal, note, speechEnd, newChat, paste, send, answer, waitSay, askOf} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 if (!(await c.serial(() => ctx.p.evaluate(() => !!document.querySelector('.terminal-wrapper')?.checkVisibility())))) throw Error('터미널이 닫혀 있음 — wo-01 끝 화면이 아님');
 const G = await guideIn(c, ctx, 'vs', RESUME == null ? {} : {items: QE, ring: 'm1'});
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 let since = RESUME;
 if (since == null) {
  await ctx.say('wo0201', async () => {
   await guideRing(G, 'm1');
   await atPhrase(ctx, '현장 메모 맨 아래에'); await open(c, ctx, 'data/field_notes.md'); await reveal(c, ctx, 31, 35);
   await atPhrase(ctx, '첫 줄은'); await mark(c, ctx, 33);
   await atPhrase(ctx, '둘째 줄은'); await mark(c, ctx, 34);
  }, {at: '역량 질문은'});
  await ctx.say('wo0211', async () => {
   await mark(c, ctx, 28, {sub: '「한계」 칸은 인터록이 걸리는 값이고', shape: 'underline'});
   await atPhrase(ctx, '셋째 줄은'); await mark(c, ctx, 35);   // 28행을 잠깐 보이고 34 · 35행으로 돌아온다(한 화면에 함께 들면 굴리지 않는다)
  }, {at: '한계는 거기에 닿으면'});
  await ctx.say('wo0202', async () => {
   await mark(c, ctx, 23, {sub: '구성 요소 목록의 일련번호는 그 구성 요소에 달린 장치(펌프)의 번호입니다', shape: 'underline'});
   await atPhrase(ctx, '다듬은 세 질문은'); await note(c, 'q3');
   await speechEnd(ctx); await c.note(null); await guideAdd(G, 'q1', 'q2', 'q3');   // 큐 끝에서 글상자를 구석으로 줄여 둔다 — 길잡이의 질문 석 줄로
  }, {at: '메모 조금 위에'});
  await ctx.say('wo0203', async () => { await guideAdd(G, 'exp', 'expT'); }, {at: '어떤 답이 나와야 맞는지를'});   // ①과 ⑤ 사이 「점선」 — 그림 층에 점선이 없어 위로 도는 화살표로
  await ctx.say('wo0221', async () => {
   await closeTab(c, ctx, 'field_notes.md'); await unfold(c, ctx, 'app', 1); await unfold(c, ctx, 'features', 2); await open(c, ctx, 'app/features/expected.csv');
   await atPhrase(ctx, '맨 위에 설명 한 줄과'); await mark(c, ctx, 1);
   await atPhrase(ctx, '칸 이름만 있고'); await mark(c, ctx, 2, {shape: 'underline'});
   for (const [i, p] of ['몇 번 질문인지', '무엇을 넣어서 물을지', '어느 항목을 볼지', '나와야 할 답은', '그 근거는 어디인지를요'].entries()) { await atPhrase(ctx, p); await mark(c, ctx, 2, {cell: i, shape: 'underline'}); }
   await atPhrase(ctx, '그 옆의 decisions도'); await open(c, ctx, 'app/features/decisions.csv');
   await atPhrase(ctx, '줄이 벌써 둘 있는데'); await mark(c, ctx, 4, {cell: 0, shape: 'underline'}); await mark(c, ctx, 5, {cell: 0, shape: 'underline', keep: true, point: false});
   await atPhrase(ctx, '고른 것과 이유를 적는 칸은'); await mark(c, ctx, 4, {sub: ',,,'}); await mark(c, ctx, 5, {sub: ',,,', keep: true, point: false});
   await atPhrase(ctx, '첫째 줄은'); await mark(c, ctx, 4, {cell: 0, shape: 'underline'});
   await atPhrase(ctx, '둘째 줄은'); await mark(c, ctx, 5, {cell: 0, shape: 'underline'});
  }, {at: '기대 답은 features 폴더의'});
  await ctx.say('wo0204', async () => {
   await newChat(c, ctx); await paste(c, ctx, askOf('wo0204'));
   since = await send(c, ctx, '보여 달라는 겁니다');
  }, {at: '기대 답을 원자료에서'});
 }
 const waited = [];
 if (await waitSay(c, ctx, since, 'wo0291', async () => { await tab(c, ctx, 'expected.csv'); await c.emph(await ln(c, ctx, 1), {shape: 'band'}); }, 'expected 맨 윗줄에')) waited.push('wo0291');
 const r = await answer(c, ctx, since);
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '02a');
 return {segment: 'wo-02a', page: 0, cut, ask: 'R1', aiRequests: since == null ? 0 : 1, answer: r.message, codexMs: r.ms, used: r.used, waitLines: waited, next: 'wo-02b: R1 답 보기 · R2(expected 적기)'};
};
