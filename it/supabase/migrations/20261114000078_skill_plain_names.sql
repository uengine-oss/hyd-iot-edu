-- 기본 제공 스킬 셋의 설명과 문서 제목에서 작업자끼리 쓰던 꼬리표를 뗀다 (2026-11-14)
--
-- 스킬의 설명과 문서 제목은 포털(AI 에이전트 › 에이전트와 스킬, 판단 실험 › 에이전트 시험 비교, 처리 건의 실행 기록)에 그대로 보인다.
-- 거기에 「(시나리오 A)」 · 「(시나리오 B)」 · 「(시나리오 C)」와 「… 카드」가 붙어 있었다 — 흐름의 이름이 아니라 만들던 사람들의 부르는 이름이다.
--   cooling-emergency-response   쿨러 과열 경보 — 원인 진단 · 냉각 조치 카드 (시나리오 A)   →  쿨러 과열 경보 — 원인 진단 · 냉각 조치 제안
--   pm-schedule-planning         정기 정비 도래 — 언제 정비할지 카드 (시나리오 B)          →  정기 정비 도래 — 정비 시점 제안
--   spare-purchase-planning      예비품 재고 기준 이탈 — 발주 카드 (시나리오 C)            →  예비품 재고 기준 이탈 — 발주안 제안
-- 문서는 첫 줄(제목)의 꼬리표만 뗀다. 본문(절차 · 결과 — AI 가 읽고 따르는 지시)은 그대로다.
--
-- 기본 제공 행(origin = 'seed')만 바꾼다. 설명은 앞 판의 글 그대로일 때만 바꾸고(고친 설명은 그대로 둔다), 제목의 꼬리표는 있으면 뗀다.
-- seed.sql 은 새로 만든 DB 에만 들어가므로 이미 쓰던 DB 를 여기서 seed.sql 과 같은 내용으로 맞춘다. 새로 만든 DB 에서는 이 파일이 시드보다
-- 먼저 돈다(행이 아직 없다) — 그때는 아무것도 바뀌지 않고 seed.sql 이 같은 내용을 넣는다.

update public.tenant_skills s
   set description = v.new_description
  from (values
        ('cooling-emergency-response', '쿨러 과열 경보 — 원인 진단 · 냉각 조치 카드 (시나리오 A)', '쿨러 과열 경보 — 원인 진단 · 냉각 조치 제안'),
        ('pm-schedule-planning',       '정기 정비 도래 — 언제 정비할지 카드 (시나리오 B)',          '정기 정비 도래 — 정비 시점 제안'),
        ('spare-purchase-planning',    '예비품 재고 기준 이탈 — 발주 카드 (시나리오 C)',            '예비품 재고 기준 이탈 — 발주안 제안')
       ) as v(skill_name, old_description, new_description)
 where s.tenant_id = 'hyd' and s.origin = 'seed' and s.skill_name = v.skill_name and s.description = v.old_description;

update public.tenant_skills
   set content = regexp_replace(content, '^(# [^\n]*?) \(시나리오 [ABC]\)(\n|$)', '\1\2')
 where tenant_id = 'hyd' and origin = 'seed'
   and skill_name in ('cooling-emergency-response', 'pm-schedule-planning', 'spare-purchase-planning')
   and content ~ '^# [^\n]*? \(시나리오 [ABC]\)(\n|$)';
