// v10 이식: film-commands/32.mjs 
import {v10} from '../ui.mjs';
import {correctHandle} from '../lib/color-recovery.mjs';
export default async ctx=>{
 const c=await v10(ctx);await c.begin();
 c.noteHandle=()=>correctHandle(c,'모아 두는 데서');
 await c.say('live-second-topic-intro');await c.source('N20-02',()=>c.click('text','새로 만들기'));await c.say('live-peek-full-r2',()=>c.click('css','[role=region] a[aria-label="전체 페이지로 열기"]'));
 await c.source('N20-03',async()=>{await c.click('title','');await c.type('지식 자산화');});await c.say('live-page-enter-r3',()=>c.key('Enter'));await c.say('live-example-label');
 await c.source('N20-05',()=>c.type('배운 것을 한 번 읽고 끝내지 않고, 필요할 때 다시 꺼내 쓰는 방법을 생각합니다.'));await c.source('N11-02',()=>c.key('Enter'));
 await c.say('live-filter-callout-r5',()=>c.type('/콜아웃'));await c.source('N20-08',()=>c.click('menu','콜아웃'));await c.say('live-bold-short-r4',()=>c.key('Control+b'));
 await c.source('N20-09',()=>c.type('모아 두는 데서, 다시 꺼내 쓰는 데까지'));await c.say('live-normal-short-r4',()=>c.key('Control+b'));await c.source('N20-10',()=>c.key('Shift+Enter'));
 await c.source('N20-11',()=>c.type('내 말로 정리하면 무엇을 알고 무엇이 아직 모호한지 드러난다. 출처도 함께 남겨 두면 나중에 다시 확인하기 좋다.'));
 await c.source('N20-15',()=>c.noteHandle());await c.source('N20-16',async()=>{const q=await c.locate('menu','색');await c.move(q.x,q.y);});await c.say('live-color-find-r3',()=>c.hoverColor('파란색 배경'));await c.source('N20-17',()=>c.click('menu','파란색 배경'));
 await c.say('live-callout-exit-first-v2-r5',async()=>{await c.endOf('[role=note] [contenteditable=true][role=textbox]');await c.key('Enter');});await c.say('live-callout-exit-second-r5',()=>c.exitCallout());
 await c.say('live-heading-search-r6',()=>c.type('/제목'));await c.say('fix-heading-two',()=>c.click('menu','제목2'));await c.say('live-example-heading',()=>c.type('내 말로 남기는 짧은 메모'));await c.source('N20-22',()=>c.key('Enter'));
 await c.say('live-bullet-search-r2',()=>c.type('/글머리'));await c.source('N11-08',()=>c.click('menu','글머리 기호 목록'));
 await c.say('live-example-one',()=>c.type('기록의 목적은 다시 찾고 활용하는 것이다.'));
 await c.say('live-example-two',async()=>{await c.key('Enter');await c.type('원문과 내가 이해한 내용을 구분해 남긴다.');});
 await c.say('live-example-three',async()=>{await c.key('Enter');await c.type('나중에 다시 보고 싶은 질문도 함께 남긴다.');});
 await c.source('N11-14',()=>c.key('Enter'));await c.say('N11-v020-r2',()=>c.key('Enter'));
 await c.say('live-toggle-search-r2',()=>c.type('/토글'));await c.source('N13-02',()=>c.click('menu','토글 목록'));await c.say('live-example-question',()=>c.type('어떻게 다시 찾아볼까?'));
 await c.source('N13-04',()=>c.click('aria','열기'));await c.source('N13-05',()=>c.click('text','빈 토글입니다. 클릭하거나 블록을 내부로 드래그하세요.'));await c.say('live-example-answer',()=>c.type('주제 이름을 분명하게 정하고 필요한 출처를 함께 남긴다.'));await c.source('N13-10',()=>c.click('aria','닫기'));
 await c.say('live-example-finish');await c.say('live-home-list-r2',()=>c.home());
 return 'Second topic filled with short learning examples';
};
