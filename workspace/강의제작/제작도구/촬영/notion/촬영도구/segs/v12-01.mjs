// v12-01 · 1단계 여는 말 — 시작(준비): config v12.home(Notion 「홈」 화면, 사용자 2026-11-13 결정)을 한 번 열어 둔 뒤 Notion 다운로드 쪽(v12.download)을 연다.
// 끝: 오른쪽 위 「Notion 열기」를 눌러 웹 작업 화면이 열린 상태(그 단추는 마지막으로 본 노션 쪽을 연다 — 그래서 준비에서 v12.home을 먼저 연다).
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:1}];
export async function prepare(c){
 const {raw,serial}=c;const v=c.ctx.v12;
 await serial(()=>raw.goto(v.home,{timeout:150000,waitUntil:'domcontentloaded'}));await serial(()=>raw.waitForFunction(()=>/\| Notion$/.test(document.title)&&!!document.querySelector('[role=treeitem]'),undefined,{timeout:90000}));await c.sleep(1500);
 // 녹화 밖: 리허설 · 앞 촬영이 남긴 콜아웃 기억 색(localStorage …:calloutBlockBackground)과 최근 사용 색을 비우고 다시 불러온다 — 비우지 않으면
 // 4단계 첫 상자가 기본 회색이 아니라 마지막에 쓴 색으로 생긴다(take-k9-v12-04). 처음부터 찍을 때만 한다(중간부터 이어 찍으면 앞 단계가 쓴 색이 맞다).
 const left=await serial(()=>raw.evaluate(()=>{const ks=Object.keys(localStorage).filter(k=>/:calloutBlockBackground$|:recentlyUsedHighlightColors$/.test(k));ks.forEach(k=>localStorage.removeItem(k));return ks;}));
 await c.fs.appendFile(c.out+'/reset.jsonl',JSON.stringify({removed:left})+String.fromCharCode(10));
 if(left.length){await serial(()=>raw.goto(v.home,{timeout:150000,waitUntil:'domcontentloaded'}));await serial(()=>raw.waitForFunction(()=>/\| Notion$/.test(document.title)&&!!document.querySelector('[role=treeitem]'),undefined,{timeout:90000}));await c.sleep(1500);}
 // 녹화 밖: 「홈」이 영어로 그려졌으면 한국어가 될 때까지 다시 불러온다(시험 lang1 — 서비스 워커를 거치지 않게 한 뒤에도 첫 불러오기 한 번이 영어였다).
 if((await c.lang())!=='ko')await c.ensureKorean();
 if(!(await serial(()=>raw.evaluate(()=>document.title))).startsWith('홈 |'))throw Error('v12.home이 「홈」이 아님: '+(await serial(()=>raw.evaluate(()=>document.title))));
 // 학생 첫 화면은 왼쪽 목록이 펼쳐져 있다. 앞 실행이 접어 두었으면 녹화 밖에서 편다(k2 직전: 접혀 있었다).
 if(await serial(()=>raw.evaluate(()=>!!document.querySelector('[aria-label="사이드바 열기"]')))){await serial(()=>raw.mouse.move(20,20));await c.sleep(500);await serial(()=>raw.click('[aria-label="사이드바 열기"]'));await c.sleep(1200);}
 await serial(()=>raw.goto(v.download,{timeout:150000,waitUntil:'domcontentloaded'}));
 await serial(()=>raw.waitForSelector('a[aria-label="Windows용 Notion 다운로드"]',{timeout:20000}));
 const q=await serial(()=>raw.evaluate(()=>{const r=document.querySelector('a[aria-label="Windows용 Notion 다운로드"]').getBoundingClientRect();return{x:Math.round(r.x+r.width*0.8),y:Math.round(r.bottom+40)};}));
 await c.place(q);
}
export const ops=c=>({1:{
 // 「Notion 열기」(로그인된 계정)는 같은 탭에서 앱으로 간다. 앱이 뜨면 화살표를 다시 그리고 녹화를 그 문서에서 다시 받는다.
 노션열기:async()=>{const sel=await c.mark({css:'button',text:'Notion 열기',first:true});const q=await c.serial(()=>c.raw.evaluate(s=>{const r=document.querySelector(s).getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};},sel));
  await c.click('css',sel);await c.serial(()=>c.raw.waitForFunction(()=>location.host.startsWith('app.notion')&&!!document.querySelector('[role=treeitem]'),undefined,{timeout:30000}));
  await c.sleep(1500);if((await c.lang())!=='ko')throw Error('Notion opened in English (lang=en) — 이 take는 쓸 수 없다: v12-01부터 다시');
  // 「홈」으로 돌아와야 한다(대본 첫 화면). 다른 쪽이 열렸으면 이 take는 쓸 수 없다.
  if(!(await c.serial(()=>c.raw.evaluate(()=>document.title))).startsWith('홈 |'))throw Error('「Notion 열기」 뒤 홈이 아닌 쪽이 열림: '+(await c.serial(()=>c.raw.evaluate(()=>document.title))));
  await c.place(q);await c.ctx.restartCapture();},
}});
