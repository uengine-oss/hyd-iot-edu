-- U2 (TODO A2, 2026-10-08): 에이전트 스킬 저장소. 포털은 읽기만 하고, 수강생은 랩업(Claude Code)에서 SQL 로 넣는다.
-- 원천 하나: 스킬 본문 = tenant_skills.content (SKILL.md 원문), 에이전트에 붙이기 = agent_skills 행.
-- 에이전트 프로필(목표·성격·모델·도구)은 기존 public.users 칸(migration 000001) 그대로다.
-- 제품 모양: agent_skills(user_id, tenant_id, skill_name) = process-gpt-vue3 ProcessGPTBackend.ts:4389-4407 replaceAgentSkills,
--           tenant_skills(tenant_id, skill_name) = deepagents core/skills/tools.py:702-716.
-- HYD 차이: 제품은 SKILL.md 파일을 스킬 저장소(디스크·Git)에 두고 tenant_skills 에 이름만 둔다. HYD 는 본문을 content 에 둬서
--           포털(process)과 워커가 같은 행을 읽는다. 워커는 실행마다 작업 폴더 .claude/skills/<이름>/SKILL.md 로 쓴다.
-- 사용법·예시: docs/handoff/verification/2026-10-08/u2-agents-skills.md

create table if not exists public.tenant_skills (
  tenant_id text not null references public.tenants(id) on update cascade on delete cascade,
  skill_name text not null,                             -- Claude Code 스킬 폴더 이름: 소문자·숫자·하이픈
  description text not null default '',                 -- 한 줄 설명(목록·에이전트 지시문에 보임)
  content text not null default '',                     -- SKILL.md 원문(프런트매터 있어도 되고 없어도 된다)
  owner_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, skill_name),
  constraint tenant_skills_name_shape check (skill_name ~ '^[a-z0-9][a-z0-9-]{0,63}$')
);
comment on table public.tenant_skills is 'U2: 에이전트 스킬(SKILL.md). 포털 "AI 에이전트 › 스킬"이 읽고, 워커가 붙은 에이전트의 실행 작업 폴더에 쓴다';

create table if not exists public.agent_skills (
  user_id text not null references public.users(id) on update cascade on delete cascade,
  tenant_id text not null references public.tenants(id) on update cascade on delete cascade,
  skill_name text not null,
  created_at timestamptz not null default now(),
  primary key (user_id, tenant_id, skill_name),
  foreign key (tenant_id, skill_name) references public.tenant_skills(tenant_id, skill_name) on update cascade on delete cascade
);
comment on table public.agent_skills is 'U2: 에이전트(users.id)에 붙인 스킬. 없는 스킬은 붙일 수 없다(외래 키)';

-- 권한 · RLS: migration 000001 과 같은 교육 환경 정책(읽기 전체 허용 · 쓰기 authenticated)
do $$ declare t text; begin
  foreach t in array array['tenant_skills', 'agent_skills'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists %I on public.%I', t || '_read_all', t);
    execute format('create policy %I on public.%I for select to anon, authenticated using (true)', t || '_read_all', t);
    execute format('drop policy if exists %I on public.%I', t || '_write_authenticated', t);
    execute format('create policy %I on public.%I for all to authenticated using (true) with check (true)', t || '_write_authenticated', t);
  end loop;
end $$;
grant select on public.tenant_skills, public.agent_skills to anon;
grant all on public.tenant_skills, public.agent_skills to authenticated, service_role;
