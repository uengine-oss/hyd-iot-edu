// v12 녹화 전 대조. 녹화 없이 node로도 돈다:  node preflight12.mjs [--음성]   (run.sh chain12와 ctrl.chain이 녹화 전에 같은 것을 돌린다)
// ① segs/v12-*.mjs의 parts가 큐 파일(source-cues-v12.json)의 큐를 빠짐없이 한 번씩 덮는지 — 구간 차례는 큐 파일의 단계 차례를 따른다
//    (대본에서 단계 차례를 바꾸면 큐 파일을 다시 만들기만 하면 구간 차례가 따라간다. 한 구간 안의 parts는 큐 파일에서 이어져 있어야 한다)
// ② 모듈마다 손잡이 이름이 그 단계 큐의 조작 이름(op)과 같은지(없는 손잡이 · 남는 손잡이) ③ 단계를 가르는 구간 경계가 쉼 자리(‖)인지
// ④ config.json v12 칸 ⑤ --음성이면 큐마다 음성 캐시(<id>.json)가 있고 글이 큐 파일과 같은지. 어긋나면 모듈 · 단계 · 큐 id를 대고 멈춘다.
const fs=await import('node:fs/promises');
const HERE=decodeURIComponent(new URL('.',import.meta.url).pathname).replace(/^\/([A-Za-z]:)/,'$1');
const abs=r=>decodeURIComponent(new URL(r,'file:///'+HERE).pathname.replace(/^\/([A-Za-z]:)/,'$1').replace(/\/$/,''));

// 시작 검사(ctrl.chain이 녹화 · 리허설 시작에 부른다): Notion은 ego 확대 100%로 찍는다(사용자 2026-11-12 「100프로로 해도될듯」).
// 확대 100%면 화면 지정(config.json viewport, 1536×864 · 배율 1) 그대로 innerWidth = 지정 폭, devicePixelRatio = 1이고,
// Windows 표시 배율 125%라 프레임은 1920×1080이다. 확대 150%면 innerWidth가 1024가 된다. 다르면 무엇이 어긋났는지 대고 멈춘다.
export const EXPECT_ZOOM=1;
export function liveCheck({metrics,frame,viewport}){
 const want={iw:Math.round(viewport.width/EXPECT_ZOOM),ih:Math.round(viewport.height/EXPECT_ZOOM),dpr:1,frame:'1920x1080'};
 const got={iw:metrics.iw,ih:metrics.ih,dpr:Math.round(metrics.dpr*100)/100,frame:frame.width+'x'+frame.height};
 const bad=Object.keys(want).filter(k=>want[k]!==got[k]);
 if(bad.length)throw Error('ego 화면 확대가 기대(' +EXPECT_ZOOM*100+'%)와 다름 — 기대 '+JSON.stringify(want)+' / 실제 '+JSON.stringify(got)+' (preflight12.mjs liveCheck, config.json viewport). ego 설정은 사용자가 맞춘다');
 return got;
}

// 녹화 시작 검사: 리허설이 남긴 쪽(「…리허설」, 제목 없는 「새 페이지」)이 왼쪽 목록에 있으면 그 이름이 녹화에 찍히므로 멈춘다(녹화 모드에서만 — 리허설 중에는 r15 쪽이 있어야 한다).
// 페이지 안에서 돈다: 사이드바의 목록 항목(role=treeitem) 이름을 읽는다. 사이드바가 닫혀 있어도 DOM에 있는 항목은 읽는다.
export function sidebarLeftovers(){
 const items=[...document.querySelectorAll('[role=treeitem]')].filter(e=>e.closest('.notion-sidebar-container,nav,[aria-label="사이드바"]'));
 if(!items.length)throw Error('Sidebar page list not found (preflight12.mjs sidebarLeftovers)');
 return [...new Set(items.map(e=>(e.querySelector('[role=button],a')?.textContent||e.textContent).trim()).filter(t=>/리허설/.test(t)||t==='새 페이지'))];
}

