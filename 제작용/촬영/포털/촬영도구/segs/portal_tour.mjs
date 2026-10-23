// 포털 소개 구간(1회차 실습2 뒷부분). 큐 · 조작은 ../포털소개_큐.json, 대상 이름 → 화면 요소는 아래 target().
// 리듬: 조작마다 문장 안 시점(0~1)에 출발한다. click은 대상에 닿은 뒤 바로 누르고, select는 칸을 누른 뒤 값을 고른다.
// 결과(새 화면)는 누른 뒤에 나오므로, 그 화면 설명은 다음 문장이 맡는다.
import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {portal} from '../ui.mjs';
const HERE=fileURLToPath(new URL('.',import.meta.url));
export const CUES=HERE+'../../포털소개_큐.json';
const FIXED={
 'top:진행 중':{css:'#openCount',anchor:'below'},
 'top:서비스':{css:'#healthDots span',anchor:'below'},
 'top:나 고르기':{css:'#inboxBadge button',anchor:'below'},
 'top:알림':{css:'#shellBell',anchor:'below'},
 'inbox-me':{css:'select[data-inbox-me]',anchor:'right'},
 'scen:HYD-01':{text:'HYD-01',tag:'strong',anchor:'below'},
 'scen:HYD-03':{text:'HYD-03',tag:'strong',anchor:'below'},
 'scen:유온':{css:'.big.num small',nth:0,anchor:'after'},
 'scen:보호 정지':{css:'.threshold-note',nth:0,anchor:'below'},
 'scen:냉각 효율':{css:'.kv span',contains:'냉각 효율',nth:0,anchor:'after'},
 'scen:경보':{text:'경보',tag:'span',nth:0,anchor:'after'},
 'scen:쿨러 열화 주입':{text:'쿨러 열화 주입',tag:'button',anchor:'below',top:300},
 'inc:HYD-01':{text:'HYD-01',tag:'strong',anchor:'below'},
 'trend:graph':{css:'#pTs1',dy:20},
 'flow:diagram':{text:'업무 흐름',anchor:'below'},
 'onto:count':{css:'#ontoStats',anchor:'below',dx:117},
 'know:파일 선택':{text:'파일 선택',tag:'span',nth:0,anchor:'after'},
 'fab:연결됨':{text:'연결됨',tag:'b',nth:0,anchor:'after'},
};
export function target(name){
 if(FIXED[name])return FIXED[name];
 const [k,v]=name.split(/:(.*)/s);
 if(k==='tab')return{tab:v,anchor:'right'};
 if(k==='group')return{text:v,within:'.rail',tag:'.navgroup',anchor:'after'};
 if(k==='card')return{text:v,within:'.card',tag:'span',anchor:'after'};
 if(k==='map'||k==='flow')return{text:v,tag:'text',anchor:'below'};
 if(k==='onto')return{text:v,tag:'text',anchor:'below'};
 if(k==='agent')return{text:v,tag:'strong',anchor:'after'};
 if(k==='text')return{text:v,anchor:'below'};
 throw Error('unknown portal target '+name);
}
// 조작 하나. dry(녹화 없음 · 대상 확인)에서도 같은 함수를 쓴다.
export async function op(c,o){
 const [kind,name]=o;const t=target(name);
 if(kind==='point')return c.point(t);
 if(kind==='click')return c.click(t);
 if(kind==='scroll')return c.scrollTop(t,t.top??96);
 if(kind==='select')return c.select(t,o[2]);
 throw Error('unknown op '+kind);
}
const frac=o=>o[0]==='select'?o[3]:o[2];
export async function seg(ctx,n){
 const cues=JSON.parse(await fs.readFile(CUES,'utf8')).cues.filter(c=>c.segment===n);
 const c=await portal(ctx);
 // 녹화 전(화면에 남지 않음): 구간 1은 포털 홈 맨 위에서 시작한다. 다른 구간은 앞 구간 끝 화면 그대로.
 // 「나」는 브라우저(localStorage hyd.me)에 남으므로 지우고 새로 열어 「나 고르기」 상태로 시작한다.
 if(n===1){if(!ctx.p.url().startsWith('http://127.0.0.1:8088/'))await ctx.p.goto('http://127.0.0.1:8088/',{waitUntil:'domcontentloaded'});
  await ctx.p.evaluate(()=>localStorage.removeItem('hyd.me'));await ctx.p.reload({waitUntil:'domcontentloaded'});await ctx.sleep(2000);
  await ctx.p.evaluate(()=>{document.querySelector('.rail nav button[data-tab="main"]').click();for(const e of document.querySelectorAll('.rail,main#content'))e.scrollTop=0;});
  await ctx.sleep(2500);await ctx.installPointer({x:760,y:430});}
 // 구간 3: 실시간 모니터링 그래프(Grafana)는 처음 열 때 8초쯤 걸린다. 녹화 전에 한 번 열어 두고 앞 구간 끝 메뉴로 돌아온다.
 if(n===3){const back=await ctx.p.evaluate(()=>document.querySelector('.rail nav button.active')?.dataset.tab);
  await ctx.p.evaluate(()=>document.querySelector('.rail nav button[data-tab="trends"]').click());await ctx.sleep(10000);
  await ctx.p.evaluate(b=>document.querySelector(`.rail nav button[data-tab="${b}"]`).click(),back);await ctx.sleep(1500);}
 await ctx.begin();
 for(const q of cues){
  const dur=JSON.parse(await fs.readFile(ctx.audio+'/'+q.id+'.json','utf8')).duration_ms;
  const ops=q.ops||[];const lead=300;
  const fn=ops.length?async()=>{const start=Date.now()-lead;   // 큐(음성) 시작 시각
   for(let i=0;i<ops.length;i++){const due=start+Math.round(dur*(frac(ops[i])??0))-Date.now();if(due>0)await ctx.sleep(due);
    ctx.commitAt=0;await op(c,ops[i]);}}:null;
  await ctx.say(q.id,fn,{pointFrac:0,pointDelay:lead});
 }
 return {pos:c.pos()};
}
