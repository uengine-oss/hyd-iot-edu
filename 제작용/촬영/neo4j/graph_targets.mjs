export function installGraphObserver(){
 if(window.__forestRead?.version===3)return;
 window.__forestRead={version:3,texts:[],circles:[],targets:new Map()};
 for(const name of ['fillText','arc']){const orig=CanvasRenderingContext2D.prototype[name];CanvasRenderingContext2D.prototype[name]=function(...args){
  if(this.canvas.matches?.('[data-testid="nvl-c2d-canvas"]')){const m=this.getTransform(),r=this.canvas.getBoundingClientRect(),x=name==='fillText'?args[1]:args[0],y=name==='fillText'?args[2]:args[1];const item={text:name==='fillText'?args[0]:null,wx:x,wy:y,x:r.x+(m.a*x+m.c*y+m.e)*r.width/this.canvas.width,y:r.y+(m.b*x+m.d*y+m.f)*r.height/this.canvas.height,r:name==='arc'?args[2]*Math.abs(m.a)*r.width/this.canvas.width:null,t:Date.now(),canvas:this.canvas};const a=window.__forestRead[name==='fillText'?'texts':'circles'];a.push(item);if(a.length>5000)a.splice(0,2000);if(name==='fillText'){
 const q=window.__forestRead,cs=q.circles.filter(c=>c.canvas===this.canvas&&c.wx!==undefined&&Math.abs(c.t-item.t)<35&&c.r>5);
 const c=cs.sort((a,b)=>Math.hypot(a.x-item.x,a.y-item.y)-Math.hypot(b.x-item.x,b.y-item.y))[0];
 if(c&&Math.hypot(c.x-item.x,c.y-item.y)<c.r*1.4){const map=q.targets.get(this.canvas)||new Map();map.set(item.text,{wx:c.wx,wy:c.wy,t:item.t});q.targets.set(this.canvas,map);}
 }}
  return orig.apply(this,args);
 };}
}
export function graphTarget({label,edge=false,allowOutside=false}){
 const canvas=Array.from(document.querySelectorAll('[data-testid="nvl-c2d-canvas"]')).find(c=>c.getBoundingClientRect().height>0),q=window.__forestRead;if(!canvas||!q)throw Error('Graph not visible');
 // 라벨은 저배율에서 생략될 수 있다. 실제로 그려졌을 때의 원 좌표를 보존해 최신 그리기 좌표로 추적한다.
 if(!edge){
  const remembered=q.targets.get(canvas)||new Map();q.targets.set(canvas,remembered);
  for(const t of new Map(q.texts.filter(x=>x.canvas===canvas).map(t=>[t.text,t])).values()){
   const candidates=q.circles.filter(c=>c.canvas===canvas&&c.wx!==undefined&&Math.abs(c.t-t.t)<35&&c.r>5);
   const c=candidates.sort((a,b)=>Math.hypot(a.x-t.x,a.y-t.y)-Math.hypot(b.x-t.x,b.y-t.y))[0];
   if(c&&Math.hypot(c.x-t.x,c.y-t.y)<c.r*1.4)remembered.set(t.text,{wx:c.wx,wy:c.wy,t:t.t});
  }
  const groups=new Map();for(const [text,c]of remembered){const k=c.wx.toFixed(2)+','+c.wy.toFixed(2);const a=groups.get(k)||{...c,texts:[]};a.texts.push(text);a.t=Math.max(a.t,c.t);groups.set(k,a);}
  const matches=[...groups.values()].filter(g=>g.texts.join('').replace(/\s/g,'').includes(label.replace(/\s/g,''))).sort((a,b)=>Number(b.texts.some(t=>t.replace(/\s/g,'')===label.replace(/\s/g,'')))-Number(a.texts.some(t=>t.replace(/\s/g,'')===label.replace(/\s/g,'')))||b.t-a.t);
  for(const match of matches){const c=q.circles.filter(c=>c.canvas===canvas&&Math.abs(c.wx-match.wx)<.01&&Math.abs(c.wy-match.wy)<.01).at(-1);if(c){const r=canvas.getBoundingClientRect();if(allowOutside||(c.x>=r.left&&c.x<=r.right&&c.y>=r.top&&c.y<=r.bottom))return {x:c.x,y:c.y,r:c.r};}}
 }
 const latest=q.texts.filter(x=>x.canvas===canvas).at(-1)?.t||0;
 let t=q.texts.filter(x=>x.canvas===canvas&&x.text===label).at(-1);
 if(!t&&!edge){
  const all=q.texts.filter(x=>x.canvas===canvas),latest=all.at(-1)?.t||0;
  const circles=q.circles.filter(x=>x.canvas===canvas&&x.r>5&&x.t>=latest-50&&x.wx!==undefined);
  for(const c of circles){const parts=all.filter(x=>x.t>=latest-50&&Math.hypot(x.x-c.x,x.y-c.y)<c.r*1.4).sort((a,b)=>a.y-b.y||a.x-b.x);const joined=[...new Set(parts.map(x=>x.text))].join('').replace(/\s/g,'');if(joined.includes(label.replace(/\s/g,''))){t={x:c.x,y:c.y,t:c.t};break;}}
 }
 if(!t)throw Error('Label not rendered: '+label);
 const rect=canvas.getBoundingClientRect();let point;
 if(edge)point={x:t.x+8,y:t.y};
 else {const nodes=q.circles.filter(x=>x.canvas===canvas&&Math.abs(x.t-t.t)<35&&x.r>5&&x.wx!==undefined);let c=nodes.sort((a,b)=>Math.hypot(a.x-t.x,a.y-t.y)-Math.hypot(b.x-t.x,b.y-t.y))[0];if(!c||Math.hypot(c.x-t.x,c.y-t.y)>c.r*1.5)throw Error('Label association failed: '+label);c=q.circles.filter(x=>x.canvas===canvas&&Math.abs(x.wx-c.wx)<.01&&Math.abs(x.wy-c.wy)<.01).at(-1)||c;point={x:c.x,y:c.y,r:c.r};}
 if(!allowOutside&&(point.x<rect.left||point.x>rect.right||point.y<rect.top||point.y>rect.bottom))throw Error('Target outside graph: '+label);
 return point;
}
