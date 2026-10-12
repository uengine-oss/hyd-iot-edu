"""Native tool rows describe purpose/count without losing original query/response."""
import json
from copy import deepcopy
import pytest
from test_portal_remaining_ui import page, record_components
from test_portal_failure_states_ui import retain

@pytest.mark.parametrize('tool,input,output,purpose,count',[
 ('mcp__neo4j__read_neo4j_cypher',{'query':"CALL db.index.fulltext.queryNodes('ont_names', $text) YIELD node, score RETURN node"+' /* long input */'*800},[{'type':'text','text':'[]'}],'이름·본문 검색','0건'),
 ('mcp__neo4j__read_neo4j_cypher',{'query':"MATCH (s:Skill)-[:CONSISTS_OF]->(a:Action) WHERE a.code CONTAINS 'PR_CREATE' RETURN s"},[{'type':'text','text':'[{"name":"구매 요청"}]'}],'조치 방법','1건'),
 ('mcp__enterprise__query',{'sql':'SELECT * FROM public.part_quotes WHERE part_no = $1'+' /* tail */'*800},{'rows':[]},'업무 DB 조회','0건'),
 ('Bash',{'command':'rg --files /workspace && python -c "print(1)"'+' # tail'*800},'one\ntwo','명령 실행','반환 본문'),
 ('future_tool',{'secret_argument':'internal_unknown_id','nested':{'full':'x'*5000}},{'future_schema':17},'목적 기록 없음','결과 형식'),
])
def test_native_tool_rows_have_shared_purpose_and_count_with_complete_original(page,tool,input,output,purpose,count):
 record_components(page)
 original=deepcopy((input,output))
 events=[{'id':'start','event_type':'tool_usage_started','data':{'tool':tool,'tool_use_id':'same','input':input}},
         {'id':'end','event_type':'tool_usage_finished','data':{'tool':tool,'tool_use_id':'same','output':output,'is_error':False}}]
 page.evaluate("evs=>{selectTab('instances');document.querySelector('#instDetail').innerHTML='<div id=semanticTrace>'+hydTrace.rowsOf(evs).map(r=>hydTrace.rowHtml(r,false)).join('')+'</div>';}",events)
 text=page.locator('#semanticTrace').inner_text()
 assert purpose in text and count in text
 for token in ('CALL db.index','MATCH (','SELECT *','rg --files','secret_argument','internal_unknown_id','future_schema','[] · text'):
  assert token not in text
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 if 'fulltext' in input.get('query',''):
  retain(page,'generic-tool-purpose-count','#semanticTrace','Isolated Chromium fixture using unmodified production renderer; long query and zero actual fixture rows. Not operating execution.',[purpose,count])
 fold=page.locator('#semanticTrace details.tr-tool')
 fold.locator(':scope > summary').focus();page.keyboard.press('Enter')
 blocks=fold.locator('pre').all_inner_texts()
 assert json.loads(blocks[1])==input
 assert (json.loads(blocks[2]) if not isinstance(output,str) else blocks[2])==output
 assert (input,output)==original


