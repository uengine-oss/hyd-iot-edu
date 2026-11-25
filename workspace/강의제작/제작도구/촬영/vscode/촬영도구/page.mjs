// 녹화 브라우저 연결 한 곳. 녹화 · 리허설(ctrl.mjs) · 되돌리기(segs/lab-common.mjs resetLab) · 화면 준비(prep.mjs) · 자가시험(draw_check.mjs)이 모두 여기서 페이지를 받는다.
// 녹화 브라우저는 포털 촬영도구 browser.mjs를 이 폴더 config.json(cdp · viewport · profile · locale)으로 띄운 헤드리스 Chromium이고(run.sh up),
// 여기서는 CDP로 붙었다 떨어지기만 하므로 구간 사이에 같은 페이지 · 열린 폴더 · 터미널 · Codex 대화가 그대로 남는다.
// 받는 것은 Playwright Page에 아래 넷을 더한 것이다.
//   p.cdp(명령, 인자)   그 페이지의 CDP 세션으로 보낸다(화면 값 · screencast · ACK)
//   p.events()          그동안 온 Page.screencastFrame 이벤트를 꺼낸다
//   p.text()            화면 글 전체 — 바깥 문서와 그 안 모든 프레임(Codex 채팅은 웹뷰 iframe 안의 iframe이다)의 보이는 글 · 입력칸 안내 글 · aria-label
//   p.clickText(글)     글이 정확히 같은 보이는 요소 하나를 프레임을 따라 들어가 누른다(Codex 웹뷰 안의 단추). 없거나 여럿이면 멈춘다
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const HERE=fileURLToPath(new URL('.',import.meta.url)).replace(/\\/g,'/');
export const CFG=JSON.parse(await fs.readFile(HERE+'config.json','utf8'));
export const WORK=path.resolve(HERE,CFG.work).replace(/\\/g,'/');
export const VIEW=CFG.viewport;
// 웹 VS Code를 열거나 새로 고칠 때의 기다림: 문서가 읽힌 데까지만 기다리고(그 뒤는 부르는 쪽이 .monaco-workbench를 기다린다) — 기본값(load)은 창을 새로 고칠 때 1분 가까이 돌아오지 않았다.
export const NAV={timeout:60000,waitUntil:'domcontentloaded'};

// 떠나는 중인 프레임(웹뷰가 다시 그려지는 순간)만 건너뛴다. 그 밖의 오류는 그대로 올린다.
const gone=e=>/detached|destroyed|closed|navigat/i.test(String(e?.message??e));
const readText=()=>{
 let body=document.body?.innerText??'';
 for(const e of document.querySelectorAll('script,style'))if(e.textContent)body=body.replace(e.textContent,'');   // 확장 호스트 프레임은 스크립트 글이 본문 글로 읽힌다
 const out=[body];
 for(const e of document.querySelectorAll('[placeholder],[data-placeholder],[aria-label],[aria-placeholder]'))
  for(const k of ['placeholder','data-placeholder','aria-label','aria-placeholder']){const v=e.getAttribute(k);if(v&&e.getClientRects().length)out.push(v);}
 return out.join('\n');
};

export async function wrap(page){
 if(page.cdp)return page;
 const s=await page.context().newCDPSession(page),got=[];
 s.on('Page.screencastFrame',params=>got.push({method:'Page.screencastFrame',params}));
 page.cdp=(m,a)=>s.send(m,a);
 page.events=async()=>got.splice(0);
 page.text=async()=>{const out=[];for(const f of page.frames()){try{out.push(await f.evaluate(readText));}catch(e){if(!gone(e))throw e;}}return out.join('\n');};
 page.clickText=async text=>{
  const hits=[];
  for(const f of page.frames()){try{const l=f.getByText(text,{exact:true});const n=await l.count();for(let i=0;i<n;i++)if(await l.nth(i).isVisible())hits.push(l.nth(i));}catch(e){if(!gone(e))throw e;}}
  if(hits.length!==1)throw Error(`화면 글 「${text}」인 보이는 요소가 ${hits.length}개 (촬영도구/page.mjs clickText)`);
  await hits[0].click({timeout:5000});
 };
 page.detach=()=>s.detach();
 return page;
}

// n = 녹화 브라우저의 몇 번째 페이지인가(0 = 웹 VS Code, 1 = 랩 결과 화면). 바로 다음 번호까지만 새로 연다.
export async function openPage(n=0){
 const {playwright}=await import(new URL('../../포털/촬영도구/env.mjs',import.meta.url).href);
 const browser=await playwright().chromium.connectOverCDP(`http://127.0.0.1:${CFG.cdp}`).catch(e=>{throw Error(`녹화 브라우저(CDP ${CFG.cdp})에 붙지 못함 — ./run.sh up으로 먼저 띄운다 (촬영도구/page.mjs): ${String(e.message).split('\n')[0]}`);});
 const ctx=browser.contexts()[0];if(!ctx)throw Error('녹화 브라우저에 문맥이 없음 — ./run.sh down 뒤 up (촬영도구/page.mjs)');
 const pages=ctx.pages();
 if(!Number.isInteger(n)||n<0||n>pages.length)throw Error(`녹화 브라우저의 페이지는 ${pages.length}개 — ${n}번 페이지를 열 수 없음(0부터, 바로 다음 번호까지만 새로 연다) (촬영도구/page.mjs)`);
 const p=await wrap(pages[n]??await ctx.newPage());
 return {p,close:async()=>{await p.detach();await browser.close();}};
}

// 웹 VS Code에서 그 폴더를 여는 주소. 접속 토큰은 config.json의 token_file에서 읽고, 값을 로그 · 화면에 남기지 않는다.
export async function folderUrl(dir){
 const f=path.resolve(HERE,CFG.token_file);
 const tkn=(await fs.readFile(f,'utf8').catch(()=>{throw Error('접속 토큰 파일 없음: '+f+' — 촬영준비 길 1의 --connection-token-file과 같은 파일을 config.json token_file에 둔다 (촬영도구/page.mjs)');})).trim();
 return CFG.server+'?tkn='+tkn+'&folder='+encodeURIComponent('/'+dir);
}
