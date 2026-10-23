// v10 이식: film-commands/33.mjs 
import {v10} from '../ui.mjs';
export default async ctx=>{
 const c=await v10(ctx);await c.begin();
 await c.source('N22-01',()=>c.click('aria','보기 추가'));await c.source('N22-02',()=>c.click('menu','표'));
 await c.source('N22-03',()=>c.click('css','input[placeholder="보기 이름"]'));await c.source('N22-04',async()=>{await c.key('Control+a');await c.type('전체 주제');});await c.say('live-view-create-done',()=>c.click('text','완료'));
 await c.say('live-close-settings',()=>c.click('aria','닫기'));
 await c.line('새 데이터 소스를 만들지 않고 같은 주제 모음을 다른 모습으로 보는 겁니다.');await c.line('갤러리와 표가 각각 다른 노트를 갖는 것이 아닙니다.');
 await c.say('live-property-settings',()=>c.click('css','.notion-collection-edit-view'));
 await c.say('live-property-edit',async()=>{await c.hoverSel('loc=role:menuitem[name="속성 편집"]');await c.click('menu','속성 편집');});
 await c.say('live-property-new',()=>c.click('menu','새 속성'));
 await c.fs.writeFile(c.out+'/property-create-state.txt',await c.snapshot());
 return 'Table view and property editor ready';
};
