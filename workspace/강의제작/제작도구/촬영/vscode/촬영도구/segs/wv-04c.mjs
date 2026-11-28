// 통합 2회차 06-1편 구간 04c(첫 페이지 — 웹 VS Code): 결과 화면에서 VS Code로 돌아와 터미널의 같은 출력과 새로 생긴 output 폴더(result.html)를 짚는다.
// 시작: wv-04a 끝(터미널에 첫 실행 출력, 탐색기에 output 행 접힘 — 둘째 페이지의 결과 화면은 wv-04b가 맨 위로 올려 두었다).
// 앞 take는 wv-04a로 준다 — wv-04b는 둘째 페이지라, 주면 run.sh가 이 페이지를 결과 화면 주소로 옮기려 한다(rec의 resumeUrl).
// 결과 화면을 띄워 두라는 말(wv0405)은 결과 화면 위에서 한다(wv-04b) — 이 구간은 VS Code로 돌아온 말(wv0406)부터다.
// 끝: 터미널 출력 그대로, 탐색기에 output이 펴져 result.html · result.json이 보인다.
import {labUi, atPhrase, rowSeen} from './lab-common.mjs';
import {label, twistie, fold, termRows, snap} from './wv-common.mjs';

export default async ctx => {
 const c = await labUi(ctx);
 const rows = await c.serial(() => ctx.p.evaluate(() => [...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].map(e => e.innerText.trim())));
 if (!rows.includes('output')) throw Error('탐색기에 output 행이 없음 — wv-04a 끝 상태에서 시작한다 (segs/wv-04c.mjs)');
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 await ctx.say('wv0406', async () => {
  await c.emph(await termRows(c, ctx, 'run.py', '결과: output/result.html', 1), {shape: 'band'});   // 명령 다음 줄(제목)부터 「결과: …」까지
  await snap(ctx, 'wv0406-term');
  await atPhrase(ctx, '탐색기에는 output이라는'); { const q = await twistie(c, ctx, 'output', 1); await c.move(q.x, q.y); }
  await atPhrase(ctx, '실행한 결과가 쌓이는'); await fold(c, ctx, 'output', 1, true); await rowSeen(ctx, 'result.html', 2);
  await atPhrase(ctx, '방금 본 결과 화면도'); await c.emph(label('result.html'), {shape: 'underline', at: await twistie(c, ctx, 'result.html', 2)});
  await snap(ctx, 'wv0406-output');
 }, {at: '터미널에도 같은 내용이'});
 return {segment: 'wv-04c', next: 'wv-05: 바이브 코딩과 Codex', aiRequests: 0};
};
