// 시험(수업 아님): 클릭 · 입력 없이 화살표만 화면 여러 곳으로 옮겨 이동 끝 되돌림과 프레임 공백을 확인한다. 페이지 내용은 바꾸지 않는다.
import {v10} from '../ui.mjs';
export default async ctx=>{
 const c=await v10(ctx);await c.begin();
 const v=await c.serial(()=>c.raw.evaluate(()=>({w:innerWidth,h:innerHeight})));
 const pts=[[.62,.55],[.15,.3],[.8,.7],[.4,.2],[.7,.85],[.25,.75],[.9,.35],[.5,.5]];
 for(const [fx,fy] of pts){await c.move(Math.round(v.w*fx),Math.round(v.h*fy));await c.sleep(500);}
 return 'motion test done';
};
