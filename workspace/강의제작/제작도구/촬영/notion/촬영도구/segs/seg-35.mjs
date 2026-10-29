// v10 이식: film-commands/35.mjs 
import {openFilePopup} from '../lib/file-popup.mjs';
import {v10} from '../ui.mjs';
import {finishTable} from '../lib/table-finish.mjs';
export default async ctx=>{
 const c=await v10(ctx);await c.begin();
 await c.say('live-image-purpose');await c.say('live-property-settings-r3',()=>c.click('css','.notion-collection-edit-view'));
 await c.say('live-property-edit',async()=>{await c.hoverSel('loc=role:menuitem[name="속성 편집"]');await c.click('menu','속성 편집');});await c.say('live-property-new',()=>c.click('menu','새 속성'));
 await c.say('live-image-name',async()=>{await c.click('css','input[placeholder="속성 이름"]');await c.type('카드 이미지');});await c.say('live-image-kind',()=>c.click('menu','파일과 미디어'));await c.say('live-property-close-r3',()=>c.click('aria','닫기'));
 await c.say('live-gallery-return',()=>c.click('text','주제 카드'));
 await c.say('live-image-topic',()=>c.click('text','Notion 익히기'));await c.say('live-peek-full-r3',()=>c.click('css','[role=region] a[aria-label="전체 페이지로 열기"]'));
 await c.say('live-value-field',()=>c.slot('분야'));await c.say('live-value-tool',()=>c.role('option','도구'));await c.say('live-value-understanding',()=>c.slot('이해도'));await c.say('live-value-example',()=>c.role('option','대충 앎'));
 await c.say('live-image-property',()=>c.slot('카드 이미지'));await openFilePopup(c);await c.say('live-image-link-tab-v2',()=>c.role('tab','링크'));
 const url=name=>'https://raw.githubusercontent.com/uengine-oss/hyd-iot-edu/662a6749/'+encodeURI('workspace/강의제작/제작도구/촬영/notion/design/'+name+'.png');
 await c.say('live-image-link-notion',async()=>{await c.popupInput();await c.serial(()=>c.p.keyboard.insertText(url('notion')));});await c.say('live-image-link-apply-v2',()=>c.role('button','링크'));await c.say('live-file-popup-dismiss-v2',async()=>{await c.key('Escape');await c.sleep(300);await c.key('Escape');});await c.say('live-image-check');
 await c.say('live-home-list-r3',()=>c.home());await c.say('fix-second-topic-open',()=>c.click('text','지식 자산화'));await c.say('live-peek-full-r4',()=>c.click('css','[role=region] a[aria-label="전체 페이지로 열기"]'));
 await c.say('live-value-field',()=>c.slot('분야'));await c.say('live-value-study',()=>c.role('option','학습 방법'));await c.say('live-value-understanding-r2',()=>c.slot('이해도'));await c.say('live-value-example-r2',()=>c.role('option','대충 앎'));
 await c.say('live-image-property-r2',()=>c.slot('카드 이미지'));await openFilePopup(c);await c.say('live-image-link-tab-v2-r2',()=>c.role('tab','링크'));await c.say('live-image-link-knowledge',async()=>{await c.popupInput();await c.serial(()=>c.p.keyboard.insertText(url('knowledge')));});await c.say('live-image-link-apply-v2-r2',()=>c.role('button','링크'));await c.say('live-file-popup-dismiss-v2-r2',async()=>{await c.key('Escape');await c.sleep(300);await c.key('Escape');});
 await c.say('live-home-list-r4',()=>c.home());
 await c.source('N21-21',()=>c.click('css','.notion-collection-edit-view'));await c.say('live-gallery-preview',()=>c.click('menu','레이아웃'));
 await c.source('N21-23',()=>c.click('text','카드 미리보기'));await c.say('live-preview-property',async()=>{await c.click('menu','페이지 속성');await c.click('menu','카드 이미지');});await c.line('방금 올린 그림이 카드에 보이도록 연결하는 설정입니다.');
 await c.source('N21-25',()=>c.click('text','카드 크기'));await c.source('N21-26',()=>c.click('menu','작게'));await c.say('fix-close-settings',()=>c.click('aria','닫기'));
 await c.line('두 카드의 그림과 제목을 볼까요.');await c.line('같은 계열의 그림을 쓰니 서로 다른 주제도 하나의 노트처럼 보입니다.');
 await finishTable(c);
 return 'Gallery images, visible fields and search verified';
};
