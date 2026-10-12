"""Saved actual deferral and Codex builtin contract in independent Chromium."""
import json
from pathlib import Path
from copy import deepcopy
from test_portal_remaining_ui import page,record_components,WWW
from test_portal_failure_states_ui import retain

SNAPSHOT=Path(__file__).parent/'fixtures/portal_pm_deferral.json'

def test_saved_actual_deferral_renders_partial_package_milestone_and_unknown_parts(page):
 source=json.loads(SNAPSHOT.read_text(encoding='utf-8'));event=source['event'];before=deepcopy(event)
 record_components(page)
 page.evaluate("ev=>{selectTab('instances');document.querySelector('#instDetail').innerHTML='<div id=pmDeferral>'+hydTrace.rowsOf([ev]).map(r=>hydTrace.rowHtml(r,false)).join('')+'</div>';}",event)
 text=page.locator('#pmDeferral').inner_text()
 assert '평가 보류' in text and '업무 완료 아님' in text
 assert page.locator('#pmDeferral [data-pm-asset]').count()>0
 assert '4,000' in text and '12,000' in text and '리턴' in text
 assert '미확인' in text or '확인 안 됨' in text
 for token in ('maintenanceDiagnostics','_deferral','WO_RESCHEDULE','execution:pm-plan','AnomalyPattern.code'):
  assert token not in text
 retain(page,'saved-actual-B-deferral','#pmDeferral','Actual saved GET evidence replayed in isolated Chromium; product rendering only, no new worker run and no current re-evaluation.',['평가 보류','4,000','12,000','리턴'])
 raw=page.locator('#pmDeferral details[data-deferral-raw]')
 raw.locator(':scope > summary').focus();page.keyboard.press('Enter')
 assert json.loads(raw.locator('pre').inner_text())==event['data']['receipt']['assessment']
 assert event==before


def test_codex_shell_string_read_contract_has_known_name_and_narrow_purpose(page):
 record_components(page)
 command='"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Raw -Encoding UTF8 -LiteralPath \'context/task.json\'"'
 assert page.evaluate('UI.toolName("shell")')=='명령 실행'
 result=page.evaluate('s=>hydWords.ask("shell",s)',command)
 assert '파일 본문 읽기' in result and '작업 입력' in result
 assert 'Get-Content' not in result and 'powershell.exe' not in result
 assert '목적 기록 없음' in page.evaluate('hydWords.ask("shell","Remove-Item data; Get-Content context/task.json")')


def test_saved_deferral_reaches_case_record_and_task_output_without_registering_decision(page):
 source=json.loads(SNAPSHOT.read_text(encoding='utf-8'));ev=source['event'];receipt=ev['data']['receipt']
 record_components(page)
 view={'instance':{'proc_inst_id':ev['proc_inst_id'],'status':'RUNNING','initial_variables':{},'variables_data':[{'key':'_deferral','value':receipt}]},'definition':{'activities':[{'id':'T_agent','name':'업무 평가'}]},'workitems':[{'id':ev['todo_id'],'activity_id':'T_agent','activity_name':'업무 평가','agent_orch':'cliagents','agent_mode':'autonomous','status':'PENDING','output':{'_deferral':receipt}}],'events':[ev]}
 page.evaluate("v=>{selectTab('instances');const model=hydRecord.build(v);document.querySelector('#instDetail').innerHTML='<div id=recordDeferral>'+model.steps.map((s,i)=>'<li class=\"cr-step open\">'+hydRecord.stepHtml(s,i,model.steps.length,true)+'</li>').join('')+'</div>';document.querySelectorAll('#recordDeferral [data-open-default]').forEach(d=>d.open=true);}",view)
 text=page.locator('#recordDeferral').inner_text()
 assert '평가 보류' in text and '4,000' in text and '12,000' in text
 assert '판단 등록 · 승인 · 실행 기록이 아닙니다' in text
 assert page.locator('#recordDeferral [data-pm-asset]').count()>0
 task=(WWW/'taskDetail.js').read_text(encoding='utf-8').replace('window.hydTaskDetail = { open,','window.hydTaskDetail = { valueHtml, open,')
 page.add_script_tag(content=task)
 page.evaluate("r=>document.querySelector('#instDetail').innerHTML='<div id=taskDeferral>'+hydTaskDetail.valueHtml('_deferral',r,{})+'</div>'",receipt)
 assert page.locator('#taskDeferral [data-pm-asset]').count()>0
 assert '4,000' in page.locator('#taskDeferral').inner_text() and '12,000' in page.locator('#taskDeferral').inner_text()


def test_deferral_missing_evaluation_is_unknown_and_raw_is_retained(page):
 record_components(page)
 receipt={'reason':'원문 조회 실패','assessment':{'reason':'원문 조회 실패','status':'UNKNOWN','evidence':{'evaluate_cards':{'result':'error','document':{'options':[]}}}}}
 page.evaluate("r=>{selectTab('instances');document.querySelector('#instDetail').innerHTML='<div id=unknownDeferral>'+hydWords.deferralEvidenceHtml(r)+'</div>'}",receipt)
 text=page.locator('#unknownDeferral').inner_text()
 assert '평가 보류' in text and '확인할 수 없습니다' in text
 assert '평가 대안 0개' not in text and '승인 완료' not in text
 assert page.locator('#unknownDeferral [data-pm-asset]').count()==0
 raw=page.locator('#unknownDeferral details[data-deferral-raw]');raw.locator('summary').click()
 assert json.loads(raw.locator('pre').inner_text())==receipt['assessment']


def test_registered_ontology_basis_alias_keeps_exact_description_in_fold(page):
 record_components(page)
 basis='ontology AnomalyPattern.code pattern'
 page.evaluate("s=>{selectTab('instances');document.querySelector('#instDetail').innerHTML='<div id=basisAlias>'+hydRecord.knowledgeHtml({v:{}},null,{origin:{cause_basis:s}})+'</div>'}",basis)
 text=page.locator('#basisAlias').inner_text()
 assert '이상 패턴 코드' in text and 'AnomalyPattern.code' not in text
 raw=page.locator('#basisAlias details');raw.locator('summary').focus();page.keyboard.press('Enter')
 assert json.loads(raw.locator('pre').inner_text())['cause_basis']==basis
