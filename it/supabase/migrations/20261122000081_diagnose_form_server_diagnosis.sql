-- 기준 흐름 2.7 의 진단 폼을 폼 표에 맞춘다 (2026-11-22)
--
-- 처리 건의 원인 진단 · 사건 카드는 AI 가 결과 칸에 옮겨 적은 가이드 카드(guide_card)가 아니라 판단을 등록할 때 판단 엔진이 다시 한 진단(판단 기록
-- origin.diagnosis)이 됐다(procsvc/instances.py incident_card). 결과의 원인 · 고장 유형은 등록한 판단의 원인과 같아야 한다(decision_cause_gaps).
-- 기준 흐름 「설비 이상 조치」(it/process/definitions/anomaly_response_v22.json)가 2.7 로 올라가며 진단 폼 칸 셋의 설명이 그 사실대로 바뀌었다 —
-- 전에는 guide_card 칸이 그 카드에 없는 칸(recommended)까지 적었고, 그 카드가 무엇으로 쓰이는지 말하지 않았다.
--
-- 흐름의 단계는 자기 정의 판본 안의 폼을 쓰므로 이 표는 정의에 묶이지 않은 작업 행이 폼 이름으로 찾을 때만 읽힌다. seed.sql 은 새로 만든 DB 에만
-- 들어가므로, 이미 쓰던 DB 의 진단 폼 행을 여기서 seed.sql 과 같은 내용으로 바꾼다(073 과 같은 길). 새로 만든 DB 에서는 이 파일이 시드보다 먼저
-- 돈다(행이 아직 없다) — 그때는 아무것도 바뀌지 않고 seed.sql 이 같은 내용을 넣는다.

update public.form_def set fields_json = '[{"key":"cause","text":"판정한 원인 노드 id (cause:… 꼴 — hyd-dmn diagnose 가 돌려준 top_cause 그대로. 판단을 등록할 때 쓴 원인과 다르면 결과를 받지 않는다)","type":"text"},{"key":"failure_mode","text":"고장 유형 노드 id (fm:… 꼴 — hyd-dmn diagnose 가 돌려준 failure_mode 그대로. 판단을 등록할 때 쓴 고장 유형과 다르면 결과를 받지 않는다)","type":"text"},{"key":"guide_card","text":"hyd-dmn diagnose 도구가 돌려준 card 객체 그대로 — 기록으로만 남는다. 처리 건의 원인 진단은 판단을 등록할 때(submit_decision) 판단 엔진이 다시 한 진단이다","type":"object"}]'
 where tenant_id = 'hyd' and id = 'diagnose';
