// 길뚫기(녹화 없음): 상주 녹화 브라우저와 다른 새 브라우저에서 포털 지식 지도를 열어 화면 글 · 값 · 스크린샷을 남긴다.
// 사용: node scout.mjs <출력 폴더> <단계 JSON>  — 단계: [["tab","ontology"],["shot","이름"],["click",css,contains],["type",css,text],["select",css,label],["chip",title],["text",css],["eval",js]]
import fs from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require('/opt/node22/lib/node_modules/playwright');
const [out,stepsFile]=process.argv.slice(2);fs.mkdirSync(out,{recursive:true});
const steps=JSON.parse(fs.readFileSync(stepsFile,'utf8'));
const b=await chromium.launch({headless:true,args:['--force-device-scale-factor=1.5','--hide-scrollbars']});
const ctx=await b.newContext({viewport:{width:1280,height:720},deviceScaleFactor:1.5,locale:'ko-KR',timezoneId:'Asia/Seoul'});
const p=await ctx.newPage();
await p.goto('http://127.0.0.1:8088/',{waitUntil:'domcontentloaded'});await p.waitForTimeout(3000);
const log=[];
for(const s of steps){const [k,a,c]=s;
 try{
 if(k==='tab'){await p.click(`.rail nav button[data-tab="${a}"]`);await p.waitForTimeout(3500);}
 else if(k==='shot'){await p.screenshot({path:`${out}/${a}.png`});log.push(['shot',a]);}
 else if(k==='click'){const loc=c?p.locator(a,{hasText:c}):p.locator(a);const n=await loc.count();const vis=[];for(let i=0;i<n;i++)if(await loc.nth(i).isVisible())vis.push(i);
   const pick=vis.find(i=>true);log.push(['click',a,c,'matches',n,'visible',vis.length]);await loc.nth(pick).click();await p.waitForTimeout(1500);}
 else if(k==='type'){await p.fill(a,c);await p.waitForTimeout(2000);}
 else if(k==='select'){await p.selectOption(a,{label:c});await p.waitForTimeout(3500);}
 else if(k==='chip'){await p.locator('#ontoLayers .chiptoggle',{hasText:a}).locator('input').uncheck();await p.waitForTimeout(800);}
 else if(k==='text'){log.push(['text',a,await p.evaluate(s=>[...document.querySelectorAll(s)].filter(e=>e.checkVisibility()).map(e=>e.innerText.trim()).join('\n---\n'),a)]);}
 else if(k==='eval'){log.push(['eval',a.slice(0,60),await p.evaluate(a)]);}
 }catch(e){log.push(['ERROR',JSON.stringify(s),String(e).slice(0,300)]);}
}
fs.writeFileSync(out+'/log.json',JSON.stringify(log,null,1));
for(const l of log)console.log(JSON.stringify(l).slice(0,3000));
await b.close();