def test_actual_cost_producer_is_rendered_as_four_distinct_amounts_and_ties_are_honest(page):
 from hydcommon.purchase_comparison import compare
 skill={'source_id':'fixture-source','parts':['part:kit'],'actions':[{'code':'PR_CREATE','value':'sup:registered'}],
        'purchase_comparison_policy':{'version':1,'loss_per_failure':137,'inspection_threshold':0.02,'inspection_cost':17,
          'anchor':{'source_id':'fixture-source','quote':'독립 시험 원문: 불량 1건 손실 137만 원. 불량률이 2%를 넘으면 전수 검사 비용 17만 원.'}}}
 facts={'purchase_part':'part:kit','need_qty':6,'need_by_days':4,
        'spare_quotes':{'sup:registered':{'price':35,'fail_rate':0.04,'lead_d':2,'avl':True}}}
 comparison=compare(skill,facts)
 assert comparison['purchase_amount']==210 and comparison['expected_failure_cost']==32.88
 assert comparison['inspection_cost']==17 and comparison['total_cost']==259.88
 option={'id':'skill:purchase','name':'등록 공급사 구매','kind':'work_order','feasible':True,'rank':1,'score':-259.88,
         'evaluation_mode':'execution','execution_checked':True,'economicComparison':comparison,'actions':skill['actions'],
         'resolvedSupplier':{'id':'sup:registered','policy':'lowest_approved','quote':{'name':'등록 공급사','price':35,'lead_d':2,'avl':True}}}
 other={**deepcopy(option),'id':'skill:tied','name':'동일 비용 구매','rank':2}
 decision={'options':[option,other],'recommended':option['id'],'facts':facts,
           'origin':{'part':{'id':'part:kit','name':'정비 부품','partNo':'P-KIT'}},'evaluation_mode':'execution','execution_checked':True}
 original=deepcopy(decision)
 record_components(page)
 page.add_script_tag(path=str(__import__('test_portal_remaining_ui').WWW/'approvalCard.js'))
 page.evaluate("d=>{selectTab('instances');document.querySelector('#instDetail').innerHTML='<div id=costApproval>'+hydApprove.html(d,d.recommended,{pending:true})+'</div>';}",decision)
 text=page.locator('#costApproval').inner_text()
 for phrase in ('발주 금액','210만원','기대 불량 비용','32.88만원','전수 검사 비용','17만원','비교 총비용','259.88만원','손실 137만원','검사 기준 2 % 초과'):
  assert phrase in text
 for token in ('fixture-source','part:kit','sup:registered','purchase_amount','economicComparison'):
  assert token not in text
 retain(page,'purchase-cost-source-policy','#costApproval','Actual pure purchase comparison producer with independent source policy/quote fixture; 137 is deliberate to detect fixed cost assumptions. Not operating approval or ERP execution.',['발주 금액','기대 불량 비용','전수 검사 비용','비교 총비용'])
 tied=page.locator('#costApproval .ap-card > details').filter(has_text='다른 안')
 tied.locator(':scope > summary').focus();page.keyboard.press('Enter')
 text=tied.inner_text()
 assert '비교 총비용 같음' in text and '점수가 0 낮습니다' not in text
 raw=page.locator('#costApproval .ap-business details').first
 raw.locator(':scope > summary').focus();page.keyboard.press('Enter')
 assert json.loads(raw.locator('pre').inner_text())['economicComparison']==comparison
 assert decision==original


def test_absent_or_invalid_cost_values_are_not_inferred_from_purchase_amount(page):
 record_components(page)
 option={'actions':[{'code':'PR_CREATE','value':'sup:unknown'}],'facts':{'po_amount':400}}
 html=page.evaluate('o=>hydWords.purchaseContextHtml(o)',option)
 assert '비교 기록 없음' in html and '400' in html
 invalid={**option,'economicComparison':{'purchase_amount':None,'total_cost':False}}
 html=page.evaluate('o=>hydWords.purchaseContextHtml(o)',invalid)
 assert '금액 기록 미확인' in html and '총비용</dt><dd>0만원' not in html


def test_case_start_uses_known_pattern_and_identifies_references_without_claiming_their_contents(page):
 record_components(page)
 values={'pattern':'SPARE_BELOW_MIN','incident':'INC-original-exact','alert_id':'ERP-SPARE-original-exact','asset':'HYD-03'}
 view={'instance':{'proc_inst_id':'student.case','proc_def_id':'known','proc_inst_name':'구매 처리','status':'RUNNING',
                  'initial_variables':values,'variables_data':[]},'definition':{'processDefinitionName':'구매 처리','activities':[]},'events':[],'workitems':[]}
 page.evaluate("v=>{selectTab('instances');const m=hydRecord.build(v,{agents:[],people:[]});document.querySelector('#instDetail').innerHTML='<div id=startSemantic>'+hydRecord.stepHtml(m.steps[0],0,m.steps.length,true)+'</div>';}",view)
 text=page.locator('#startSemantic').inner_text()
 assert '예비품 재고 기준 이탈' in text and '사건 식별값 있음' in text and '경보 식별값 있음' in text
 for value in ('SPARE_BELOW_MIN','INC-original-exact','ERP-SPARE-original-exact'):
  assert value not in text
 raw=page.locator('#startSemantic details').filter(has_text='시작 값 원문')
 raw.locator(':scope > summary').focus();page.keyboard.press('Enter')
 assert json.loads(raw.locator('pre').inner_text())==values
 assert '표시 이름 기록 없음' in page.evaluate('hydWords.startValue("pattern","UNKNOWN_BUSINESS_PATTERN")')


