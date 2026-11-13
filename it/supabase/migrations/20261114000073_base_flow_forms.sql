-- 기준 흐름 2.4 의 폼을 폼 표에 맞춘다 (2026-11-14)
--
-- 기준 흐름 「설비 이상 조치」(it/process/definitions/anomaly_response_v22.json)가 2.4 로 올라가며 폼 둘이 바뀌었다.
--   diagnose     원인 · 고장 유형 칸의 설명에 있던 예시 값이 시나리오 A 의 정답 id(쿨러 핀 오염 원인과 그 고장 유형)였다. AI 가 진단 없이
--                예시를 옮겨 적을 수 있어, 값의 꼴과 출처(진단 도구가 돌려준 값 그대로)만 적는다.
--   select_card  운전원이 조치 카드를 거절할 수 있다. 거절에는 고른 조치가 없으므로 조치 칸 둘은 선택 칸이 되고, 승인 / 반려 칸과 사유 칸이 생겼다.
--                조치 종류 목록도 정의와 같은 넷(즉시 제어 · 작업지시만 · 발주만 · 실행할 조치 없음)으로 맞춘다(전에는 둘만 있었다).
--
-- 흐름의 단계는 자기 정의 판본 안의 폼을 쓰므로(2.3 으로 진행 중인 처리 건은 2.3 의 폼 그대로다) 이 표는 정의에 묶이지 않은 작업 행이
-- 폼 이름으로 찾을 때만 읽힌다. seed.sql 은 새로 만든 DB 에만 들어가므로, 이미 쓰던 DB 의 두 행을 여기서 seed.sql 과 같은 내용으로 바꾼다.
-- 새로 만든 DB 에서는 이 파일이 시드보다 먼저 돈다(행이 아직 없다) — 그때는 아무것도 바뀌지 않고 seed.sql 이 같은 내용을 넣는다.

update public.form_def set fields_json = '[{"key":"cause","text":"판정한 원인 노드 id (cause:… 꼴 — hyd-dmn diagnose 가 돌려준 top_cause 그대로)","type":"text"},{"key":"failure_mode","text":"고장 유형 노드 id (fm:… 꼴 — hyd-dmn diagnose 가 돌려준 failure_mode 그대로)","type":"text"},{"key":"guide_card","text":"hyd-dmn diagnose 도구가 돌려준 가이드 카드 객체 그대로 (alert · causes · recommended · skills · citations · summary)","type":"object"}]'
 where tenant_id = 'hyd' and id = 'diagnose';

update public.form_def set fields_json = '[{"key":"chosen_skill","text":"승인한 스킬(SOP) id — 거절하면 비운다","type":"text","required":false},{"key":"chosen_skill_kind","text":"승인한 카드의 조치 종류 — 거절하면 비운다","type":"select","items":[{"control":"즉시 제어"},{"work_order":"작업지시만"},{"purchase":"발주만"},{"other":"실행할 조치 없음"}],"required":false},{"key":"approval","text":"승인 / 반려","type":"select","items":["승인","반려"]},{"key":"approval_reason","text":"사유","type":"textarea","required":false}]'
 where tenant_id = 'hyd' and id = 'select_card';
