// v10 이식: film-commands/34.mjs 
import {v10} from '../ui.mjs';
export default async ctx=>{
 const c=await v10(ctx);await c.begin();
 await c.say('live-property-field',async()=>{await c.click('css','input[placeholder="속성 이름"]');await c.type('분야');});await c.say('live-property-kind',()=>c.click('menu','선택'));
 for(const [voice,text] of [['live-property-option-tool','도구'],['live-property-option-study','학습 방법'],['live-property-option-ai','AI 실습']]){
  if(!(await c.serial(()=>c.p.evaluate(()=>!!document.querySelector('input[placeholder="새 옵션을 입력하세요"]')))))await c.say('live-property-add-option',()=>c.click('text','옵션 추가'));await c.say(voice,async()=>{await c.click('css','input[placeholder="새 옵션을 입력하세요"]');await c.type(text);await c.key('Enter');});
 }
 await c.say('live-property-close',()=>c.click('aria','닫기'));
 await c.say('live-property-settings',()=>c.click('css','.notion-collection-edit-view'));
 await c.say('live-property-edit',async()=>{await c.hoverSel('loc=role:menuitem[name="속성 편집"]');await c.click('menu','속성 편집');});await c.say('live-property-new',()=>c.click('menu','새 속성'));
 await c.say('live-understanding-field',async()=>{await c.click('css','input[placeholder="속성 이름"]');await c.type('이해도');});await c.say('live-property-kind',()=>c.click('menu','선택'));
 for(const [voice,text] of [['live-understanding-first','설명 못함'],['live-understanding-second','대충 앎'],['live-understanding-third','설명 가능']]){
  if(!(await c.serial(()=>c.p.evaluate(()=>!!document.querySelector('input[placeholder="새 옵션을 입력하세요"]')))))await c.say('live-property-add-option',()=>c.click('text','옵션 추가'));await c.say(voice,async()=>{await c.click('css','input[placeholder="새 옵션을 입력하세요"]');await c.type(text);await c.key('Enter');});
 }
 await c.say('live-property-close',()=>c.click('aria','닫기'));await c.say('live-understanding-purpose');
 await c.fs.writeFile(c.out+'/table-state.txt',await c.snapshot());
 return 'Topic categories and self-assessment options created';
};
