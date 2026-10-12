'use strict';
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const www=path.join(__dirname,'../../it/portal/www');
const ctx={console,document:{querySelectorAll:()=>[],getElementById:()=>null,addEventListener:()=>{}},location:{hash:''},setTimeout:()=>0,localStorage:{getItem:()=>null}};
ctx.window=ctx;vm.createContext(ctx);
vm.runInContext('const esc=s=>String(s??"");',ctx);
for(const file of ['ui.js','plainWords.js']) vm.runInContext(fs.readFileSync(path.join(www,file),'utf8'),ctx);
ctx.UI=vm.runInContext('UI',ctx);
ctx.UI.names=JSON.parse(fs.readFileSync(path.join(www,'names.json'),'utf8'));
assert.equal(ctx.hydWords.code('WO_CREATE'),'정비 오더 등록');
assert.equal(ctx.hydWords.code('WO_COMPLETE'),'정비 오더 완료');
assert.equal(ctx.hydWords.action({code:'WO_CREATE'}),'정비 오더 등록');
// 기존 화면의 정비 요청 별칭은 이미 정책을 만족하므로 유지한다.
assert.equal(ctx.UI.flowName('정비 작업지시'),'정비 요청');
for(const id of ['action:work-order','proc:maintenance-wo','skill:cancel-work-order','skill:schedule-maintenance']) assert.match(ctx.UI.names[id],/정비 오더/);
assert.equal(ctx.hydWords.text('원문: 작업지시 WO-OLD'),'원문: 작업지시 WO-OLD');
assert.equal(ctx.hydWords.code('UNKNOWN'),'UNKNOWN');
console.log('Maintenance display labels PASS; original text and unknown code preserved');
