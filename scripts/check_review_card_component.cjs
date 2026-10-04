/* Pure JS component contract check; no browser, portal server or network.
   Uses the deployed source function block and a preserved real API response. */
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
const source=fs.readFileSync('it/portal/www/enterprise.js','utf8');
const start=source.indexOf('const KIND_KO ='),end=source.indexOf('window.hydCards =');
assert(start>=0 && end>start);
const context={window:{},esc:v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))};
vm.createContext(context);vm.runInContext(source.slice(start,end)+'\nwindow.component={cardHtml,reviewMatches};',context);
const {cardHtml,reviewMatches}=context.window.component;
const review=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const option=review.snapshot.options[0],params=option.reviewed_choice.parameters;
const checks=[];
function check(name,ok){assert(ok,name);checks.push({name,passed:true});}
check('exact identity and parameters match',reviewMatches(review,review.scope.decision,option.id,params,{workitem:review.scope.workitem}));
check('a different parameter invalidates the review',!reviewMatches(review,review.scope.decision,option.id,{...params,fan_pct:94}));
check('a different work item invalidates the review',!reviewMatches(review,review.scope.decision,option.id,params,{workitem:'another'}));
check('a different decision invalidates the review',!reviewMatches(review,'another',option.id,params));
check('missing review is false',reviewMatches(null,review.scope.decision,option.id,params)===false);
const html=cardHtml(option);
check('card distinguishes original SOP and reviewed actions',html.includes('원문 SOP가 수정된 것은 아닙니다') && html.includes('FAN_SET=95') && html.includes('FAN_SET=100'));
check('card publishes source timestamp and model boundary',html.includes(option.forecastContext.source_t) && html.includes('교육용 시뮬레이터 모델'));
const excluded={...option,feasible:false};
check('excluded card can be selected only to review',!cardHtml(excluded,{selectable:true,pending:true,reviewable:true}).match(/<input[^>]* disabled/));
check('excluded default selection stays disabled',!!cardHtml(excluded,{selectable:true,pending:true}).match(/<input[^>]* disabled/));
check('card escapes changed action labels',!cardHtml({...option,name:'<script>wrong()</script>'}).includes('<script>'));
console.log(JSON.stringify({scope:'pure component; no browser render or click',checks},null,2));
