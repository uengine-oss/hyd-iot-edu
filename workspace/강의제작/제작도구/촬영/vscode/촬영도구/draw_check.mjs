// 화면 위 그림 층(draw.mjs)과 녹화 제어(ctrl.mjs)의 자가시험 — 녹화 브라우저(run.sh up)와 웹 VS Code 없이, 이 PC의 Playwright(포털 촬영도구 env.mjs가 찾는 자리)로 띄운 흉내 화면에서 돈다.
//   node draw_check.mjs [출력 폴더]        기본 출력 = <work>/draw-check-<시각>/ (work = config.json)
// 하는 일: ① ctrl.mjs의 run()으로 흉내 화면을 실제로 녹화한다(구간 = 이 파일의 default) — 강조 넷(띠 · 밑줄 · 테두리 · 함께 두기), Codex 패널 비율 상자,
//   펜 그림(한 획씩 긋기 · 걷기 · 다시 띄우기 · 지금 여기 동그라미 · 덧긋기 · 덧쓰기), 글상자와 그 줄 강조. 조작마다 화면의 그림 층을 재어 어긋나면 멈춘다.
//   녹화가 남긴 timing.json의 강조마다 떠 있을 때와 지워진 뒤의 프레임을 <출력>/확인/에 뽑는다(눈으로 본다: 글을 가리는지, 이웃 줄을 가로지르는지, 흔적이 남는지).
//   ② 말만 하는 큐 둘로 ctrl.mjs의 기본 큐 쉼(1300ms)을 잰다. ③ 일부러 깨뜨린 입력 아홉을 리허설(dry)로 돌려, 모두 큐 id를 대며 멈추는지 본다.
// 끝줄 「그림 층 자가시험 통과」가 나오고 종료 코드가 0이면 통과다. 실제 웹 VS Code의 선택자 · Codex 답의 자리는 이 시험이 보지 않는다 — 구간 모듈의 run.sh dry가 본다.
import fs from 'node:fs/promises';
import {fileURLToPath,pathToFileURL} from 'node:url';

const HERE=fileURLToPath(new URL('.',import.meta.url)).replace(/\\/g,'/');
const SELF=pathToFileURL(fileURLToPath(import.meta.url)).href;
const CASE=new URL(import.meta.url).searchParams.get('case')?.split('?')[0]??null;   // ctrl.mjs가 모듈 주소 끝에 ?<시각>을 붙인다