export async function preflight({audio=false}={}){
 const CFG=JSON.parse(await fs.readFile(HERE+'config.json','utf8'));
 const {partCues,EMOJI_KEYS}=await import('file:///'+HERE+'lib/ui-v12.mjs');
 const file=JSON.parse(await fs.readFile(HERE+'source-cues-v12.json','utf8').catch(()=>{throw Error('source-cues-v12.json 없음: PYTHONUTF8=1 python build_cues_v12.py');}));
 const cues=file.cues,pos=new Map(cues.map((c,i)=>[c.id,i]));
 const names=(await fs.readdir(HERE+'segs')).filter(f=>/^v12-[0-9a-z]+\.mjs$/.test(f));
 if(!names.length)throw Error('segs/v12-*.mjs 없음');
 const errs=[],segments=[];
 for(const f of names){
  const id=f.slice(0,-4);let mod;
  try{mod=await import('file:///'+HERE+'segs/'+f);}catch(e){errs.push(f+': 불러오지 못함 '+e.message);continue;}
  if(!Array.isArray(mod.parts)||!mod.parts.length){errs.push(f+': parts 없음');continue;}
  if(typeof mod.ops!=='function'){errs.push(f+': ops(c) 없음');continue;}
  const H=mod.ops(null),need={},ids=[];
  for(const part of mod.parts){let xs;try{xs=partCues(cues,part);}catch(e){errs.push(f+': '+e.message);continue;}
   ids.push(...xs.map(c=>c.id));for(const c of xs)if(c.op)(need[part.step]??=new Set()).add(c.op);
   const before=cues[pos.get(xs[0].id)-1],last=xs.at(-1);
   if(part.from&&before?.end==='잇기')errs.push(`${f} 단계 ${part.step}: 구간이 ${xs[0].id} 앞(▸ 바로 뒤)에서 시작 — 구간 경계는 쉼 자리(‖)여야 한다`);
   if(part.until&&last.end==='잇기')errs.push(`${f} 단계 ${part.step}: 구간이 ${last.id}(▸로 끝남)에서 끝남 — 구간 경계는 쉼 자리(‖)여야 한다`);}
  for(const st of new Set([...Object.keys(need).map(Number),...Object.keys(H).map(Number)])){
   const want=need[st]||new Set(),have=Object.keys(H[st]||{});
   const missing=[...want].filter(x=>!have.includes(x)),extra=have.filter(x=>!want.has(x));
   if(missing.length||extra.length)errs.push(`${f} 단계 ${st}: 손잡이 없음 [${missing.join(', ')}] · 큐에 없는 손잡이 [${extra.join(', ')}] (큐 파일의 op 이름은 build_cues_v12.py OPS)`);}
  for(let i=1;i<ids.length;i++)if(pos.get(ids[i])!==pos.get(ids[i-1])+1)errs.push(`${f}: parts가 큐 파일에서 이어져 있지 않음(${ids[i-1]} 다음이 ${ids[i]})`);
  if(ids.length)segments.push({id,file:f,mod,ids,steps:[...new Set(mod.parts.map(p=>p.step))],first:pos.get(ids[0])});
 }
 segments.sort((a,b)=>a.first-b.first);
 const seen=segments.flatMap(s=>s.ids);
 const dup=seen.filter((x,i)=>seen.indexOf(x)!==i);if(dup.length)errs.push('두 구간이 같은 큐를 덮음: '+[...new Set(dup)].slice(0,10).join(' '));
 const miss=cues.filter(c=>!seen.includes(c.id)).map(c=>c.id);if(miss.length)errs.push('어느 구간도 덮지 않은 큐: '+miss.slice(0,20).join(' ')+(miss.length>20?' …(+'+(miss.length-20)+')':''));
 const v=CFG.v12||{};
 for(const k of ['home','download','cover','guide'])if(!v[k])errs.push(`config.json v12.${k} 비어 있음`);
 for(const k of EMOJI_KEYS)if(!v.emoji?.[k])errs.push(`config.json v12.emoji["${k}"] 비어 있음`);
 if(v.guide&&!(await fs.stat(abs(v.guide)).then(()=>true).catch(()=>false)))errs.push('config.json v12.guide 파일 없음: '+abs(v.guide));
 if(audio){const AUDIO=abs(CFG.audio_play),bad=[];
  for(const c of cues){const j=await fs.readFile(AUDIO+'/'+c.id+'.json','utf8').then(JSON.parse).catch(()=>null);if(!j)bad.push(c.id+'(없음)');else if(j.text!==c.text)bad.push(c.id+'(글 다름)');}
  if(bad.length)errs.push(`음성 캐시가 큐 파일과 다른 큐 ${bad.length}개: ${bad.slice(0,12).join(' ')}${bad.length>12?' …':''} — PYTHONUTF8=1 python voice.py source-cues-v12.json(유료, 견적 · 승인 뒤) → PYTHONUTF8=1 python 음성쉼.py`);}
 if(errs.length)throw Error('preflight12 — '+errs.length+'건\n'+errs.join('\n'));
 return {cues,segments,text:new Map(cues.map(c=>[c.id,c.text]))};
}

if(typeof process!=='undefined'&&process.argv?.[1]?.replace(/\\/g,'/').endsWith('/preflight12.mjs')){
 try{const r=await preflight({audio:process.argv.includes('--음성')});
  console.log(JSON.stringify({ok:true,cues:r.cues.length,segments:r.segments.map(s=>`${s.id}:${s.steps.join('+')}(${s.ids.length}큐)`)}));}
 catch(e){console.error(e.message);process.exit(1);}
}
