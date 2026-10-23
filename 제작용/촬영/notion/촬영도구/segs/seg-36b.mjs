// 구간36 뒷부분(take-36이 '/콜아웃' 입력 중 '/콜'에서 멈춤 — Zoom으로 PC가 느려 입력 명령 시간 초과). 같은 화면(슬래시 메뉴 열림)에서 남은 '아웃'부터 잇는다.
import {v10} from '../ui.mjs';
import {correctHandle} from '../lib/color-recovery.mjs';
export default async ctx=>{
 const c=await v10(ctx);await c.begin();
 c.noteHandle=()=>correctHandle(c,'나의 주제를');
 await c.type('아웃');await c.source('N24-08',()=>c.click('menu','콜아웃'));await c.say('live-bold-short',()=>c.key('Control+b'));
 await c.say('live-template-callout-title',()=>c.type('나의 주제를, 나의 방식으로'));await c.say('live-normal-short',()=>c.key('Control+b'));await c.source('N24-10',()=>c.key('Shift+Enter'));await c.say('live-template-callout-body',()=>c.type('짧은 글부터 시작하세요. 아래 항목은 필요한 만큼 바꾸고 모두 채울 필요는 없습니다.'));
 await c.source('N24-15',()=>c.noteHandle());await c.source('N24-16',async()=>{const q=await c.locate('menu','색');await c.move(q.x,q.y);});await c.say('live-color-find',()=>c.hoverColor('파란색 배경'));await c.source('N24-17',()=>c.click('menu','파란색 배경'));
 await c.say('live-callout-exit-first-v2',async()=>{await c.endOf('[role=note] [contenteditable=true][role=textbox]');await c.key('Enter');});await c.say('live-callout-exit-second',()=>c.exitCallout());
 await c.say('live-heading-search',()=>c.type('/제목'));await c.source('N24-22',()=>c.click('menu','제목2'));await c.say('live-template-section',()=>c.type('나의 기록'));await c.source('N11-06',()=>c.key('Enter'));
 await c.say('live-bullet-search',()=>c.type('/글머리'));await c.source('N11-08',()=>c.click('menu','글머리 기호 목록'));await c.say('live-template-prompt-one',()=>c.type('기억하고 싶은 내용'));await c.say('live-template-prompt-two',async()=>{await c.key('Enter');await c.type('다시 보고 싶은 자료');});
 await c.source('N11-14',()=>c.key('Enter'));await c.source('N11-15',()=>c.key('Enter'));await c.say('live-toggle-search',()=>c.type('/토글'));await c.source('N13-02',()=>c.click('menu','토글 목록'));await c.say('live-template-question',()=>c.type('나에게 맞게 바꾸려면'));
 await c.source('N13-04',()=>c.click('aria','열기'));await c.source('N13-05',()=>c.click('text','빈 토글입니다. 클릭하거나 블록을 내부로 드래그하세요.'));await c.say('live-template-help',()=>c.type('항목 이름과 배치는 자유롭게 바꾸세요. 내용이 길어지면 하위 페이지로 나누세요.'));await c.source('N13-10',()=>c.click('aria','닫기'));
 const body=await c.serial(()=>c.p.evaluate(()=>{const r=document.querySelector('[role=region]')||document;const heading=[...r.querySelectorAll('[role=textbox]')].find(e=>e.textContent==='나의 기록');return{title:r.querySelector('h1')?.textContent,notes:[...r.querySelectorAll('[role=note]')].map(e=>({text:e.textContent,bg:getComputedStyle(e.firstElementChild).backgroundColor})),headingOutside:!!heading&&!heading.closest('[role=note]')};}));if(!body.headingOutside)throw Error('Template heading nested or missing');await c.fs.writeFile(c.out+'/template-body.json',JSON.stringify(body));
 await c.say('live-template-close',async()=>{await c.key('Escape');await c.key('Escape');});
 return 'Reusable new-topic template created';
};
