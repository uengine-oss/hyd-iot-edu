// README 설명 구간(1회차 실습2 앞부분). 큐 · 조작은 ../README_큐.json, 대상 이름 → 화면 요소는 아래 TARGETS.
// 리듬: 문장 시작 직후 그 줄의 첫 대상을 짚고(가리키며 설명), 대상이 여럿이면 문장 길이에 나눠 차례로 옮긴다. 스크롤은 「내려가겠습니다」 시점.
import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {portal} from '../ui.mjs';
const HERE=fileURLToPath(new URL('.',import.meta.url));
const A='article.markdown-body';
const TARGETS={
 'repo-title':{css:'#repo-title-component strong a, strong[itemprop=name] a',anchor:'below'},
 'file-list':{css:'table[aria-labelledby="folders-and-files"]',anchor:'pad',dy:120},
 'readme-title':{css:`${A} .markdown-heading`,nth:0},
 'readme-intro':{css:`${A} > p`,nth:0,anchor:'margin'},
 'where-table':{css:`${A} table`,nth:0,anchor:'pad'},
 'compose-intro':{css:`${A} > p`,contains:'설비 데이터 수집',anchor:'margin'},
 'image-sentence':{css:`${A} > p`,contains:'Docker 이미지는',anchor:'margin'},
 'volume-sentence':{css:`${A} > p`,contains:'Docker 이미지는',anchor:'margin',dy:36},
 'env-intro':{css:`${A} > p`,contains:'Windows에서는 Git Bash와',anchor:'margin'},
 'env-table-head':{css:`${A} thead`,contains:'프로젝트 준비 기준',anchor:'pad'},
 'wsl-intro':{css:`${A} > p`,contains:'이 프로젝트는 Windows의 Git Bash',anchor:'margin'},
 'wsl-docker-desktop':{css:`${A} > p code`,contains:'docker-',anchor:'below'},
 'wsl-warning':{css:`${A} > p strong`,contains:'wsl --install',anchor:'below'},
 'code-button':{text:'Code',tag:'button',anchor:'below'},
};
function target(name){
 if(TARGETS[name])return TARGETS[name];
 const [k,v]=name.split(/:(.*)/s);
 if(k==='h')return{css:`${A} .markdown-heading`,contains:v};
 if(k==='row')return{css:`${A} tr`,contains:v,nth:0,anchor:'pad'};
 if(k==='env')return{css:`${A} tr`,cell0:v,anchor:'pad'};
 if(k==='env-check')return{css:`${A} tr`,cell0:v,cell:3,anchor:'pad'};
 if(k==='pre')return{css:`${A} pre`,nth:Number(v),anchor:'pad'};
 throw Error('unknown README target '+name);
}
export async function seg(ctx,n){
 const cues=JSON.parse(await fs.readFile(HERE+'../../README_큐.json','utf8')).cues.filter(c=>c.segment===n);
 const c=await portal(ctx);
 // 녹화 전(화면에 남지 않음): 구간 1은 저장소 첫 화면에서 시작한다. 다른 구간은 앞 구간 끝 화면 그대로.
 if(n===1||n===6){if(!ctx.p.url().startsWith('https://github.com/uengine-oss/hyd-iot-edu'))await ctx.p.goto('https://github.com/uengine-oss/hyd-iot-edu',{waitUntil:'domcontentloaded'});
  await ctx.p.evaluate(()=>scrollTo(0,0));await ctx.sleep(1500);}
 await ctx.begin();
 for(const q of cues){
  const dur=JSON.parse(await fs.readFile(ctx.audio+'/'+q.id+'.json','utf8')).duration_ms;
  const ops=q.ops||[];
  const lead=300;
  const fn=ops.length?async()=>{const start=Date.now()-lead;   // 큐(음성) 시작 시각
   for(let i=0;i<ops.length;i++){const f=ops[i][2]??(i?0.8*i/ops.length:0);const due=start+Math.round(dur*f)-Date.now();if(due>0)await ctx.sleep(due);
    const [op,name]=ops[i];const t=target(name);
    if(op==='point')await c.point(t);else if(op==='scroll')await c.scrollTop(t);else throw Error('unknown op '+op);}}:null;
  // 첫 조작은 문장 시작 직후(또는 지정 시점), 이후 조작은 지정 시점에. 스크롤로 시작하는 큐는 첫 문장(「…내려가겠습니다」) 끝 무렵.
  if(ops[0]?.[0]==='scroll'&&ops[0][2]===undefined)ops[0]=[...ops[0].slice(0,2),Math.min(0.3,2600/dur)];
  await ctx.say(q.id,fn,{pointFrac:0.0,pointDelay:lead});
 }
 return {pos:c.pos(),scrollY:await ctx.p.evaluate(()=>scrollY)};
}
