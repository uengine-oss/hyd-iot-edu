// 5분 예시 구간 01a(둘째 페이지 — PAGE=1): python run.py design의 결과 화면에서 겹친 곳 하나를 짚는다.
// 시작: 녹화 밖에서 그 폴더의 output/result.html을 만든 상태(ws-reset.mjs 뒤 python run.py design). 끝: 같은 화면(다음 구간은 첫 페이지 VS Code).
import {labUi, atPhrase, resultView, LABS} from './lab-common.mjs';
import {RESULT_TITLE} from './ws-common.mjs';

export default async ctx => {
 const c = await labUi(ctx);
 await resultView(c, ctx, LABS.ws.dir, RESULT_TITLE);
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 await ctx.say('ws0101', async () => {
  await c.emph({sel: '.verdict strong', has: '식별자가 겹치는 원자료 행'}, {shape: 'underline'});
  await atPhrase(ctx, '겹친 곳은'); await c.emph({sel: '.card .ch b', has: 'HYD-02'}, {shape: 'underline'});
  await atPhrase(ctx, '13행과 14행'); await c.emph({sel: '.card li .chip', has: 'components.csv:13'}, {shape: 'underline'});
 }, {at: '맨 위에 한 줄이'});
 return {segment: 'ws-01a', next: 'ws-01b: VS Code에서 원자료 두 줄', aiRequests: 0};
};