const FLOW={id:'설계 흐름',board:[110,300,1700,400],items:[
 {id:'q1',kind:'box',at:[160,400,340,130],text:'역량 질문'},
 {id:'q2',kind:'box',at:[580,400,340,130],text:'질문의 낱말을\n클래스 · 속성 · 관계로'},
 {id:'q3',kind:'box',at:[1000,400,340,130],text:'정의 표로 적기'},
 {id:'q4',kind:'box',at:[1420,400,340,130],text:'인스턴스를 넣어\n질문에 답해 보기'},
 {id:'a12',kind:'arrow',from:'q1',to:'q2'},{id:'a23',kind:'arrow',from:'q2',to:'q3'},{id:'a34',kind:'arrow',from:'q3',to:'q4'},
 {id:'back',kind:'arrow',from:'q4',to:'q1',route:'under',drop:70},
 {id:'db',kind:'text',at:[1520,340],text:'그래프 DB',color:'red'},
]};
const CUES={
 'dc-0101':['현장 메모 끝에 물음이 세 가지 있습니다. 첫째는 센서가 어디 붙어 있는지, 둘째는 센서끼리 견줄 수 있는지, 셋째는 부품을 어느 설비가 같이 쓰는지예요.',9000],
 'dc-0102':['쿼리에서 이 조각이 설비 코드를 받는 자리이고, 터미널의 두 줄을 견줘 보면 개수가 다릅니다. 표에서는 이 칸이 답이에요.',9000],
 'dc-0103':['Codex 답에서는 이 줄을 봅니다. 그리고 파일을 엽니다.',5000],
 'dc-0104':['설계가 어떤 차례로 가는지 그려 볼게요. 맨 먼저 역량 질문입니다. 다음 칸은 낱말을 옮기는 칸이에요. 고른 것은 정의 표로 적습니다. 마지막 칸은 질문에 답해 보기입니다. 질문에서 시작해서 질문으로 돌아오죠.',15000],
 'dc-0105':['그림을 다시 띄워 보면 지금은 둘째 칸입니다. 넷째 칸의 질문에 답해 보기는 그래프 DB에서 합니다. 남은 것은 이 화살표예요.',10000],
 'dc-0106':['요령은 여덟 가지입니다. 이번에 쓴 것은 한 번에 기능 하나씩, 그리고 선택지와 그 결과를 받아 내가 고르기예요.',8000],
 'dc-0107':['터미널의 끝 줄입니다.',2500],
 'gp-0101':['말만 하는 첫 큐입니다.',1200],'gp-0102':['말만 하는 둘째 큐입니다.',1200],
};
const TIPS=['자료는 예 줄과 개수로 묻기','무엇을 정할지 모르면 AI가 나에게 묻게 하기','한 번에 기능 하나씩','선택지와 그 결과를 받아 내가 고르기','됐습니다를 믿지 말고 직접 보기','시험용 요령 여섯','시험용 요령 일곱','시험용 요령 여덟'];

// 흉내 화면: 웹 VS Code의 칸 이름(편집기 줄 · 터미널 줄 · 탐색기 · Codex 패널)과 결과 표만 같은 선택자로 둔다. 편집기의 빈칸은 실제처럼 줄바꿈 없는 빈칸이다.
const nb=s=>s.replace(/ /g,'\u00a0');
const NOTES=['# 현장 메모','','## 4. 이 정리로 알고 싶은 것','','- 센서가 어느 설비의 어느 구성 요소에 붙어 있는지','- 같은 것을 재는 센서끼리 견줄 수 있는지','- 부품을 어느 설비들이 같이 쓰는지','','MERGE (a:Asset {code: row.code})','SET a.name = row.name','RETURN count(a) AS 설비'];
const PAGE=`<!doctype html><meta charset="utf-8"><title>draw-check</title><style>
html,body{margin:0;height:100%;background:#1f1f1f;color:#ccc;font:16px/1.4 'Malgun Gothic',sans-serif;overflow:hidden}
.wb{display:grid;grid-template-columns:270px 1fr 470px;grid-template-rows:1fr 240px 27px;height:100vh}
.explorer-folders-view{grid-row:1/3;background:#181818;padding:8px 0}.monaco-list-row{padding:3px 18px;height:22px;box-sizing:border-box}
.part.editor{background:#1f1f1f;overflow:hidden;position:relative}.editor-scrollable{position:absolute;inset:34px 0 0 0;overflow:hidden}
.view-lines{position:absolute;left:64px;top:0;font:17px/23px Consolas,'Malgun Gothic',monospace;color:#d4d4d4}.view-line{height:23px;white-space:pre}
.tabs{height:34px;background:#181818;line-height:34px;padding-left:16px}
.terminal-wrapper{background:#181818;border-top:1px solid #333;padding:8px 14px;overflow:hidden}.xterm-rows{font:16px/21px Consolas,'Malgun Gothic',monospace}.xterm-rows>div{height:21px;white-space:pre}
.part.auxiliarybar{grid-row:1/3;grid-column:3;background:#181818;border-left:1px solid #333;padding:0;position:relative}
.answer{position:absolute;left:6%;right:6%;top:12%}.answer p{margin:0;height:26px;line-height:26px}
.statusbar{grid-column:1/4;background:#0078d4;color:#fff;padding-left:10px;line-height:22px;font-size:12px}
table{position:absolute;right:30px;top:60px;border-collapse:collapse;font-size:13px}td,th{border:1px solid #444;padding:4px 10px}
</style><div class="wb">
<div class="explorer-folders-view">${['data','equipment.csv','field_notes.md','app','README.md'].map(n=>`<div class="monaco-list-row"><span class="label-name">${n}</span></div>`).join('')}</div>
<div class="part editor"><div class="tabs">field_notes.md</div><div class="editor-instance"><div class="monaco-editor"><div class="editor-scrollable"><div class="view-lines">
${NOTES.map(l=>`<div class="view-line"><span>${nb(l)}</span></div>`).join('')}
<div class="view-line" style="position:absolute;top:900px"><span>${nb('- 화면 아래로 굴러간 줄')}</span></div>
</div></div></div></div>
<table><thead><tr><th>센서</th><th>설비</th><th>구성 요소</th></tr></thead><tbody><tr><td>TS1</td><td>HYD-01</td><td>오일 탱크</td></tr><tr><td>PS1</td><td>HYD-01</td><td>주 펌프</td></tr></tbody></table></div>
<div class="part auxiliarybar"><div class="answer">${['자료를 읽었습니다.','표는 다섯 개입니다.','설비 대장은 5줄, 구성 요소 목록은 41줄입니다.','잇는 칸은 설비코드입니다.','이 두 기준은 어떻게 볼까요?'].map(s=>`<p>${s}</p>`).join('')}</div></div>
<div class="terminal-wrapper"><div class="xterm-rows">${['D:\\HYD-Practice\\ontology-lab>python run.py','설비 5','구성 요소 41','센서 41','결과: output/result.html'].map(l=>`<div>${l}</div>`).join('')}</div></div>
<div class="statusbar">main</div></div>`;

