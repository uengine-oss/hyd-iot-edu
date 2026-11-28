// 06-2 구간 04e(첫 페이지): R9가 고친 파일을 차례로 열어 보기(decisions · expected · classes · relations · row_rules, properties는 띠만) → python run.py names. Codex 부탁 없음.
// 시작: wo-04d 끝(R9 답이 선 화면, 앞 take를 준다). 끝: 터미널에 결과 줄 — 다음은 wo-04f(PAGE=1). 녹화 뒤 사본 SEG=04e. 큐 wo0485는 대본 wo0416을 나눈 앞쪽(판정 문서 「막힌 곳 ①」).
// 짚는 줄은 Codex가 적은 파일에서 글로 찾는다(PICK 표). 묶은 부탁이 파일 여섯을 다 고치지 않았으면 여기서 멈춘다 — 대본 wo0483 조작 칸대로 빠진 파일만 한 번 더 부탁하는 큐를 더한다.
import {atPhrase} from './lab-common.mjs';
import {ui, QE, PICK, guideIn, seamOut, keepEnd, open, mark, lineOf, lineHas, linesHas, markAll, speechEnd, command} from './wo-common.mjs';

const A = 'app/features/';
export default async ctx => {
 const c = await ui(ctx, 0);
 const need = {decisions: await lineHas(ctx, A + 'decisions.csv', '구성 요소 자리와 그 실물', '실물'), expected: await linesHas(ctx, A + 'expected.csv', x => x.startsWith('1,HYD-02,') && x.includes('실물')),
  classes: await lineOf(ctx, A + 'classes.csv', '실물,'), relations: await lineHas(ctx, A + 'relations.csv', PICK.relUnit, '실물'), rows: await lineOf(ctx, A + 'row_rules.csv', 'components.csv,13,'), props: await linesHas(ctx, A + 'properties.csv', x => x.startsWith('실물,'))};
 if (need.expected.length !== 1 || !need.props.length) throw Error('R9가 expected.csv(HYD-02 실물 줄) · properties.csv(실물 줄)를 다 고치지 않음 — 대본 wo0483 조작 칸대로 빠진 파일만 한 번 더 부탁하는 큐를 정한다: ' + JSON.stringify(need));
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm2'});
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 await ctx.say('wo0483', async () => {
  await open(c, ctx, A + 'decisions.csv'); await mark(c, ctx, need.decisions);
  await mark(c, ctx, need.decisions, {cell: 1, shape: 'underline', keep: true, point: false}); await mark(c, ctx, need.decisions, {cell: 2, shape: 'underline', keep: true, point: false});
  await atPhrase(ctx, '기대 답에는 펌프 줄이'); await open(c, ctx, A + 'expected.csv'); await mark(c, ctx, need.expected[0]);
  await atPhrase(ctx, '클래스 표에는 실물이'); await open(c, ctx, A + 'classes.csv'); await mark(c, ctx, need.classes); await mark(c, ctx, need.classes, {cell: 2, shape: 'underline', keep: true, point: false});
  await atPhrase(ctx, '관계 표에도'); await open(c, ctx, A + 'relations.csv'); await mark(c, ctx, need.relations); await mark(c, ctx, need.relations, {cell: 4, shape: 'underline', keep: true, point: false});
  await atPhrase(ctx, '겹친 줄을 적는 표에는'); await open(c, ctx, A + 'row_rules.csv'); await mark(c, ctx, need.rows);
  await speechEnd(ctx); await open(c, ctx, A + 'properties.csv'); await markAll(c, ctx, need.props);   // 실물의 속성 줄(일련번호 · 비고)은 열어서 띠만 긋고 말하지 않는다
 }, {at: '결정 표에는'});
 await ctx.say('wo0485', async () => { await command(c, ctx, 'python run.py names', 'python run.py names입니다'); }, {at: '돌려 봐야 알죠'});
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '04e');
 return {segment: 'wo-04e', page: 0, cut, aiRequests: 0, next: 'wo-04f: 결과 화면(PAGE=1) F5 — 구성 요소 이름과 실물'};
};
