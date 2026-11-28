// 통합 2회차 06-1편 구간 01(둘째 페이지 — PAGE=1): 여는 말. 그림 한 장(사용자 녹화의 첫 화면) 위에 펜 그림 넷을 말에 맞춰 긋는다(촬영준비 길 6 「그림 한 장 위에 그리는 장면」).
// 시작: 둘째 페이지에 배경 그림(wv-common.mjs FIRST_FRAME — 지금은 임시 그림)을 가득 띄운 화면. 첫 페이지의 웹 VS Code는 건드리지 않는다. 끝: 같은 그림, 펜 그림을 모두 걷은 뒤.
// 부르기: PAGE=1 ./run.sh rec <이름> wv-01.mjs. 다음은 2장(사용자 녹화 — 모듈 없음), 그 뒤 wv-03.
// 그림 층이 못 하는 것: 점선(③ 칸 · 말풍선에서 네모로 가는 화살표)은 실선으로, 말풍선은 칸으로, 체크 · 물음표는 글자로, 테두리는 「지금 여기」 동그라미(ring)로 그린다(판정/녹화모듈_06-1.md).
import {labUi, atPhrase, imageView} from './lab-common.mjs';
import {FIRST_FRAME, INTRO, LAYERS, LAYERS_EXTRA, SITUATION, STEPS, speechEnd, snap} from './wv-common.mjs';

export default async ctx => {
 const c = await labUi(ctx);
 await imageView(c, ctx, FIRST_FRAME);
 await c.installPointer({x: 1500, y: 880});
 await ctx.begin();
 const intro = c.pen(INTRO), layers = c.pen(LAYERS), sit = c.pen(SITUATION), steps = c.pen(STEPS);

 await ctx.say('wv0101', async () => {
  await intro.draw('past');
  await atPhrase(ctx, '이제부터는'); await intro.draw('go', 'make');
  await snap(ctx, 'wv0101');
 }, {at: '방금 이론에서'});
 await ctx.say('wv0102', async () => {
  await intro.hide();
  await atPhrase(ctx, '맨 아래에는'); await layers.draw('L1', 'L1t');
  await atPhrase(ctx, '그 위에는'); await layers.draw('L2');
  await atPhrase(ctx, '그리고 맨 위에'); await layers.draw('L3');
  await snap(ctx, 'wv0102');
 }, {at: '맨땅에서 세울 때는'});
 await ctx.say('wv0106', async () => {
  await layers.draw('say');
  await atPhrase(ctx, '설비 네 대에'); await layers.draw('t1', 't2', 't3', 't4');
  await atPhrase(ctx, '어느 설비에 맞는 이야기인지 가려서'); await layers.draw('s1', 's2', 's3', 's4', 'which');
  await atPhrase(ctx, '떠 버립니다'); await layers.draw('lost');
  await snap(ctx, 'wv0106');
  await speechEnd(ctx); await layers.erase(...LAYERS_EXTRA);
 }, {at: '유온 TS1이 몇 도를'});
 await ctx.say('wv0107', async () => {
  await layers.draw('q');
  await atPhrase(ctx, '질문마다 나와야 할 답을'); await layers.draw('qa', 'a');
  await atPhrase(ctx, '질문에 맞춰 스키마를'); await layers.draw('as', 's');
  await atPhrase(ctx, '실제로 물어보고'); await layers.draw('sc', 'c');
  await atPhrase(ctx, '다음 층으로 올라갑니다'); await layers.draw('cq', 'ok');
  await snap(ctx, 'wv0107');
 }, {at: '먼저 그 층이 답해야 할 질문부터'});
 await ctx.say('wv0108', async () => {
  await layers.draw('r2');
  await atPhrase(ctx, '3회차에는'); await layers.draw('r3');
  await atPhrase(ctx, '4회차에는'); await layers.draw('r4');
  await atPhrase(ctx, '아래층이 서 있어야'); await layers.ring('L1');
  await snap(ctx, 'wv0108');
 }, {at: '이번 2회차에는'});
 await ctx.say('wv0103', async () => {
  await layers.hide();
  await atPhrase(ctx, '어느 날 보전팀에서'); await sit.draw('team', 'send', 'me');
  await atPhrase(ctx, '표가 다섯 개'); await sit.draw('f1', 'f2', 'f3', 'f4', 'f5');
  await atPhrase(ctx, '메모도 한 장'); await sit.draw('memo');
  await snap(ctx, 'wv0103');
 }, {at: '상황을 하나 잡고'});
 await ctx.say('wv0104', async () => {
  await sit.draw('b1');
  await atPhrase(ctx, '이 부품은 어느 설비들이'); await sit.draw('b2');
  await atPhrase(ctx, '우리가 맡은 일'); await sit.draw('know');
  await snap(ctx, 'wv0104');
 }, {at: '이 설비에는 어떤 센서가'});
 await ctx.say('wv0105', async () => {
  await sit.hide(); await layers.show('L1', 'L1t', 'L2', 'L3', 'r2', 'r3', 'r4');
  await atPhrase(ctx, '이 표들에 이미 다 들어 있어요'); await layers.draw('src', 'feed'); await layers.trace('feed');
  await snap(ctx, 'wv0105');
 }, {at: '곧 맨 아래층이 답해야 할 질문'});
 await ctx.say('wv0109', async () => {
  await layers.hide();
  await atPhrase(ctx, '첫 걸음은'); await steps.draw('s1');
  await atPhrase(ctx, '둘째 걸음은'); await steps.draw('a12', 's2');
  await atPhrase(ctx, '셋째 걸음은'); await steps.draw('a23', 's3');
  await atPhrase(ctx, '맨 앞의 자료 살피기'); await steps.ring('s1');
  await snap(ctx, 'wv0109');
 }, {at: '세 걸음으로 세웁니다'});
 await ctx.say('wv0110', async () => {
  await steps.draw('how');
  await snap(ctx, 'wv0110');
  await speechEnd(ctx); await steps.hide();
 }, {at: 'VS Code에서 AI와 함께'});
 return {segment: 'wv-01', next: '2장 사용자 녹화(wv0201~wv0204) → wv-03', aiRequests: 0};
};
