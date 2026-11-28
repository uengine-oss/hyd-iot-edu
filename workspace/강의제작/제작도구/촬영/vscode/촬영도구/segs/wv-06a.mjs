// 통합 2회차 06-1편 구간 06a(첫 페이지 — 웹 VS Code): 막연한 부탁 「현장 메모 정리해 줘」를 Codex에 보내고, 답이 끝날 때까지 기다리며 지금 무엇을 하는지 말한다(자르지 않는다 — 영상 V-14).
// 시작: wv-05 끝(빈 Codex 새 대화, 터미널에 첫 실행 출력, 편집기에 field_notes.md · equipment.csv). 앞 take: wv-05. 끝: Codex 답이 다 선 화면(그 답을 보는 말은 다음 구간 wv-06b).
// 실제 요청을 보낸다 — 리허설도 같다(CODEX_HOME=… ./run.sh dry|rec …, 촬영준비 길 9). 끝난 답은 돌려주는 값 answer로 timing.json result에 남고, 다음 구간 wv-06b 머리의 표를 그 답으로 맞춘다.
// wv0602가 끝났는데 답이 아직이면 기다림 말 wv0691 · wv0692를 차례로 하고(waitLines — 답이 오면 남은 말은 건너뛴다), 그래도 남는 기다림은 말 없이 둔다.
import {labUi, atPhrase, codexFocus, codexType, codexSubmit, codexWait, waitLines, em} from './lab-common.mjs';
import {ASK_VAGUE, faint, speechEnd} from './wv-common.mjs';

// 진행 표시가 뜨는 자리(Codex 패널 안 비율 상자 — 보낸 부탁 아래 「Working for Ns」부터 「Running command」 줄까지). 웹뷰의 바뀌는 글은 잴 수 없어 리허설 화면(wv06a-dry1/일하는중.png)을 보고 정했다.
// 대본 「진행 표시(흐린 테두리)」 — 녹화 전 맞춤: 녹화 답의 진행 표시 모양을 보고 고친다.
const WORKING = em.codex(0.02, 0.17, 0.98, 0.34);

export default async ctx => {
 const c = await labUi(ctx);
 if (!(await c.serial(() => ctx.p.text())).includes('Ask Codex anything')) throw Error('빈 Codex 새 대화가 아님 — wv-05 끝 상태에서 시작한다 (segs/wv-06a.mjs)');
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 let since = 0;
 await ctx.say('wv0601', async () => {
  await codexFocus(c, ctx);
  await atPhrase(ctx, ASK_VAGUE); await codexType(c, ctx, ASK_VAGUE);
  await atPhrase(ctx, '보냅니다'); since = await codexSubmit(c, ctx);
 }, {at: '오른쪽 대화 칸에'});
 // 진행 표시 테두리는 그 말이 끝날 때 걷는다 — 남겨 두면 답이 올라와 패널이 굴러간 뒤 엉뚱한 줄을 둘러싼다(wv06a-r1, 2026-11-27).
 await ctx.say('wv0602', async () => { await faint(c, ctx, WORKING, {shape: 'box'}); await speechEnd(ctx); await c.clearEmph(); }, {at: '지금 화면에 올라오는 글이'});
 if (ctx.rehearsal) await ctx.sleep(6000).then(() => c.serial(() => ctx.p.screenshot({path: ctx.out + '/일하는중.png'})));   // 리허설만: 일하는 동안의 패널 모습을 남겨 비율 상자를 맞춘다
 const waited = await waitLines(ctx, since, ['wv0691', 'wv0692']);
 const r = await codexWait(ctx, since);
 if (ctx.rehearsal) { await c.serial(() => ctx.p.screenshot({path: ctx.out + '/답.png'})); await ctx.fs.writeFile(ctx.out + '/답.md', r.message ?? ''); }
 return {segment: 'wv-06a', next: 'wv-06b: 끝난 답 보기', aiRequests: 1, answer: r.message, codexMs: r.ms, used: r.used, waitLines: waited};
};
