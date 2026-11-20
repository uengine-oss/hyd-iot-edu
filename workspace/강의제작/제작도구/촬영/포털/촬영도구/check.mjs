// 녹화 브라우저 점검(페이지 상태를 바꾸지 않는다). 지금 열린 페이지에서 ① screencast 프레임 한 장의 크기가 그 도구 config의 viewport × deviceScaleFactor인지 ② 화면 글자가 학생 Windows 크롬과 같은 글꼴로 그려졌는지 본다.
//   node check.mjs [--한글만] [--탭 <주소 조각>] [프레임을 저장할 .jpg]
//   HYD_BROWSER_CONFIG=<그 도구 촬영도구/config.json> node check.mjs …     다른 도구(neo4j)의 녹화 브라우저
// 글꼴은 CDP CSS.getPlatformFontsForNode가 답한 「실제로 글자를 그린 글꼴」이다(CSS에 적힌 이름이 아니다). 화면 안에 보이는 요소 가운데 글이 한글만 · 숫자만 · 영문만인 것을 종류마다 40개까지 재고,
// 고정폭으로 정한 칸(원문 · 코드)은 재지 않는다. 맞는 글꼴은 둘뿐이다: 그 페이지가 스스로 싣는 웹 글꼴(@font-face — 포털은 Pretendard Variable, 학생 PC에서도 같은 파일로 그린다)과,
// 웹 글꼴에 없는 글자를 Windows가 대신 그리는 Malgun Gothic. 그 밖의 글꼴(리눅스의 Inter · WenQuanYi · DejaVu 등)로 그려진 글자가 있으면 학생 화면과 다르다.
// 영문 · 숫자를 웹 글꼴 없이 시스템 글꼴 목록으로 그리는 화면은 --한글만을 주어 한글만 판정한다.
// 한글 표본이 하나도 없으면 판정할 수 없으므로 실패다(한글이 보이는 화면에서 다시 잰다). 어긋나면 그 글과 글꼴을 대며 종료 코드 1.
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import {ENV,playwright} from './env.mjs';
const HERE=fileURLToPath(new URL('.',import.meta.url));
const cfgPath=process.env.HYD_BROWSER_CONFIG||HERE+'config.json';
const CFG=JSON.parse(fs.readFileSync(cfgPath,'utf8'));
const args=process.argv.slice(2);let hangulOnly=false,frag=null,save=null;
for(let i=0;i<args.length;i++){if(args[i]==='--한글만')hangulOnly=true;else if(args[i]==='--탭')frag=args[++i];else save=args[i];}
const V=CFG.viewport,W=Math.round(V.width*V.deviceScaleFactor),H=Math.round(V.height*V.deviceScaleFactor);
function jpegSize(b){let i=2;while(i<b.length){if(b[i]!==255){i++;continue;}const m=b[i+1];i+=2;if(m===216||m===217)continue;const len=b.readUInt16BE(i);if([192,193,194].includes(m))return{width:b.readUInt16BE(i+5),height:b.readUInt16BE(i+3)};i+=len;}throw Error('JPEG 크기를 읽지 못함');}
const {chromium}=playwright();
const b=await chromium.connectOverCDP(`http://127.0.0.1:${CFG.cdp}`),ctx=b.contexts()[0];
const p=frag?ctx.pages().find(x=>decodeURIComponent(x.url()).includes(frag)):ctx.pages()[0];
if(!p)throw Error(`탭 없음: ${frag??'(첫 탭)'} — 열린 탭 ${ctx.pages().map(x=>x.url()).join(' | ')}`);
const s=await ctx.newCDPSession(p);
await s.send('Emulation.setDeviceMetricsOverride',{...V,mobile:false});
// 프레임: 1.5초 동안 받은 것 가운데 마지막 장(첫 장은 화면 값이 걸리기 전 크기일 수 있다). 멈춘 화면은 프레임이 오지 않으므로 화면에 남지 않는 변화로 한 장을 받는다.
const got=[];s.on('Page.screencastFrame',e=>{s.send('Page.screencastFrameAck',{sessionId:e.sessionId}).catch(()=>{});got.push(Buffer.from(e.data,'base64'));});
await s.send('Page.startScreencast',{format:'jpeg',quality:85,maxWidth:W,maxHeight:H,everyNthFrame:1});
for(let i=0;i<5;i++){await p.evaluate(()=>{const e=document.documentElement,o=e.style.opacity;e.style.opacity='0.999';requestAnimationFrame(()=>{e.style.opacity=o;});});await p.waitForTimeout(300);}
await s.send('Page.stopScreencast');
if(!got.length)throw Error('screencast 프레임이 오지 않음');
const frame=jpegSize(got.at(-1));if(save)fs.writeFileSync(save,got.at(-1));
const css=await p.evaluate(()=>({w:innerWidth,h:innerHeight,dpr:devicePixelRatio}));
// 글꼴 표본에 이름표를 달고(끝나면 뗀다) CDP로 요소마다 실제 글꼴을 묻는다.
const marked=await p.evaluate(()=>{
 const kind=t=>/^[가-힣]+$/.test(t)?'한글':/^[0-9]+$/.test(t)?'숫자':/^[A-Za-z]+$/.test(t)?'영문':null,n={한글:0,숫자:0,영문:0};
 for(const e of document.querySelectorAll('body *')){
  if(e.children.length||!e.checkVisibility({checkVisibilityCSS:true}))continue;
  const r=e.getBoundingClientRect();if(r.width<=0||r.height<=0||r.bottom<0||r.top>innerHeight||r.right<0||r.left>innerWidth)continue;
  const k=kind(e.textContent.replace(/\s/g,''));if(!k||n[k]>=40)continue;
  if(/mono|consolas|courier/i.test(getComputedStyle(e).fontFamily))continue;
  e.setAttribute('data-hyd-font',k);n[k]++;}
 return n;});
