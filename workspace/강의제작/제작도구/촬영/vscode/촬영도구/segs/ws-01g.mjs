// 5분 예시 구간 01g(둘째 페이지 — PAGE=1): 결과 화면을 새로 고쳐(학생의 F5) 자리 하나와 실물 두 대로 풀린 것을 보고, 랩 한 바퀴를 글상자로 맺는다.
// 시작: 녹화 밖에서 둘째 페이지에 python run.py names의 결과 화면을 연 상태(01a가 연 design 화면 — 여기서 F5로 새 결과를 읽는다). 끝: 같은 화면, 글상자를 걷은 뒤.
import {labUi, atPhrase, scrollPageTo} from './lab-common.mjs';
import {NAMES_TITLE} from './ws-common.mjs';

const node = id => ({sel: 'g.n[data-id="' + id + '"]'});
const box = (ctx, id) => ctx.p.evaluate(id => { const e = document.querySelector('g.n[data-id="' + id + '"]'); if (!e) throw Error('그림에 노드 없음: ' + id); const b = e.getBoundingClientRect(); return {x: b.x + b.width / 2, y: b.y + b.height / 2}; }, id);
const speechEnd = async ctx => { const q = ctx.__cue; if (!ctx.rehearsal) { const w = q.t0 + q.dur - Date.now(); if (w > 0) await ctx.sleep(w); } };

export default async ctx => {
 const c = await labUi(ctx);
 await c.installPointer(ctx.prev ? null : {x: 1400, y: 500});
 await ctx.begin();
 await ctx.say('ws0116', async () => {
  // 학생의 F5 — 새로 읽은 문서에는 표시 포인터가 없어 같은 자리에 다시 놓는다(촬영준비 길 6)
  const at = await c.serial(() => ctx.p.evaluate(() => { const r = document.getElementById('recording-pointer')?.getBoundingClientRect(); return r ? {x: r.x, y: r.y} : null; }));
  await c.serial(() => ctx.p.reload()); await ctx.sleep(800); await c.installPointer(at);
  if (!(await c.serial(() => ctx.p.title())).startsWith(NAMES_TITLE)) throw Error('결과 화면 제목이 「' + NAMES_TITLE + '」로 시작하지 않음');
  await c.emph({sel: '.verdict strong', has: '구성 요소 자리'}, {shape: 'underline'});
  await atPhrase(ctx, '그림을 보면'); await scrollPageTo(c, ctx, () => c.serial(() => box(ctx, 'HYD-02+주 펌프 (A)|KP-1902-551')));
  await c.emph(node('HYD-02+주 펌프 (A)|KP-2603-114'), {shape: 'box'}); await c.emph(node('HYD-02+주 펌프 (A)|KP-1902-551'), {shape: 'box', keep: true});
  await atPhrase(ctx, '이름이 주 펌프 A로'); await c.emph(node('HYD-02+주 펌프 (A)'), {shape: 'box'});
 }, {at: '구성 요소 자리 다섯 곳에'});
 await ctx.say('ws0115', async () => {
  await c.clearEmph();
  await c.note(['갈린다', '열어 본다', '받아 본다', '고른다', '적게 한다', '돌려 본다'], {title: '랩의 한 바퀴', at: 'tc'});
  await atPhrase(ctx, '길이 갈리면'); await c.emph({note: '갈린다'}, {shape: 'underline'});
  await atPhrase(ctx, '원자료를 열어'); await c.emph({note: '열어 본다'}, {shape: 'underline'});
  await atPhrase(ctx, '받아 본 뒤에'); await c.emph({note: '받아 본다'}, {shape: 'underline'});
  await atPhrase(ctx, '내 이유로 고르죠'); await c.emph({note: '고른다'}, {shape: 'underline'});
  await atPhrase(ctx, 'Codex가 적고'); await c.emph({note: '적게 한다'}, {shape: 'underline'});
  await atPhrase(ctx, '돌려서'); await c.emph({note: '돌려 본다'}, {shape: 'underline'});
  await speechEnd(ctx); await c.note(null);
 }, {at: '방금 한 것이'});
 return {segment: 'ws-01g', next: '끝', aiRequests: 0};
};
