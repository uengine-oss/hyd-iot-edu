// 통합 2회차 06-1편 구간 04a(첫 페이지 — 웹 VS Code): 첫 실행 명령. 터미널 입력 줄을 누르고 python run.py를 말에 맞춰 키로 친 뒤, 큐의 끝(「대신 세어 줍니다」)에서 Enter.
// 결과 화면이 저절로 열리는 장면이라 두 구간으로 찍는다(촬영준비 길 6 「결과 화면이 저절로 열리는 장면」): 이 구간은 터미널에 「결과: output/result.html」이 뜬 뒤 0.7초 두고 끝내고,
// 다음 wv-04b(둘째 페이지)가 결과 화면에서 시작한다 — 합성하면 Enter 직후 결과 화면이 앞에 뜬 것처럼 이어진다. 그래서 Enter는 명령을 풀어 말한 뒤 큐 끝에 친다(Enter 뒤 바로 다음 구간 wv0402 「엔터를 누르자마자 … 열렸습니다」).
// 시작: wv-03 끝(터미널이 열려 프롬프트만 있음, 편집기에 field_notes.md · equipment.csv, data가 펴짐, output/ 없음). 앞 take: wv-03.
// 끝: 터미널에 첫 실행 출력(제목 · 읽은 표와 행 수 · 출발 그림 연결 · 「결과: output/result.html」), 탐색기에 output 행(접힘). Codex를 부르지 않는다.
import {labUi, atPhrase, exists, termLine, termWait} from './lab-common.mjs';
import {LAB, PROMPT} from './wv-common.mjs';

export default async ctx => {
 const c = await labUi(ctx);
 if (await exists(ctx, LAB + '/output')) throw Error('output/이 이미 있음 — 결과 화면이 저절로 열리는 첫 실행이 아니다. ./run.sh reset wv-reset.mjs 뒤 wv-03부터 (segs/wv-04a.mjs)');
 if (!(await c.serial(() => ctx.p.evaluate(() => !!document.querySelector('.terminal-wrapper')?.checkVisibility())))) throw Error('터미널이 닫혀 있음 — wv-03 끝 상태에서 시작한다 (segs/wv-04a.mjs)');
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 await ctx.say('wv0401', async () => {
  const q = await termLine(c, ctx, PROMPT); await c.clickAt(q.x, q.y);
  await atPhrase(ctx, 'python, 한 칸'); await c.typeKeys('python');
  await atPhrase(ctx, 'run.py라고'); await c.typeKeys(' run.py');
  await atPhrase(ctx, '대신 세어 줍니다'); await c.key('Enter');
 }, {at: '터미널에 python'});
 await termWait(ctx, '결과: output/result.html', 20000);
 if (!(await exists(ctx, LAB + '/output/result.html'))) throw Error('wv0401: 실행 뒤 output/result.html이 없음 (segs/wv-04a.mjs)');
 await ctx.sleep(700);
 return {segment: 'wv-04a', next: 'wv-04b(PAGE=1): 결과 화면', aiRequests: 0};
};