// ── 구간(ctrl.mjs가 부른다) ──
const state=p=>p.evaluate(()=>{const r=document.getElementById('recording-draw'),b=e=>{const x=e.getBoundingClientRect();return [x.x,x.y,x.width,x.height].map(v=>Math.round(v*10)/10);};
 return {marks:[...(r?.querySelectorAll('[data-mark]')||[])].map(g=>[...g.children].map(b)),fig:r?.querySelector('[data-fig]')?.dataset.fig??null,
  pens:[...(r?.querySelectorAll('[data-fig] [data-pen],[data-fig] [data-stroke]')||[])].map(e=>e.dataset.pen||e.dataset.stroke),penmarks:[...(r?.querySelectorAll('[data-penmark]')||[])].map(e=>e.dataset.penmark),
  note:r?.querySelectorAll('[data-note] [data-line]').length??0,children:r?r.children.length:0};});
const rectOf=(p,sel,find)=>p.evaluate(({sel,find})=>{const e=[...document.querySelectorAll(sel)].find(x=>x.textContent.replace(/\u00a0/g,' ').includes(find));const b=e.getBoundingClientRect();return [b.x,b.y,b.width,b.height];},{sel,find});
const need=(ok,msg,got)=>{if(!ok)throw Error('자가시험: '+msg+(got===undefined?'':' — '+JSON.stringify(got)));};
const near=(a,b,d=1.5)=>Math.abs(a-b)<=d;

