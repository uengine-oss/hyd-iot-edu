// 클릭 없이 화살표만 움직이는 시험(프레임 · 휘청 확인). 왼쪽 메뉴 몇 곳과 화면 가운데를 오간다. 음성 없음(silent).
import {portal} from '../ui.mjs';
export default async function(ctx){
 const c=await portal(ctx);
 await ctx.begin();
 await ctx.silent('t1','왼쪽에 메뉴가 세로로 모여 있어요. 위에서부터 짚어 볼게요.',()=>c.point({tab:'inbox'}));
 await ctx.silent('t2','설비 묶음의 결함 시뮬레이션이 여기 있고요.',()=>c.point({tab:'scenario'}));
 await ctx.silent('t3','지식 묶음 아래 지식 관리가 있습니다.',()=>c.point({tab:'knowledge'}));
 await ctx.silent('t4','맨 아래 시스템 묶음에는 홈이 있어요.',()=>c.point({tab:'main'}));
 await ctx.silent('t5','가운데 화면으로 돌아오겠습니다.',()=>c.move(820,380));
 await ctx.silent('t6','오른쪽 위로도 한 번 가 볼게요.',()=>c.move(1180,110));
 return {pos:c.pos()};
}
