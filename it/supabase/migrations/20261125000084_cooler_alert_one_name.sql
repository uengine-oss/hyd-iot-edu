-- 같은 경보를 두 이름(「쿨러 과열 경보」 · 경보 패턴 이름 「쿨러 성능 저하」)으로 부르던 것을 경보 패턴의 이름 하나로 맞춘다(2026-11-25 화면 탐사:
-- 결함 시뮬레이션 · 경보별 운영 흐름 · 처리 건은 「쿨러 성능 저하」, 흐름 그림의 시작 · 에이전트 목표 · 스킬 이름은 「쿨러 과열 경보」).
-- 새 DB 는 seed.sql 이 새 이름으로 넣는다. 이미 설치된 DB 는 기본 글 그대로인 줄만 바꾼다 — 학생이 고친 목표 · 스킬 글은 건드리지 않는다.
update public.users
   set goal = '쿨러 성능 저하 경보의 원인을 진단하고' || substr(goal, length('쿨러 과열 경보의 원인을 진단하고') + 1)
 where id = 'agent:cooling' and tenant_id = 'hyd' and goal like '쿨러 과열 경보의 원인을 진단하고%';

update public.tenant_skills
   set description = '쿨러 성능 저하 경보 — 원인 진단 · 냉각 조치 제안'
 where tenant_id = 'hyd' and skill_name = 'cooling-emergency-response' and origin = 'seed' and description = '쿨러 과열 경보 — 원인 진단 · 냉각 조치 제안';

update public.tenant_skills
   set content = replace(content, '쿨러 과열 경보(COOLER_DEGRADATION) 한 건에서', '쿨러 성능 저하 경보(COOLER_DEGRADATION) 한 건에서')
 where tenant_id = 'hyd' and skill_name = 'cooling-emergency-response' and origin = 'seed' and content like '%쿨러 과열 경보(COOLER_DEGRADATION) 한 건에서%';