async function main_seg(ctx){
 const {labUi,atPhrase,em}=await import(new URL('segs/lab-common.mjs',SELF).href);
 const c=await labUi(ctx),p=ctx.p,settle=()=>ctx.sleep(320);
 await ctx.begin();
 // 1) 편집기 줄을 말에 맞춰 한 줄씩(띠): 다음 강조가 뜨면 앞 강조는 지워진다
 await ctx.say('dc-0101',async()=>{
  for(const [ph,line] of [['첫째는','- 센서가'],['둘째는','- 같은 것을'],['셋째는','- 부품을']]){
   if(ph!=='첫째는')await atPhrase(ctx,ph);
   await c.emph(em.line(line));await settle();
   const s=await state(p),r=await rectOf(p,'.view-line',line),g=await rectOf(p,'.view-line span',line);
   need(s.marks.length===1&&s.marks[0].length===1,'띠가 하나만 떠 있어야 한다('+line+')',s.marks);
   const m=s.marks[0][0];need(m[1]>=r[1]-0.5&&m[1]+m[3]<=r[1]+r[3]+0.5,'띠가 그 줄 높이를 벗어났다(이웃 줄을 가로지름)',{m,r});need(near(m[0],g[0])&&near(m[2],g[2]),'띠가 그 줄 글과 어긋났다',{m,g});
  }},{at:'첫째는'});
 // 2) 구절 밑줄 → 터미널 두 줄을 함께(keep) → 표의 칸 테두리
 await ctx.say('dc-0102',async()=>{
  await c.emph(em.line('MERGE'),{shape:'underline',phrase:'row.code'});await settle();
  let s=await state(p);const ln=await rectOf(p,'.view-line','MERGE'),nx=await rectOf(p,'.view-line','SET a.name');
  need(s.marks.length===1,'밑줄 하나',s.marks);const u=s.marks[0][0];
  need(u[1]>=ln[1]+ln[3]-4&&u[1]+u[3]<=nx[1]+6,'밑줄이 글자 아래 · 다음 줄 글 위에 있지 않다',{u,ln,nx});need(u[2]<ln[2]/2+60,'밑줄이 구절보다 훨씬 길다',u);
  await atPhrase(ctx,'터미널의 두 줄');
  await c.emph(em.term('설비 5'));await c.emph(em.term('구성 요소 41'),{keep:true});await settle();
  s=await state(p);need(s.marks.length===2,'견주는 두 줄의 띠가 함께 떠 있어야 한다',s.marks);
  await atPhrase(ctx,'표에서는');
  await c.emph(em.row('TS1',2),{shape:'box'});await settle();
  s=await state(p);const td=await rectOf(p,'td','오일 탱크');need(s.marks.length===1,'테두리가 뜨면 앞의 두 띠는 지워져야 한다',s.marks);
  const b=s.marks[0][0];need(b[0]<td[0]&&b[1]<td[1]&&b[0]+b[2]>td[0]+td[2]&&b[1]+b[3]>td[1]+td[3],'테두리가 칸을 두르지 않는다',{b,td});
 },{at:'이 조각'});
 // 3) Codex 패널의 비율 상자(웹뷰는 글을 잴 수 없다) → 누르기가 시작하면 강조가 지워진다
 await ctx.say('dc-0103',async()=>{
  const r=await p.evaluate(()=>{const A=document.querySelector('.part.auxiliarybar').getBoundingClientRect(),b=document.querySelectorAll('.answer p')[2].getBoundingClientRect();return [(b.x-A.x)/A.width,(b.y-A.y)/A.height,(b.right-A.x)/A.width,(b.bottom-A.y)/A.height];});
  await c.emph(em.codex(...r));await settle();
  need((await state(p)).marks.length===1,'Codex 패널 띠');
  await atPhrase(ctx,'파일을');
  const q=await c.point('.explorer-folders-view .label-name','field_notes.md');
  await c.clickAt(q.x,q.y);await settle();
  need((await state(p)).marks.length===0,'누른 뒤에 강조가 남았다');
 },{at:'이 줄'});
 // 4) 펜 그림을 말에 맞춰 한 획씩 → 지금 여기 동그라미 → 걷기(흔적 없음)
 const fig=c.pen(FLOW);
 await ctx.say('dc-0104',async()=>{
  await fig.draw('q1');
  await atPhrase(ctx,'다음 칸은');await fig.draw('a12','q2');
  await atPhrase(ctx,'고른 것은');await fig.draw('a23','q3');
  await atPhrase(ctx,'마지막 칸은');await fig.draw('a34','q4');
  await atPhrase(ctx,'질문으로 돌아오죠');await fig.draw('back');
  let s=await state(p);need(s.fig==='설계 흐름'&&['q1','q2','q3','q4','a12','a23','a34','back'].every(i=>s.pens.includes(i))&&!s.pens.includes('db'),'그린 것이 정의의 여덟이 아니다',s.pens);
  await fig.ring('q1');await fig.point('q1');
  s=await state(p);need(s.penmarks.join()==='q1','지금 여기 동그라미',s.penmarks);
  await ctx.sleep(900);await fig.hide();await settle();
  s=await state(p);need(s.fig===null&&s.children===0,'걷은 뒤 그림 층에 남은 것이 있다',s);
 },{at:'맨 먼저 역량 질문'});
 // 5) 다시 띄우기 → 다른 칸에 동그라미 → 칸 글의 구절에 밑줄 → 덧쓰기 → 화살표 덧긋기 → 걷기
 await ctx.say('dc-0105',async()=>{
  await fig.show('q1','q2','q3','q4','a12','a23','a34','back');await fig.ring('q2');
  let s=await state(p);need(s.pens.length===12&&s.penmarks.join()==='q2','다시 띄운 그림',s);   // 칸 넷은 획 + 글 = 8, 화살표 넷
  await atPhrase(ctx,'질문에 답해 보기');
  await c.emph({pen:'q4'},{shape:'underline',phrase:'질문에 답해 보기'});await settle();
  s=await state(p);need(s.marks.length===1&&s.marks[0].length===1,'칸 글의 구절 밑줄',s.marks);
  await atPhrase(ctx,'그래프 DB');await fig.draw('db');
  await atPhrase(ctx,'이 화살표');await fig.trace('back');
  await settle();s=await state(p);need(s.penmarks.join()==='back'&&s.pens.includes('db')&&s.marks.length===0,'덧긋기는 앞 동그라미와 앞 강조를 지우고 화살표에 그어진다',s);
  await ctx.sleep(900);await fig.hide();await settle();
  s=await state(p);need(s.children===0,'걷은 뒤 그림 층에 남은 것이 있다(강조 포함)',s);
 },{at:'다시 띄워'});
 // 6) 글상자와 그 줄 강조(둘을 함께) → 걷기
 await ctx.say('dc-0106',async()=>{
  await c.note(TIPS,{title:'AI를 잘 쓰는 요령 여덟',at:'tr'});
  await atPhrase(ctx,'한 번에 기능 하나씩');await c.emph({note:'한 번에 기능 하나씩'},{point:false});
  await atPhrase(ctx,'선택지와');await c.emph({note:4},{keep:true,point:false});await settle();
  let s=await state(p);need(s.note===8&&s.marks.length===2,'글상자 여덟 줄과 강조 둘',s);
  await ctx.sleep(1200);await c.note(null);await settle();
  s=await state(p);need(s.children===0,'글상자를 걷은 뒤 남은 것이 있다',s);
 },{at:'요령은'});
 // 7) 구간 끝까지 남는 강조 — ctrl.mjs가 마지막 말이 끝날 때 지운다
 await ctx.say('dc-0107',async()=>{await c.emph(em.term('결과: output'));},{at:'끝 줄'});
 return {view:'draw-check'};
}

