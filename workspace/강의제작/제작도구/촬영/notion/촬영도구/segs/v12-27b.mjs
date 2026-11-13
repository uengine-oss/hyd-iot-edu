// v12-27b · 27단계 내보내기(뒤) — 시작: 내려받기 목록 탭이 앞(v12-27 끝). 준비(녹화 밖): 앞 구간 폴더의 학습노트_내보내기.zip을 이 구간 폴더 내보내기/에 풀고,
// 맨 위의 「내 학습 노트 ….html」을 뒤 탭(file://)에 열어 둔다. 끝: 내보낸 HTML에서 「Notion 익히기」를 눌러 연 쪽.
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:27,from:'새탭열기'}];
export async function prepare(c){
 const path=await import('node:path');const {unzip}=await import('../lib/unzip.mjs');
 if(!c.ctx.prevOut)throw Error('v12-27b needs the previous take (v12-27) for the zip');
 const zip=c.ctx.prevOut+'/학습노트_내보내기.zip';await c.fs.stat(zip).catch(()=>{throw Error('Export zip missing: '+zip);});
 const dir=path.resolve(c.out+'/내보내기');const files=await unzip(zip,dir);
 const top=files.filter(f=>path.dirname(f)===dir&&f.toLowerCase().endsWith('.html')&&path.basename(f).startsWith(c.ctx.homeTitle));
 if(top.length!==1)throw Error('Exported home html at the top level: '+top.length+' of '+files.length+' files');
 c.state.exportHtml=top[0];await c.openTab('export','file:///'+encodeURI(top[0].replace(/\\/g,'/')));
}
export const ops=c=>{const {at}=kit(c);return{27:{
 새탭열기:at(0,async()=>{c.at(1);await c.gate();await c.front('export');}),
 카드누르기:async()=>{const g=await c.forPage('export');const sel=await g.mark({css:'a',has:'Notion 익히기',first:true});await g.inView(sel);
  const q=await g.serial(()=>g.raw.evaluate(s=>{const r=document.querySelector(s).getBoundingClientRect();return{x:r.x+Math.min(45,r.width/2),y:r.y+r.height/2};},sel));const before=await g.serial(()=>g.raw.url());
  await g.click('css',sel);await g.serial(()=>g.raw.waitForFunction(u=>location.href!==u&&document.readyState==='complete',before,{timeout:10000}));
  if(!decodeURIComponent(await g.serial(()=>g.raw.url())).includes('Notion 익히기'))throw Error('Export link did not open the Notion 익히기 page');
  await g.place(q);await c.ctx.restartCapture();},
}};};
