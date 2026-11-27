// 통합 2회차 06-1편 구간 07: AI를 어디에 두고 일할까 — 편집기 빈자리 위에 펜 그림 하나를 두 칸으로 긋는다(왼쪽 ① 모를 때 — 사람과 AI가 나란히 물어 가며, 오른쪽 ② 알고 나면 — 사람이 위에서 방향을 잡고 판단).
// 시작: wv-06b 끝(Codex 답이 남은 화면). 앞 take를 주어 화살표를 잇는다. Codex를 부르지 않는다. 그림은 큐 wv0702의 말이 끝날 때 걷는다(구간 끝에 떠 있으면 녹화가 멈춘다).
import {labUi, atPhrase} from './lab-common.mjs';

// 프레임 px(1920×1080). 판은 편집기 빈자리(VS Code 그림이 있는 가운데)에 둔다.
const ROLE = {id: 'AI와 일하는 자리', board: [470, 250, 920, 540], items: [
 {id: 'h1', kind: 'box', at: [530, 380, 160, 90], text: '사람'},
 {id: 'a1', kind: 'box', at: [780, 380, 160, 90], text: 'AI'},
 {id: 'ha', kind: 'arrow', from: 'h1', to: 'a1', route: 'over', drop: 45},
 {id: 'ah', kind: 'arrow', from: 'a1', to: 'h1', route: 'under', drop: 45},
 {id: 't1', kind: 'text', at: [530, 610], text: '① 모를 때\n물어 가며 파악'},
 {id: 'h2', kind: 'box', at: [1110, 320, 160, 80], text: '사람'},
 {id: 'a2', kind: 'box', at: [1110, 480, 160, 80], text: 'AI'},
 {id: 'down', kind: 'arrow', from: 'h2', to: 'a2'},
 {id: 't2', kind: 'text', at: [1030, 610], text: '② 알고 나면\n내가 방향을 잡고 판단'},
]};

export default async ctx => {
 const c = await labUi(ctx);
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 const fig = c.pen(ROLE);
 await ctx.say('wv0701', async () => {
  await fig.draw('h1', 'a1');
  await atPhrase(ctx, '먼저 물어봅니다'); await fig.draw('ha', 'ah');
  await atPhrase(ctx, '딱 그 첫날이에요'); await fig.draw('t1');
 }, {at: '첫날을 떠올려 보면'});
 await ctx.say('wv0702', async () => {
  await fig.draw('h2', 'a2');
  await atPhrase(ctx, '내가 정하고'); await fig.draw('down');
  await atPhrase(ctx, '판단은 사람이 하는 겁니다'); await fig.draw('t2');
  const q = ctx.__cue; if (!ctx.rehearsal) { const w = q.t0 + q.dur - Date.now(); if (w > 0) await ctx.sleep(w); }
  await fig.hide();
 }, {at: '자리가 바뀝니다'});
 return {segment: 'wv-07', next: 'wv-08: 갖춰서 다시 부탁하기', aiRequests: 0};
};
