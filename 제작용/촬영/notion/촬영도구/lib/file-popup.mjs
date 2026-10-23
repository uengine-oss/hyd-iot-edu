// 파일 · 이미지 추가 창 열기(hover로 열리고, 안 열리면 안내 후 클릭). v10: 직접 클릭은 c.clickSel
export async function openFilePopup(c){
 const ready=()=>c.serial(()=>c.p.evaluate(()=>[...document.querySelectorAll('[role=tab]')].some(e=>e.textContent.trim()==='링크'&&e.checkVisibility({checkVisibilityCSS:true}))));
 await c.say('live-file-hover',async()=>{const q=await c.locate('text','파일 또는 이미지를 추가하세요');await c.move(q.x,q.y);});
 for(let n=0;n<8&&!(await ready());n++)await c.sleep(200);
 if(!(await ready()))await c.say('live-file-click-fallback',async()=>{try{await c.clickSel('loc=role:button[name="파일 또는 이미지를 추가하세요"]');}catch(e){if(!(await ready()))throw e;}});
 await c.serial(()=>c.p.waitForSelector('loc=role:tab[name="링크"]',{state:'visible',timeout:8000}));
}
