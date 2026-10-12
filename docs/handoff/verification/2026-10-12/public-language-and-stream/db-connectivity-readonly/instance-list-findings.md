# 상세 성공 / 목록 timeout 원인 조사

현재 `/api/instances?limit=50` 한 번을 실제GET으로 측정하여 HTTP200/0.633573초/2,461,066bytes/50행을 확인했다. 가장 큰 한 행은 JSON532,596bytes다. body는저장하지않고[instance-list-timing.json](instance-list-timing.json)에크기/시간만보존했다. 앞선shellpython-c인용실패는PythonSyntaxError이고HTTP0이며그후script1회만실제호출했다. 이번현재시점timeout재현은안됐다. 따라서목록단독2.46MB전달은확정하지만이것이과거timeout의단독원인이라고증명되지는않았다.

## 실제 query와 plan

`instance_mode.py:929`~932목록API는`repo.list_instances(status,limit,tenant)`원형그대로반환한다. `procdb.py:824`~833은`SELECT *`로variables_data/initial_variables등전체instancecolumn을반환한다. `_row:685`는datetime/UUID표현만바꾸며큰JSON을줄이지않는다. 프로세스업무본문/도구결과가포함된JSON을50개모두읽고전송하므로목록의상태/이름요약보다훨씬크다.

read-onlyEXPLAIN(ANALYZE없음)을실제DB에실행했고[instance-list-explain.log](instance-list-explain.log)를보존했다. 현재tenant/is_deleted/status없음조건은Seq Scan→start_date Sort→Limit50이며cost120.00..120.13/예상315행이다. 기존migration00001:151의index는(tenant_id,status,start_dateDESC)이므로status없음정렬에그대로최적이라고볼수없다. 그러나443행에서이plan만으로index가timeout근본원인이라고단정할수없다. 실제본회GET0.63초이므로새index/ANALYZE/서비스재시작을이번읽기조사에서실행하지않았다. 원본query의optionalnull조건은현재status/incident/asset모두null일때위predicate와동등하나runtimepreparedgenericplan은EXPLAIN상수query와다를수있다.

## 소비 계약과 안전한 좁은 해결안

`instances.js:33`은이목록을반복읽는다.17행outcomeChip은completed의variables_data에서result_report를사용한다. `hitl.js:139/176`은동일목록의variables_data.incident로incident→instance를찾는다. agentsPanel.js는proc_inst_name을읽고현재상태/현재activity_ids/이름/날짜도목록소비다. 따라서variables_data를통째로없애면incidentlink/결과칩을깨뜨린다. CaseRecord/TaskDetail의상세는별도GET본문을사용하므로전체JSON은그상세에서유지해야한다. F27의저장원문9개와검증계약을바꿀이유가없다.

최소범용안은**기존repo.list_instances의업무용계약을변경하지않고**목록API전용summary조회/DTO를추가하는것이다. `proc_inst_id/proc_def_id/proc_inst_name/status/start_date/end_date/current_activity_ids/tenant_id`등실제소비metadata를명시선택하고variables_data는incident/asset/result_report의결과칩필드등목록에필요한값만projection한다. initial_variables/장문proposal/도구원문/전체업무자료/승인객체는목록에서보내지않고기존상세GET이그대로반환한다. result_report도전체values/refs가아니라fromValues/verdictOf가필요로하는verdict/outcome/level/label등좁은필드를확인한뒤맞춘다. 보호되는DB원본을변경하거나truncate가짜본문을만들지않는다.

query projection을DB에서수행하면TOAST큰variables본문의선택값을읽는비용자체는남을수있지만전체행JSON직렬화/2.46MB전송/브라우저parse반복은줄어든다. 별도storedsummary/새상태기계를먼저만들지않는다. rowlimit/tenant/status필터와삭제제외/정렬의미는유지한다. 필요하면후속실제측정으로projection시간·bytes·incident/result칩·상세원문불변을확인하고그후에도DBquery가느리면실제ANALYZE/IOwait기준으로index를논의한다.

이번조사는소스/GET1회/EXPLAIN읽기뿐이며제품·schema·DB쓰기·network설정·worker·모델변경0이다. 최초nativeleftlisttimeout화면과현재GET성공을시간대별사실로유지한다. root의DBIO/리소스관찰과합쳐원인을정리해야한다. ProcessGPT의목록요약/상세본문분리라는참고방향과같지만특정참고제품이이번HYDDBplan을검증했다는주장은하지않는다.
