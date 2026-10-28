// 통합 2-2 구간 3(포털): 유온 센서(센서, tag TS1) → 유온(상태 변수, 별칭 TS1 · 한계 65) → 설비 HYD-02로 바꿔 같은 쿨러 · 센서 노드 확인.
// 시작 상태: 구간 2 끝(HYD-01, 오일 쿨러 상세).
import {vscode} from '../ui.mjs';
import {portal} from './p31-common.mjs';
export default async ctx=>{
 const c=await vscode(ctx), p=portal(ctx,c);
 const link=t=>({sel:'#ontoNode a[data-go]',text:t});
 await ctx.begin();
 await ctx.say('i22-18',()=>p.click(link('유온 센서'),0.4),{at:'유온 센서를 누릅니다'});
 await ctx.waitFor(()=>/tag\s*TS1/.test(document.querySelector('#ontoNode').innerText));
 await ctx.say('i22-19',async()=>{await p.hover({sel:'#ontoNode h3'},0.25);await ctx.sleep(1200);await p.hover({sel:'#ontoNode .kvt th',text:'tag',exact:true});await ctx.sleep(1500);await p.hover({sel:'#ontoNode .kvt th',text:'virtual',exact:true});await ctx.sleep(2000);await p.hover({sel:'#ontoNode a[data-go="sv:ts1"]'});},{pointFrac:0.05});
 await ctx.say('i22-20',()=>p.click({sel:'#ontoNode a[data-go="sv:ts1"]'}));
 await ctx.waitFor(()=>/limit/.test(document.querySelector('#ontoNode').innerText));
 await ctx.say('i22-21',async()=>{await p.hover({sel:'#ontoNode h3'},0.25);await ctx.sleep(1200);await p.hover({sel:'#ontoNode .kvt th',text:'aliases',exact:true});await ctx.sleep(1500);await p.hover({sel:'#ontoNode .kvt th',text:'normal',exact:true});await ctx.sleep(1000);await p.hover({sel:'#ontoNode .kvt th',text:'limit',exact:true});},{pointFrac:0.05});
 await ctx.say('i22-22',()=>p.hover({sel:'#ontoNode .kvt th',text:'limit',exact:true}),{pointFrac:0.7});
 await ctx.say('i22-23',async()=>{await p.top();await c.selectValue('#ontoAsset','HYD-02');await ctx.waitFor(()=>document.querySelector('#ontoAsset').value==='HYD-02'&&document.querySelectorAll('#ontoMap .o-node').length>100,20000);await p.click({sel:'#ontoSearch'});await c.key('Control+a');await c.type('오일 쿨러');},{at:'HYD-02를 고릅니다'});
 await ctx.waitFor(()=>!!document.querySelector('#ontoMap .o-node[data-id="comp:cooler"].match'),20000);
 await ctx.say('i22-24',async()=>{await c.clickSel('#ontoMap .o-node[data-id="comp:cooler"]');await ctx.waitFor(()=>/HYD-02 유압 파워팩/.test(document.querySelector('#ontoNode').innerText));await p.hover({sel:'#ontoNode h3'},0.25);},{at:'오일 쿨러를 누르고'});
 await ctx.say('i22-25',async()=>{await p.hover(link('HYD-02 유압 파워팩'),0.45);await ctx.sleep(2500);await p.hover(link('유온 센서'));},{pointFrac:0.05});
 await ctx.say('i22-26',()=>p.hover(link('유온 센서'),0.45),{pointFrac:0.6});
 return 'i22-3 done';
};
