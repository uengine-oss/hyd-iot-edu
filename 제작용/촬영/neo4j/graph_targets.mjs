export function installGraphObserver(){
 if(window.__forestRead)return;
 window.__forestRead={texts:[],circles:[]};
 for(const name of ['fillText','arc']){const orig=CanvasRenderingContext2D.prototype[name];CanvasRenderingContext2D.prototype[name]=function(...args){
  if(this.canvas.matches?.('[data-testid="nvl-c2d-canvas"]')){const m=this.getTransform(),r=this.canvas.getBoundingClientRect(),x=name==='fillText'?args[1]:args[0],y=name==='fillText'?args[2]:args[1];const item={text:name==='fillText'?args[0]:null,x:r.x+(m.a*x+m.c*y+m.e)*r.width/this.canvas.width,y:r.y+(m.b*x+m.d*y+m.f)*r.height/this.canvas.height,r:name==='arc'?args[2]*Math.abs(m.a)*r.width/this.canvas.width:null,t:Date.now(),canvas:this.canvas};const a=window.__forestRead[name==='fillText'?'texts':'circles'];a.push(item);if(a.length>2500)a.splice(0,1250);}
  return orig.apply(this,args);
 };}
}
export function graphTarget({label,edge=false}){
 const canvas=Array.from(document.querySelectorAll('[data-testid="nvl-c2d-canvas"]')).find(c=>c.getBoundingClientRect().height>0),q=window.__forestRead;if(!canvas||!q)throw Error('Graph not visible');
 const t=q.texts.filter(x=>x.canvas===canvas&&x.text===label).at(-1);if(!t)throw Error('Label not rendered: '+label);
 const rect=canvas.getBoundingClientRect();let point;
 if(edge)point={x:t.x+8,y:t.y};
 else {const nodes=q.circles.filter(x=>x.canvas===canvas&&Math.abs(x.t-t.t)<35&&x.r>5);const c=nodes.sort((a,b)=>Math.hypot(a.x-t.x,a.y-t.y)-Math.hypot(b.x-t.x,b.y-t.y))[0];if(!c||Math.hypot(c.x-t.x,c.y-t.y)>c.r*1.5)throw Error('Label association failed: '+label);point={x:c.x,y:c.y};}
 if(point.x<rect.left||point.x>rect.right||point.y<rect.top||point.y>rect.bottom)throw Error('Target outside graph: '+label);
 return point;
}
