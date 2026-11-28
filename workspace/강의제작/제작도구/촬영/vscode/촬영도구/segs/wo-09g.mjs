// 06-2 구간 09g(첫 페이지): properties.csv의 설치일 줄(자료형 날짜) → python run.py parts → check → query를 말에 맞춰 차례로. Codex 부탁 없음.
// 시작: wo-09f 끝(R19 답이 선 화면, 앞 take를 준다). 끝: 터미널에 query 결과 — 다음은 wo-09h(PAGE=1). 녹화 뒤 사본 SEG=09g.
import {atPhrase} from './lab-common.mjs';
import {ui, QE, PICK, guideIn, seamOut, keepEnd, open, mark, lineHas, command} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const n = await lineHas(ctx, 'app/features/properties.csv', ',' + PICK.installed + ',');
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm5'});
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 await ctx.say('wo0916', async () => {
  await open(c, ctx, 'app/features/properties.csv'); await mark(c, ctx, n);
  await atPhrase(ctx, '자료형은 날짜고요'); await mark(c, ctx, n, {cell: 3, shape: 'underline'});
  await command(c, ctx, 'python run.py parts', 'parts로 모델을');
  await command(c, ctx, 'python run.py check', 'check로 검증하고');
  await command(c, ctx, 'python run.py query', 'query로 다시 묻습니다');
 }, {at: '속성 표에 설치일 줄이'});
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '09g');
 return {segment: 'wo-09g', page: 0, cut, aiRequests: 0, next: 'wo-09h: 결과 화면(PAGE=1) F5 — 질문 4까지 같음'};
};
