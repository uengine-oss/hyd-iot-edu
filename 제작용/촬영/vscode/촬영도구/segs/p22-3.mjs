// 실전 2-2 구간 3(포털 HYD-02·03): 설비를 바꿔 같은 부품과 주 펌프 A의 설비 연결을 확인한다.
// 시작 상태: 구간 2 끝(지식 지도, 검색 「씰」, 상세 칸에 C트레이딩, 본문 맨 아래까지 내림).
import {vscode} from '../ui.mjs';
export default async ctx=>{
 const c=await vscode(ctx);
 // 굴릴 때 화살표를 옮기지 않는다(포털 CSS 화면 1024 — 예전 x 1240은 화면 밖, 2026-10-28 다시 녹화)
 const link=id=>`#ontoNode a[data-go="${id}"]`;
 const loaded=a=>ctx.waitFor(new Function(`return document.querySelector('#ontoAsset').value==='${a}'&&!!document.querySelector('#ontoMap .o-node[data-id="part:pump-seal"].match')`),20000);
 await ctx.begin();
 for(const [a,first,clickSeal,down,pump,asset] of [['HYD-02','p22-27','p22-28','p22-29','p22-29b','p22-30'],['HYD-03','p22-31','p22-32',null,'p22-32b','p22-33']].map(x=>[x[0],x[1],x[2],x[3],x[4],x[5]])){
  await ctx.say(first,async()=>{await c.scrollTo('main#content',0);await c.selectValue('#ontoAsset',a);});
  await loaded(a);
  await ctx.say(clickSeal,()=>c.clickSel('#ontoMap .o-node[data-id="part:pump-seal"]'));
  await ctx.waitFor(()=>/partNo/.test(document.querySelector('#ontoNode').innerText));
  if(down)await ctx.say(down,async()=>{await c.scrollTo('main#content',9999);await c.hoverSel('#ontoNode .kvt th','partNo');},{pointFrac:0.05});
  await ctx.say(pump,async()=>{if(!down)await c.scrollTo('main#content',9999);await c.clickSel(link('comp:pump-a'));});
  await ctx.waitFor(()=>/aliases/.test(document.querySelector('#ontoNode').innerText));
  await ctx.say(asset,()=>c.hoverSel(link('asset:'+a.toLowerCase())),{pointFrac:0.05});
 }
 return 'p22-3 done';
};
