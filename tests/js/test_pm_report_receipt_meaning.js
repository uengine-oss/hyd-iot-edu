'use strict';
const fs=require('fs'),vm=require('vm'),path=require('path'),assert=require('assert');
const ctx={window:{},UI:{status:s=>s},esc:s=>String(s)};vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../../it/portal/www/resultReport.js'),'utf8'),ctx);
const R=ctx.window.hydResultReport;
const receipt={ok:true,code:'WO_CREATE',ref:'WO-1',detail:'Source-scoped maintenance orders registered',after:{plan:{code:'WO_CREATE',assets:[{asset:'HYD-02'}]},orders:[{id:'WO-1',asset:'HYD-02'}]}};
const report={refs:{work_order:'WO-1'},summary:'정비 오더 WO-1 등록 · 생산팀 공지 — '+receipt.detail,incident_closed:false};
const before=JSON.stringify({receipt,report});
assert.equal(R.receiptDetail(receipt),'원문 정비 범위 HYD-02 오더 등록');
assert.equal(R.reportSummary(report,{work_order:receipt}),'정비 오더 WO-1 등록 · 생산팀 공지 — 원문 정비 범위 HYD-02 오더 등록');
assert.equal(R.incidentMeaning(report,{state:'CLOSED'},{state:'ok'}),'이 보고에서 사건 종결 처리: 수행 안 함 · 현재 사건: 종결');
assert.match(R.incidentMeaning(report,null,{state:'error'}),/조회 실패/);
assert.match(R.incidentMeaning(report,null,{state:'loading'}),/조회 중/);
assert.equal(JSON.stringify({receipt,report}),before);
for(const change of [{code:'UNKNOWN'},{ok:false},{after:{}},{ref:'WRONG'},{detail:'사용자가 쓴 '+receipt.detail}]) assert.equal(R.receiptDetail({...receipt,...change}),({...receipt,...change}).detail);
assert.equal(R.reportSummary({...report,summary:'자유문 '+report.summary},{work_order:receipt}),'자유문 '+report.summary);
assert.equal(R.reportSummary({...report,refs:{work_order:'WRONG'}},{work_order:receipt}),report.summary);
if(process.argv[2]) {
 const actual=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
 const found=[];function walk(x){if(!x||typeof x!=='object')return;if(x.code==='WO_CREATE'&&x.detail===receipt.detail)found.push(x);Object.values(x).forEach(walk);}walk(actual);
 assert(found.length,'Actual completed receipt absent');
 for(const r of found) assert.equal(R.receiptDetail(r),'원문 정비 범위 HYD-02 오더 등록');
 console.log('Actual completed receipts verified:',found.length);
}
console.log('PM receipt/report meaning contracts PASS');