// 일부러 깨뜨린 입력(리허설로 돈다). [큐 id, 오류에 있어야 할 말, 조작]
const BROKEN={
 none:['dc-9001','보이는 대상이 0개',c=>c.emph({sel:'.no-such-thing'})],
 many:['dc-9002','보이는 대상이 2개',c=>c.emph({sel:'.view-line',has:'센서'})],
 phrase:['dc-9003','구절 「없는 구절」',c=>c.emph({sel:'.view-line',starts:'MERGE'},{shape:'underline',phrase:'없는 구절'})],
 shape:['dc-9004','모르는 강조 모양',c=>c.emph({sel:'.view-line',starts:'MERGE'},{shape:'wave'})],
 rolled:['dc-9005','밖으로 굴러가',c=>c.emph({sel:'.view-line',starts:'- 화면 아래로'})],
 edge:['dc-9006','화면',c=>c.emph({box:[1908,300,10,20]},{shape:'box',point:false})],
 penid:['dc-9007','정의에 없는 것: q9',c=>c.pen(FLOW).draw('q9')],
 nonote:['dc-9008','떠 있는 글상자가 없음',c=>c.note(null)],
 left:['dc-9009','구간 끝에 펜 그림',c=>c.pen(FLOW).show()],
};
export default async function seg(ctx){
 if(!CASE)return main_seg(ctx);
 const {vscode}=await import(new URL('ui.mjs',SELF).href);const c=await vscode(ctx);
 if(CASE==='gap'){await ctx.begin();await ctx.say('gp-0101');await ctx.say('gp-0102');return {};}
 const [id,,op]=BROKEN[CASE];await ctx.say(id,()=>op(c));return {};
}

