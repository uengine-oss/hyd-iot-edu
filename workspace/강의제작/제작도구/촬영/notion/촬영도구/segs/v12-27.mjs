// v12-27 · 27단계 내보내기(앞) — 시작: 홈. 준비에서 chrome://downloads를 뒤 탭에 연다. 「작업」 → 「더 보기」 → 「내보내기」 → 형식 HTML · 현재 보기 · 모든 콘텐츠 · 하위 페이지 포함 켬 →
// 내보내기(zip을 이 구간 폴더에 학습노트_내보내기.zip으로 저장) → 내려받기 목록 탭. 끝: 내려받기 목록이 앞(「압축 파일이 하나 있죠」 쉼에서 구간을 끊는다 — 다음 구간 준비가 녹화 밖에서 푼다).
// 대본이 말하는 처음 상태(형식이 HTML이 아님 · 현재 보기 · 모든 콘텐츠 · 하위 페이지 포함 꺼짐)와 다르면 녹화에서는 멈추고, 리허설에서는 script-gap.jsonl에 적고 그 조작을 건너뛴다.
import {kit,BLUE,GRAY} from '../lib/ui-v12.mjs';
export const parts=[{step:27,until:'새탭열기'}];
export async function prepare(c){await c.openTab('downloads','chrome://downloads/');}
export const ops=c=>{const {at}=kit(c);
 const control=async(label,want)=>{const sel=await c.labelSel(label);const t=await c.serial(()=>c.raw.evaluate(s=>document.querySelector(s).textContent.trim(),sel));if(!t.includes(want))await c.scriptGap('내보내기 「'+label+'」 칸이 「'+t+'」 — 대본은 「'+want+'」');return sel;};
 return{27:{
 작업:()=>c.click('aria','작업'),
 내보내기:at(0,async()=>{c.at(0.2);await c.click('menu','더 보기');c.at(1);await c.click('menu','내보내기');}),
 형식HTML:at(0,async()=>{const fmt=await c.serial(()=>c.raw.evaluate(()=>[...document.querySelectorAll('[role=dialog] [role=button]')].map(e=>e.textContent.trim()).find(x=>['HTML','Markdown & CSV','PDF'].includes(x))));
  if(!fmt)throw Error('Export format button missing');if(fmt==='HTML'){await c.scriptGap('내보내기 형식이 이미 HTML(Notion이 앞서 고른 형식을 기억함) — 대본은 「처음에 다른 형식으로 골라져 있어요」');return;}
  c.at(0.75);await c.click('text',fmt);c.at(1);await c.click('menu','HTML');}),
 보기칸짚기:async()=>c.hoverAt(await control('데이터베이스 보기','현재 보기')),
 콘텐츠칸짚기:async()=>c.hoverAt(await control('페이지 콘텐츠','모든 콘텐츠')),
 하위포함:async()=>{const t='s'+Math.random().toString(36).slice(2,10);
  const v=await c.serial(()=>c.raw.evaluate(t=>{for(const e of [...document.querySelectorAll('[role=switch],[role=checkbox],input[type=checkbox]')].filter(e=>e.checkVisibility({checkVisibilityCSS:true}))){let p=e;for(let i=0;i<4&&p;i++,p=p.parentElement){const x=p.textContent.trim();if(x.includes('하위 페이지 포함')&&!x.includes('하위 페이지용 폴더')){e.setAttribute('data-v12',t);return e.getAttribute('aria-checked')??(e.tagName==='INPUT'?String(e.checked):null)??e.getAttribute('data-state');}}}throw Error('Subpage option not identified');},t));
  if(v==='true'||v==='checked'){await c.scriptGap('「하위 페이지 포함」이 이미 켜져 있음 — 대본은 「꼭 켜 주세요」');return;}if(v!=='false'&&v!=='unchecked')throw Error('Subpage option state unknown: '+v);
  await c.click('css','[data-v12="'+t+'"]');},
 // 말 없는 시간을 줄이려고 쪽 열기 · 긴 스크롤 · 내려받기를 말 도중에 시작한다(녹화 전 훑기 2026-11-13: 이 큐들은 누른 뒤 기다림이 2.5초를 넘을 후보). 내보내기는 Notion이 파일을 만드는 데 3초쯤 걸려 「누르시면」의 끝(0.75)에 누른다.
 내보내기누르기:{pointFrac:0,fn:async()=>{c.at(0.75);if((await c.serial(()=>c.raw.url())).includes(c.ctx.protect))throw Error('Original workspace export forbidden');
  // waitForEvent('download')로 받으면 ego가 GUID 이름으로 받아 내려받기 목록에 GUID가 찍힌다(리허설 r29). 브라우저 내려받기를 이 구간 폴더로 돌려
  // Notion이 준 이름 그대로 받고, 다 받은 zip을 학습노트_내보내기.zip으로 복사한 뒤(다음 구간이 푼다) 내려받기 설정을 기본값으로 되돌린다.
  const path=await import('node:path');const dir=path.resolve(c.out);const before=new Set(await c.fs.readdir(dir));
  await c.serial(()=>c.raw.cdp('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:dir}));
  try{const sel=await c.mark({css:'[role=dialog] [role=button]',text:'내보내기',last:true});await c.click('css',sel);
   let got=null;for(const t0=Date.now();!got;await c.sleep(500)){if(Date.now()-t0>120000)throw Error('Export zip did not arrive in '+dir);
    const fresh=(await c.fs.readdir(dir)).filter(n=>!before.has(n));if(fresh.some(n=>n.endsWith('.crdownload')))continue;got=fresh.find(n=>n.toLowerCase().endsWith('.zip'));}
   const f=dir+'/학습노트_내보내기.zip';await c.fs.copyFile(dir+'/'+got,f);c.state.zip=f;c.state.zipName=got;}
  finally{await c.serial(()=>c.raw.cdp('Browser.setDownloadBehavior',{behavior:'default'}));}}},
 // 내려받기 목록(chrome://downloads)의 첫 항목이 방금 받은 zip인지 보고 짚는다. 목록은 그림자 DOM 안에 있다.
 내려받기목록:at('point',async()=>{const g=await c.front('downloads');
  const q=await g.serial(()=>g.raw.evaluate(()=>{const all=[];const walk=r=>{for(const e of r.querySelectorAll('*')){if(e.tagName==='DOWNLOADS-ITEM')all.push(e);if(e.shadowRoot)walk(e.shadowRoot);}};walk(document);
   const it=all[0];if(!it)throw Error('No item in chrome://downloads');const n=it.shadowRoot?.querySelector('#file-link,#name')||it;const r=n.getBoundingClientRect();return{x:r.x+Math.min(60,r.width/2),y:r.y+r.height/2,name:n.textContent.trim()};}));
  if(q.name!==c.state.zipName)throw Error('First download is not the export zip: '+q.name+' (expected '+c.state.zipName+')');await g.move(q.x,q.y);}),
}};};
