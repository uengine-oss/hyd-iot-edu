-- G9 (전체 과정 랩업 — capstone-lab.md 5.2): 에이전트 작업 규칙의 업무부를 고르는 칸.
-- 워커가 작업 폴더에 넣는 고정 규칙(CLAUDE.md) = 공통부 + 업무부(procsvc/work_rules.py). 이 칸이 업무부 키다('hyd-plant' = HYD 설비).
-- 비어 있으면 공통부만 넣고 처리 기록에 그 사실을 남긴다. 모르는 키는 워커가 실행을 사유와 함께 실패시킨다(키 목록은 코드가 소유 — 여기서 제약하지 않음).
-- 기준 에이전트 값은 seed.sql 이 넣는다. 복제 · 구성 내보내기 · 가져오기는 이 칸을 함께 옮긴다(agent_authoring · config_bundle).
alter table public.users add column if not exists work_rules text;
comment on column public.users.work_rules is 'G9: 에이전트 작업 규칙 업무부 키 (procsvc/work_rules.py RULES). null = 공통부만';
-- 이미 시드된 DB(마이그레이션만 올리는 라이브 스택): 기준 에이전트 넷을 지금 받던 글(HYD 설비)에 그대로 둔다. 새 DB 에서는 아직 행이 없어
-- 아무것도 바꾸지 않고, 뒤이은 seed.sql 이 같은 값을 넣는다. 사람이 이미 고친 값(null 이 아닌 것)은 건드리지 않는다.
update public.users set work_rules = 'hyd-plant'
 where tenant_id = 'hyd' and id in ('sys:agent', 'agent:cooling', 'agent:pm-plan', 'agent:spare-buy') and work_rules is null;
