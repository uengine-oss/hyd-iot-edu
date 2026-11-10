// 통합 2회차 06편 구간 01: 열린 README·탐색기·Codex를 짚는다. 요청·파일 변경 없음.
// 시작: 2304×1296 metrics, 브라우저 125%, README 맨 위, 탐색기 폴더 접힘, 빈 Codex 새 대화.
import {vscode} from '../ui.mjs';

export default async ctx=>{
 const c=await vscode(ctx);
 const layout=await c.serial(()=>ctx.p.evaluate(()=>({
  width:innerWidth,height:innerHeight,dpr:devicePixelRatio,
  title:document.querySelector('.tabs-container .tab.active .label-name')?.textContent,
  root:document.querySelector('.pane-header[aria-label^="Explorer Section:"]')?.innerText,
  first:[...document.querySelectorAll('.editor-instance .view-lines .view-line')].some(e=>e.textContent.includes('#')&&e.textContent.includes('현장'))
 })));
 if(layout.title!=='README.md'||!layout.first||Math.abs(layout.dpr-1.25)>0.01||layout.width!==1843||layout.height!==1037)throw Error('첫 화면 조건 불일치: '+JSON.stringify(layout));
 if(layout.root?.toLowerCase()!=='ontology-lab')throw Error('다른 실습 폴더가 열려 있습니다.');
 const snap=await c.serial(()=>ctx.p.snapshot());
 if(!snap.includes('Ask Codex anything.')||!snap.includes('6-Luna')||!snap.includes('Medium')||snap.includes('연결 확인입니다.')||snap.includes('Restricted Mode')||snap.includes('Unable to send message'))throw Error('빈 Codex 새 대화·모델·폴더 신뢰를 먼저 확인합니다.');
 const measure=async spec=>c.serial(()=>ctx.p.evaluate(spec=>{
  let e;
  if(spec.line)e=[...document.querySelectorAll('.editor-instance .view-lines .view-line')].find(x=>x.textContent.replace(/\u00a0/g,' ').startsWith(spec.line));
  else e=[...document.querySelectorAll(spec.selector)].find(x=>(spec.text==null||(x.textContent||'').trim()===spec.text)&&x.getBoundingClientRect().width>0);
  if(!e)throw Error('화면 대상 없음: '+JSON.stringify(spec));
  const r=e.getBoundingClientRect();
  return{x:spec.line?r.x-24:spec.left?r.x-24:r.x+r.width*(spec.fx??0.5),y:r.y+r.height*(spec.fy??0.5),width:innerWidth,height:innerHeight};
 },spec));
 const point=async(name,spec)=>{
  let a=await measure(spec),b;
  for(let n=0;n<10;n++){
   await ctx.sleep(150);b=await measure(spec);
   if(Math.abs(a.x-b.x)<0.5&&Math.abs(a.y-b.y)<0.5)break;
   if(n===9)throw Error('위치가 안정되지 않음: '+name);a=b;
  }
  if(b.x<0||b.y<0||b.x>=b.width||b.y>=b.height)throw Error('화면 밖 대상: '+name);
  await c.move(b.x,b.y);
  ctx.report?.push({cue:ctx.cueId,op:'point',target:name,x:b.x,y:b.y,fail:false});
 };
 const line=(name,text)=>point(name,{line:text});
 const folder=name=>point(name,{selector:'.explorer-folders-view .monaco-list-row .label-name',text:name,left:true});
 const root=()=>point('실습 폴더 이름',{selector:'.pane-header[aria-label^="Explorer Section:"]',fx:0.025});
 const sayOptions={pointFrac:0,pointDelay:0};
 // 한 설명 안에서 대상을 바꿀 때 둘째 구절 직전에 이동한다. dry는 위치만 확인한다.
 // 실제 음성 싱크는 구매 뒤 첫 큐의 프레임·발화 시각으로 판정한다.
 const twoPoints=async(id,first,second,phrase)=>{
  let offset=0;
  if(!ctx.rehearsal){
   const cue=JSON.parse(await ctx.fs.readFile(ctx.audio+'/'+id+'.json','utf8'));
   const at=cue.text.indexOf(phrase);if(at<0)throw Error(id+': 이동 구절 없음');
   offset=Math.max(0,cue.duration_ms*at/cue.text.length-600);
  }
  await ctx.say(id,async()=>{const start=Date.now();await first();const wait=offset-(Date.now()-start);if(wait>0)await ctx.sleep(wait);await second();},sayOptions);
 };
 await c.installPointer({x:365,y:92});
 await ctx.begin();
 await ctx.say('i206-0101',()=>line('제목','# 현장'),{pointFrac:0,pointDelay:0});
 await ctx.say('i206-0102',()=>line('직접 정할 판단','포털 지식 지도에서'),{pointFrac:0,pointDelay:0});
 await ctx.say('i206-0103',root,sayOptions);
 await ctx.say('i206-0104',()=>point('웹 메뉴',{selector:'[role="menubar"]',fx:0.5}),{pointFrac:0,pointDelay:0});
 await ctx.say('i206-0105',root,sayOptions);
 await ctx.say('i206-0106',()=>point('열린 README 편집기',{selector:'.tabs-container .tab.active .label-name',left:true}),sayOptions);
 await ctx.say('i206-0110',()=>point('Codex 새 대화',{selector:'.part.auxiliarybar',fx:0.5,fy:0.45}),{pointFrac:0,pointDelay:0});
 await twoPoints('i206-0111',()=>point('Codex 입력칸',{selector:'.part.auxiliarybar',fx:0.04,fy:0.86}),()=>line('사람이 확인할 목적','포털 지식 지도에서'),'어떤 답이 필요한지');
 await ctx.say('i206-0113',()=>folder('AGENTS.md'),sayOptions);
 await twoPoints('i206-0112',()=>folder('data'),()=>folder('app'),'앱 폴더에는');
 return{segment:'i206-01',view:layout,next:'가이드 1단계: data 확인과 python run.py 첫 실행',aiRequests:0};
};