@pytest.mark.parametrize('order',['interleaved','finish-first','reconnect-replay'])
def test_reused_provider_tool_id_pairs_only_within_same_case_task_and_job(page,order):
 record_components(page)
 from test_portal_remaining_ui import WWW
 task=(WWW/'taskDetail.js').read_text(encoding='utf-8').replace('window.hydTaskDetail = {','window.hydTaskDetail = { timelineItems,')
 page.add_script_tag(content=task)
 def event(job,kind,n):
  return {'id':job+'-'+kind,'proc_inst_id':'same-case','todo_id':'same-task','job_id':job,
          'event_type':'tool_usage_'+kind,'timestamp':f'2026-10-12T00:00:0{n}Z',
          'data':{'tool':'mcp__neo4j__read_neo4j_cypher','tool_use_id':'item_1',
                  **({'input':{'query':'MATCH (s:Skill) RETURN s','source_job':job}} if kind=='started' else {'output':[{'name':'조회된 항목'}] if job=='new' else [],'is_error':False})}}
 events=[event('old','started',1),event('new','started',2),event('old','finished',3),event('new','finished',4)]
 if order=='finish-first':events=[events[3],events[2],events[1],events[0]]
 if order=='reconnect-replay':events+=deepcopy(events)
 model=page.evaluate("evs=>({trace:hydTrace.rowsOf(evs),record:hydRecord.rowsOf(evs),legacy:hydTaskDetail.timelineItems({status:'DONE'},evs,{instance:{}},false)})",events)
 for renderer in ('trace','record'):
  rows=[r for r in model[renderer] if r['kind']=='tool']
  assert len(rows)==2 and len({r['key'] for r in rows})==2
  assert all(r['status']=='ok' for r in rows)
  by_job={r['input']['source_job']:r for r in rows}
  assert by_job['old']['output']==[] and len(by_job['new']['output'])==1
 legacy=[r for r in model['legacy'] if r.get('raw') and 'tool_use_id' in r['raw']]
 assert len(legacy)==2 and len({r['k'] for r in legacy})==2
 assert all(r['cls']=='done' for r in legacy)
 page.evaluate("evs=>{selectTab('instances');document.querySelector('#instDetail').innerHTML='<div id=identityTrace>'+hydTrace.rowsOf(evs).map(r=>hydTrace.rowHtml(r,false)).join('')+'</div>';}",events)
 keys=page.locator('#identityTrace details.tr-tool').evaluate_all('nodes=>nodes.map(n=>n.dataset.k)')
 assert len(keys)==len(set(keys))==2
 # Every identity coordinate participates; no unrelated run can close a current call.
 starts=[events[0]] if order!='finish-first' else [event('old','started',1)]
 other=event('old','finished',3);other['todo_id']='another-task'
 rows=page.evaluate('evs=>hydTrace.rowsOf(evs)',starts+[other])
 assert len(rows)==2 and rows[0]['status']=='running'


def test_protected_pr74_source_policy_and_actual_rank_producer_show_410_vs_360(page):
 from test_purchase_total_cost import data,run,QUOTE
 skills,facts,rules=data();decision=run(skills,facts,rules)
 original=deepcopy(decision)
 assert decision['recommended']=='skill:b'
 record_components(page)
 from test_portal_remaining_ui import WWW
 page.add_script_tag(path=str(WWW/'approvalCard.js'))
 page.evaluate("d=>{selectTab('instances');document.querySelector('#instDetail').innerHTML='<div id=originalCost>'+hydApprove.html(d,d.recommended,{pending:true})+'</div>';}",decision)
 text=page.locator('#originalCost').inner_text()
 for phrase in ('330만원','30만원','전수 검사 비용','0만원','360만원','손실 250만원','검사 기준 10 % 초과'):
  assert phrase in text
 assert 'purchase_total_cost' not in text and 'source_total_cost' not in text
 other=page.locator('#originalCost .ap-card > details').filter(has_text='다른 안')
 other.locator(':scope > summary').focus();page.keyboard.press('Enter')
 assert '410만원' in other.inner_text() and '높음' in other.inner_text()
 raw=page.locator('#originalCost .ap-business details').first
 raw.locator(':scope > summary').focus();page.keyboard.press('Enter')
 assert json.loads(raw.locator('pre').inner_text())['economicComparison']['policy']['anchor']['quote']==QUOTE
 assert decision==original
