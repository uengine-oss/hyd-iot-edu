// v10 이식: film-commands/38.mjs 
import {v10} from '../ui.mjs';
export default async ctx=>{
 const c=await v10(ctx);await c.begin();
 await c.line('노트가 준비됐으니 다른 사람에게 보여 주는 위치를 보겠습니다.');await c.source('N26-01',()=>c.role('button','공유'));
 await c.line('이 화면에서는 누가 접근할 수 있는지와 어떤 권한을 갖는지를 확인합니다.');await c.say('live-sharing-point');await c.line('내 노트를 보여 주기만 할 때는 읽는 권한부터 생각하시면 됩니다.');await c.say('live-sharing-copy');await c.say('live-sharing-close',()=>c.key('Escape'));
 await c.source('N27-01',()=>c.role('button','공유'));await c.source('N27-02',()=>c.role('tab','게시'));await c.line('웹페이지처럼 공개하는 기능이 이곳에 있습니다.');
 await c.say('new-publish-explain',()=>c.hoverLabel('게시',true));
 await c.line('정해진 사람과 함께 보는 공유와 웹에 공개하는 게시를 구별해 두시면 됩니다.');await c.say('new-publish-close',()=>c.key('Escape'));
 await c.say('live-comment-top',()=>c.scroll(-1000));await c.say('live-comment-select',()=>c.selectText('관심 있는 주제를 모으고, 배운 내용을 나만의 방식으로 쌓아 갑니다.'));await c.say('live-comment-key',async()=>{await c.key('Control+Shift+m');await c.serial(()=>c.p.waitForFunction(()=>!!document.querySelector('[role=dialog] [role=textbox][aria-label="댓글 추가"]'),undefined,{timeout:8000}));});await c.say('live-comment-close',async()=>{await c.key('Escape');await c.serial(()=>c.p.waitForFunction(()=>!document.querySelector('[role=dialog] [role=textbox][aria-label="댓글 추가"]'),undefined,{timeout:8000}));});
 await c.line('마지막으로 지금 만든 노트를 파일로 받아 보겠습니다.');await c.source('N28-01',()=>c.click('aria','작업'));await c.source('N28-02',()=>c.click('menu','더보기'));await c.source('N28-03',()=>c.click('menu','내보내기'));
 // 내보내기 창의 선택지를 차례로 짚으며 설명한다(PDF는 말로만).
 const format=await c.serial(()=>c.p.evaluate(()=>[...document.querySelectorAll('[role=dialog] [role=button]')].map(e=>e.textContent.trim()).find(x=>['HTML','Markdown & CSV','PDF'].includes(x))));if(!format)throw Error('Export format missing');
 await c.say('new-export-format-open',()=>c.click('text',format));
 await c.say('new-export-format-explain');
 await c.say('new-export-format-pick',()=>c.click('menu','HTML'));
 await c.say('new-export-view',()=>c.hoverLabel('데이터베이스 보기'));
 await c.say('new-export-content',()=>c.hoverLabel('페이지 콘텐츠'));
 await c.fs.writeFile(c.out+'/export-dialog-state.txt',await c.snapshot());
 await c.fs.writeFile(c.out+'/export-switches.json',JSON.stringify(await c.serial(()=>c.p.evaluate(()=>[...document.querySelectorAll('[role=switch],[role=checkbox],input[type=checkbox]')].map(e=>({html:e.outerHTML,parent:e.parentElement.outerHTML})))),null,2));
 return 'Sharing, publishing and comments shown; export configured';
};