// ── 시험 본체(node draw_check.mjs) ──
if(!new URL(import.meta.url).search){
 const {playwright}=await import(new URL('../../포털/촬영도구/env.mjs',SELF).href);
 const CFG=JSON.parse(await fs.readFile(HERE+'config.json','utf8'));
 const work=fileURLToPath(new URL(CFG.work+'/',SELF)).replace(/\\/g,'/').replace(/\/$/,'');
 const out=(process.argv[2]||work+'/draw-check-'+new Date().toISOString().replace(/[-:T]/g,'').slice(0,14)).replace(/\\/g,'/');
 const audio=out+'/audio';await fs.mkdir(audio,{recursive:true});
 for(const [id,[text,duration_ms]] of Object.entries(CUES))await fs.writeFile(audio+'/'+id+'.json',JSON.stringify({text,duration_ms}));
 const browser=await playwright().chromium.launch();const VP={width:1920,height:1080,dsf:1};   // 헤드리스 Chromium의 screencast는 CSS 크기로 프레임을 준다 — 프레임 1920×1080을 받으려고 배율 1로 둔다(실제 녹화는 CSS 1843×1037)
 const page=await browser.newPage({viewport:{width:VP.width,height:VP.height},deviceScaleFactor:VP.dsf});await page.setContent(PAGE);
 const {run}=await import(new URL('ctrl.mjs',SELF).href);
 const fail=[];const check=(ok,msg,got)=>{if(!ok){fail.push(msg+(got===undefined?'':' — '+JSON.stringify(got)).slice(0,600));console.log('  실패: '+fail.at(-1));}};
 const base={work:out,audio,viewport:VP,page};   // 녹화 브라우저 대신 이 흉내 화면을 ctrl.mjs에 넘긴다(page.mjs wrap이 CDP 세션을 단다)
 try{
  // ① 녹화
  const r=await run({...base,name:'rec',moduleUrl:SELF,pointer:{x:700,y:400}});
  check(!r.error,'녹화가 오류로 끝났다',r.error);
  const t=JSON.parse(await fs.readFile(out+'/rec/timing.json','utf8')),hs=t.highlights||[];
  console.log(`녹화 ${Math.round(t.duration/100)/10}초 · 프레임 ${t.frames.length} · 큐 ${t.actions.length} · 강조 ${hs.length} · 그림 기록 ${t.drawings?.length}`);
  check(t.actions.length===7,'큐 수 7',t.actions.length);check(hs.length===12,'강조 수 12',hs.length);
  check(hs.every(h=>h.end>h.start&&h.rects.length),'강조마다 시작 < 끝 · 상자',hs.filter(h=>!(h.end>h.start)));
  const by=k=>hs.filter(h=>h.endBy===k).length;
  check(by('다음 강조')===7&&by('커서 이동')===1&&by('다음 대상')===1&&by('글상자 걷기')===2&&by('구간 끝')===1,'끝난 까닭',hs.map(h=>h.cue+' '+h.shape+' '+h.endBy));
  const last=hs.at(-1),sp=t.actions.at(-1);check(last&&last.endBy==='구간 끝'&&Math.abs(last.end-(sp.time+sp.duration))<250,'구간 끝 강조는 마지막 말이 끝날 때 지워진다',{end:last?.end,speech:sp.time+sp.duration});
  check(await page.evaluate(()=>!document.querySelector('#recording-draw [data-mark], #recording-draw [data-fig], #recording-draw [data-note]')),'녹화 뒤 화면에 그림 층이 남았다');
  // 확인 프레임: 화면이 바뀔 때만 프레임이 오므로, 그 시각의 화면 = 그 시각보다 앞선 마지막 프레임
  const fr=[...t.frames].sort((a,b)=>a.time-b.time),at=ms=>fr.filter(f=>f.time<=ms).at(-1)??fr[0];
  await fs.mkdir(out+'/확인',{recursive:true});let n=0;
  const keep=async(ms,label)=>{const f=at(ms);await fs.copyFile(out+'/rec/'+f.file,out+'/확인/'+String(++n).padStart(2,'0')+'_'+label+'.jpg');};
  for(const [i,h] of hs.entries()){await keep(Math.min(h.end-60,h.start+700),h.cue+'_강조'+(i+1)+'_'+h.shape);if(['커서 이동','다음 대상','글상자 걷기','구간 끝'].includes(h.endBy))await keep(h.end+380,h.cue+'_강조'+(i+1)+'_지운뒤');}
  const ds=t.drawings||[];for(const [i,d] of ds.entries()){const next=ds[i+1]?.time??d.time+2500;await keep(Math.min(next-40,d.time+2500),d.cue+'_'+(d.pen?'펜_'+d.op+(d.ids?'_'+d.ids.join('+'):''):'글상자_'+d.note+'줄'));}
  // ② 기본 큐 쉼
  const g=await run({...base,name:'gap',moduleUrl:SELF+'?case=gap',pointer:{x:700,y:400}});check(!g.error,'쉼 녹화 오류',g.error);
  const ga=JSON.parse(await fs.readFile(out+'/gap/timing.json','utf8')).actions,gap=ga[1].time-(ga[0].time+ga[0].duration);
  console.log('기본 큐 쉼 '+gap+'ms');check(gap>=1290&&gap<1400,'ctrl.mjs의 기본 큐 쉼이 1300ms가 아니다(타이머 오차 10ms까지)',gap);
  // ③ 깨뜨린 입력: 리허설이 큐 id와 까닭을 대며 실패해야 하고, 화면에 아무것도 남기지 않는다
  for(const [name,[id,why]] of Object.entries(BROKEN)){
   const d=await run({...base,name:'x-'+name,moduleUrl:SELF+'?case='+name,dry:true});
   const ok=d.ok===false&&String(d.error).includes(why)&&(name==='left'||String(d.error).includes(id));
   console.log(`깨뜨림 ${name}: ${ok?'멈춤':'안 멈춤'} — ${String(d.error).split('\n')[0].slice(0,150)}`);check(ok,'깨뜨린 입력 '+name+'이 큐 id와 까닭을 대며 멈추지 않았다',d.error);
   check(await page.evaluate(()=>!document.getElementById('recording-draw')),'리허설 뒤 화면에 그림 층이 남았다('+name+')');
  }
 }finally{await browser.close();}
 console.log('출력: '+out+' (확인 프레임 '+out+'/확인/)');
 if(fail.length){console.log('그림 층 자가시험 실패 '+fail.length+'건');process.exit(1);}
 console.log('그림 층 자가시험 통과');
}
