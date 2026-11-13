// 클라우드(리눅스) 녹화의 브라우저 앞부분. ego의 전역 taskSpace(<이름>)와 같은 꼴을 Playwright로 만든다 — 조작 층(ctrl.mjs · ui.mjs · restore.mjs)은 그대로 쓴다.
// browser.mjs가 띄워 둔 헤드리스 Chromium(기본 문맥 하나, 페이지 하나)에 CDP로 붙는다. 구간 사이에도 같은 페이지 · 그림 · 저장소가 남는다(ego 작업 공간 역할).
// ego와 다른 것: p.cdp(메서드, 값)은 페이지 CDP 세션의 send, p.events()는 그 세션에서 받은 screencast 프레임 이벤트를 꺼내 준다(ego처럼 {method, params}).
// waitForFileChooser는 Playwright의 waitForEvent('filechooser')다. 나머지(evaluate · mouse · keyboard · waitFor* · url · goto · click · fill)는 Playwright 페이지 그대로다.
import {PROFILE,playwright} from './env.mjs';
export {PROFILE};
const {chromium}=playwright();
let browser=null;
export async function taskSpace(){
 browser??=await chromium.connectOverCDP(`http://127.0.0.1:${PROFILE.cdp}`);
 const page=browser.contexts()[0]?.pages()[0];if(!page)throw Error('browser.mjs page missing (run.sh up 먼저)');
 const cdp=await page.context().newCDPSession(page);const buf=[];
 cdp.on('Page.screencastFrame',params=>buf.push({method:'Page.screencastFrame',params}));
 const extra={cdp:(m,a)=>cdp.send(m,a),events:async()=>buf.splice(0),waitForFileChooser:o=>page.waitForEvent('filechooser',o),label:'p1',url:async()=>page.url()};
 const wrapped=new Proxy(page,{get:(t,k)=>k in extra?extra[k]:(typeof t[k]==='function'?t[k].bind(t):t[k])});
 const bcdp=await browser.newBrowserCDPSession();
 return {page:()=>wrapped,cdp:(m,a)=>bcdp.send(m,a),tabs:async()=>[{label:'p1',url:page.url(),page:wrapped}],adopt:async()=>wrapped};
}
export async function closeTaskSpace(){await browser?.close().catch(()=>{});browser=null;}
