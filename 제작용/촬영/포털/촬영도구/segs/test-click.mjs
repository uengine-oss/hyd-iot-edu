// 클릭 · 스크롤 · 고르기 시험(음성 없음). 메뉴를 눌러 화면을 바꾸고, 화면 안을 굴려 내리고, 위 막대의 「나 고르기」로 역할을 고른다.
import {portal} from '../ui.mjs';
export default async function(ctx){
 const c=await portal(ctx);
 await ctx.begin();
 await ctx.silent('c1','왼쪽 메뉴에서 결함 시뮬레이션을 눌러 보겠습니다.',()=>c.click({tab:'scenario'}));
 await ctx.waitFor(()=>document.querySelector('.rail nav button.active')?.dataset.tab==='scenario');
 await ctx.silent('c2','설비 카드가 세 개 있습니다. 아래로 내려 보겠습니다.',()=>c.scroll(520,{text:'HYD-02',tag:'*'}));
 await ctx.silent('c3','다시 위로 올리겠습니다.',()=>c.scroll(-520));
 await ctx.silent('c4','이번에는 지식 관리를 열겠습니다.',()=>c.click({tab:'knowledge'}));
 await ctx.waitFor(()=>document.querySelector('.rail nav button.active')?.dataset.tab==='knowledge');
 await ctx.silent('c5','위쪽 가운데 나 고르기를 누르겠습니다.',()=>c.click({text:'나 고르기',tag:'button'}));
 await ctx.sleep(600);
 return {pos:c.pos()};
}
