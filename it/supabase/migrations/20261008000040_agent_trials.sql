-- A10 (TODO 확정 2026-10-08): 에이전트 시험 실행 · 비교. 처리 건(bpm_proc_inst) · 작업(todolist) · 판단 · 명령과 무관한 시험 기록 두 표.
-- agent_trial_snapshots: 고정 시나리오의 입력 스냅숏(record/replay). 판단이 읽은 원천 값(진단 · 사실 · 판단 엔진 입력 · 스킬 보조 도구)을
--   호출 키 → {kind, observed_at, ok, value|error} 로 담는다. 한 번 기록한 키는 바꾸지 않는다(같은 입력 보장) — 새 키만 덧붙는다.
-- agent_trials: 에이전트 하나 × 스냅숏 하나의 시험 결과(도구 호출 순서 · 입력 · 결과 요약 · 원인 · 후보 · 규정 · 순위 · 근거).
--   setting = 그때 쓴 에이전트 설정(users · 스킬 저장소에서 읽은 값 − 비교용 변형), fingerprint = 결과 해시(같은 입력 + 같은 설정 → 같은 값).
create table if not exists public.agent_trial_snapshots (
  id text primary key,
  tenant_id text not null default 'hyd' references public.tenants(id) on update cascade on delete cascade,
  asset text not null,
  pattern text not null,
  entries jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists ix_agent_trial_snapshots_scenario on public.agent_trial_snapshots (tenant_id, asset, pattern, created_at desc);

create table if not exists public.agent_trials (
  id text primary key,
  tenant_id text not null default 'hyd' references public.tenants(id) on update cascade on delete cascade,
  snapshot_id text not null references public.agent_trial_snapshots(id) on delete cascade,
  asset text not null,
  pattern text not null,
  agent_id text,                                         -- users.id (FK 없음: 에이전트를 지워도 지난 시험 기록은 읽힌다)
  setting jsonb not null,
  variant jsonb not null default '{}'::jsonb,
  status text not null,
  fingerprint text not null,
  result jsonb not null,
  created_at timestamptz not null default now()
);
create index if not exists ix_agent_trials_recent on public.agent_trials (tenant_id, created_at desc);
comment on table public.agent_trials is 'A10: 에이전트 시험 실행(드라이런) 결과. 처리 건 · 판단 제출 · 설비 명령을 만들지 않는다';

-- 권한 · RLS: migration 000001 과 같은 교육 환경 정책(읽기 전체 허용 · 쓰기 authenticated). process 서비스는 소유자 연결로 쓴다.
do $$ declare t text; begin
  foreach t in array array['agent_trial_snapshots', 'agent_trials'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists %I on public.%I', t || '_read_all', t);
    execute format('create policy %I on public.%I for select to anon, authenticated using (true)', t || '_read_all', t);
    execute format('drop policy if exists %I on public.%I', t || '_write_authenticated', t);
    execute format('create policy %I on public.%I for all to authenticated using (true) with check (true)', t || '_write_authenticated', t);
  end loop;
end $$;
grant select on public.agent_trial_snapshots, public.agent_trials to anon;
grant all on public.agent_trial_snapshots, public.agent_trials to authenticated, service_role;