await s.send('DOM.enable');await s.send('CSS.enable');
const {root}=await s.send('DOM.getDocument',{depth:0});
const {nodeIds}=await s.send('DOM.querySelectorAll',{nodeId:root.nodeId,selector:'[data-hyd-font]'});
const web=await p.evaluate(()=>[...new Set([...document.fonts].filter(f=>f.status==='loaded').map(f=>f.family.replace(/["']/g,'')))]);
const okFont={has:f=>f==='Malgun Gothic'||web.some(w=>f===w||f.startsWith(w+' '))};   // CDP는 웹 글꼴 이름 뒤에 굵기 이름(Thin · Medium)을 붙여 답하기도 한다
const fonts={한글:{},숫자:{},영문:{}},bad=[];
for(const nodeId of nodeIds){
 const {attributes}=await s.send('DOM.getAttributes',{nodeId});const k=attributes[attributes.indexOf('data-hyd-font')+1];
 const {fonts:fs_}=await s.send('CSS.getPlatformFontsForNode',{nodeId});
 for(const f of fs_){fonts[k][f.familyName]=(fonts[k][f.familyName]||0)+f.glyphCount;
  if(!okFont.has(f.familyName)&&(k==='한글'||!hangulOnly)){const {outerHTML}=await s.send('DOM.getOuterHTML',{nodeId});bad.push({종류:k,글꼴:f.familyName,요소:outerHTML.replace(/\s+/g,' ').slice(0,120)});}}
}
await p.evaluate(()=>{for(const e of document.querySelectorAll('[data-hyd-font]'))e.removeAttribute('data-hyd-font');});
const fails=[];
if(frame.width!==W||frame.height!==H)fails.push(`프레임 ${frame.width}×${frame.height} ≠ ${W}×${H} (${cfgPath}의 viewport × deviceScaleFactor)`);
if(css.w!==V.width||css.h!==V.height)fails.push(`CSS 화면 ${css.w}×${css.h} ≠ ${V.width}×${V.height}`);
if(!marked.한글)fails.push('한글 표본 없음 — 한글이 보이는 화면에서 다시 잰다');
if(bad.length)fails.push(`웹 글꼴도 맑은 고딕도 아닌 글자 ${bad.length}곳`);
console.log(JSON.stringify({env:ENV,url:p.url(),frame,css,표본:marked,웹글꼴:web,글꼴:fonts,어긋남:bad.slice(0,10),판정:fails.length?'실패':'통과',까닭:fails,저장:save},null,1));
await s.detach().catch(()=>{});await b.close();process.exit(fails.length?1:0);
