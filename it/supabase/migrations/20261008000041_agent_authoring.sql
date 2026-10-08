-- B1 (확정 TODO B, DECISIONS 110 ①, 2026-10-08): 포털에서 에이전트 · 스킬 만들기 · 고치기 · 붙이기, 역할 → 사람 · 단계 → 에이전트 배정, 되돌리기.
-- 기준 보호: 시드(기본) 행은 origin='seed'(기본값) — 포털 API 는 고치기 · 지우기를 사유와 함께 거절하고 "복제해서 고치기"만 허용한다.
--           포털에서 만든 행은 origin='user' — "기준으로 되돌리기"(POST /api/agents/reset)가 이것만 지운다.
--           seed.sql 은 마이그레이션 뒤에 들어가므로 기본값 'seed' 로 표시된다(시드 변경 없음).
--           랩업 SQL 로 넣은 행도 origin 을 적지 않으면 'seed'(보호)다 — 포털에서 고치려면 origin='user' 로 넣는다.
-- 단계 → 에이전트: 정의(BPMN)의 activity 수행자를 바꾸지 않는다. activity_agent_map 이 (정의 id, 단계 id) → 에이전트를 두고,
--   흐름이 그 단계에 닿을 때(procsvc/inbox.apply_advance → agent_authoring.apply_agent_map) 작업 행의 user_id 를 그 에이전트로 쓴다.
--   워커는 작업 행의 user_id 로 프로필 · 스킬 · 모델 · 도구를 읽으므로(agent-worker context.prepare → agents_store.agent_settings)
--   배정이 곧 실행 담당이다. 배정을 지우면 다음에 열리는 단계는 정의의 역할 담당(sys:agent)으로 돌아간다.
--   배정이 적용된 기록은 task_assignments(kind='agent_map')에 남는다.
-- 원본: process-gpt-vue3 ProcessGPTBackend.ts:4250-4306 putAgent · deleteAgent, :4393-4441 replaceAgentSkills · deleteAgentSkill,
--       AgentSelectField.vue (단계의 에이전트 고르기 — 제품은 정의 activity 에 직접 쓴다), /work-assignment(WorkAssignment.vue).

alter table public.users add column if not exists origin text not null default 'seed';
alter table public.users add column if not exists updated_at timestamptz;
do $$ begin
  if not exists (select 1 from pg_constraint where conname = 'users_origin_check') then
    alter table public.users add constraint users_origin_check check (origin in ('seed', 'user'));
  end if;
end $$;

alter table public.tenant_skills add column if not exists origin text not null default 'seed';
do $$ begin
  if not exists (select 1 from pg_constraint where conname = 'tenant_skills_origin_check') then
    alter table public.tenant_skills add constraint tenant_skills_origin_check check (origin in ('seed', 'user'));
  end if;
end $$;

alter table public.role_members add column if not exists origin text not null default 'seed';
do $$ begin
  if not exists (select 1 from pg_constraint where conname = 'role_members_origin_check') then
    alter table public.role_members add constraint role_members_origin_check check (origin in ('seed', 'user'));
  end if;
end $$;

create table if not exists public.activity_agent_map (
  tenant_id text not null default 'hyd' references public.tenants(id) on update cascade on delete cascade,
  proc_def_id text not null,                              -- 정의 id (모든 판본에 적용 — 판본마다 단계 id 가 같다)
  activity_id text not null,                              -- 에이전트 단계 id (task:diagnose …)
  agent_id text not null references public.users(id) on update cascade on delete cascade,   -- 에이전트를 지우면 배정도 사라진다(→ 기본 담당)
  origin text not null default 'user' check (origin in ('seed', 'user')),
  by_user text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint activity_agent_map_pkey primary key (tenant_id, proc_def_id, activity_id)
);
comment on table public.activity_agent_map is 'B1: 단계 → 담당 에이전트 배정(정의 원본은 그대로). 단계가 열릴 때 작업 행 user_id 로 적용, 이력은 task_assignments(kind=agent_map)';

alter table public.task_assignments drop constraint if exists task_assignments_kind_check;
alter table public.task_assignments add constraint task_assignments_kind_check check (kind in ('auto', 'agent_map'));

do $$ begin
  execute 'alter table public.activity_agent_map enable row level security';
  execute 'drop policy if exists activity_agent_map_read_all on public.activity_agent_map';
  execute 'create policy activity_agent_map_read_all on public.activity_agent_map for select to anon, authenticated using (true)';
  execute 'drop policy if exists activity_agent_map_write_authenticated on public.activity_agent_map';
  execute 'create policy activity_agent_map_write_authenticated on public.activity_agent_map for all to authenticated using (true) with check (true)';
end $$;
grant select on public.activity_agent_map to anon;
grant all on public.activity_agent_map to authenticated, service_role;
