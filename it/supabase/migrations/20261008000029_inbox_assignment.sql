-- U5 (mini ProcessGPT TODO 5, 2026-10-08): 역할 → 사람 업무분장 · 작업 담당자 변경 이력 · 알림 조회 인덱스.
-- HYD 에는 로그인이 없고 작업의 user_id 는 정의의 역할 바인딩(role:operator …)이다(procsvc/engine.py new_workitem).
-- vue3 의 /work-assignment(역할별 담당자)·delegation_history(위임 이력)·notifications(받은 함) 에 해당하는 최소 구조:
--   role_members      역할에 속한 사람(업무분장). 역할에 사람이 한 명이면 그 사람에게 바로 배정, 여럿이면 역할 공용으로 남긴다(procsvc/inbox.py).
--   task_assignments  작업(todolist) 담당자 해석 이력 — 업무분장으로 사람에게 바로 배정된 것(auto). 수동 재배정·위임은 범위 밖(TODO A3).
--                     todo_id 에는 FK 를 걸지 않는다: 단계가 열릴 때 배정은 작업 행이 저장되기 전(같은 전이 안)에 쓰인다. 지울 때는 처리 건 FK 로 함께 지운다.
--   notifications     기존 표. 사용자별 안 읽은 알림 조회 인덱스만 더한다.

create table if not exists public.role_members (
  tenant_id text not null default 'hyd' references public.tenants(id) on update cascade on delete cascade,
  role_id text not null references public.users(id) on update cascade on delete cascade,     -- 온톨로지 Role id = users.id (role:operator …)
  user_id text not null references public.users(id) on update cascade on delete cascade,     -- 사람 user:*
  created_at timestamptz not null default now(),
  constraint role_members_pkey primary key (tenant_id, role_id, user_id)
);

create table if not exists public.task_assignments (
  id uuid not null default gen_random_uuid(),
  tenant_id text not null default 'hyd' references public.tenants(id) on update cascade on delete cascade,
  proc_inst_id text not null references public.bpm_proc_inst(proc_inst_id) on delete cascade,
  todo_id uuid not null,
  from_user_id text,                                   -- 이전 담당(역할 id 또는 사람 id)
  to_user_id text not null,
  kind text not null check (kind in ('auto')),
  by_user text,                                        -- 바꾼 사람
  reason text,
  created_at timestamptz not null default now(),
  constraint task_assignments_pkey primary key (id)
);
create index if not exists ix_task_assignments_todo on public.task_assignments (todo_id, created_at);

create index if not exists ix_notifications_user_unread on public.notifications (tenant_id, user_id, is_read, created_at desc);
create index if not exists ix_notifications_created on public.notifications (created_at, id);

-- 사람 사용자(user:*)와 업무분장은 seed.sql 에 있다(테넌트·역할 사용자가 seed 에서 만들어지므로 마이그레이션은 구조만).

do $$ declare t text; begin
  foreach t in array array['role_members', 'task_assignments'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists %I on public.%I', t || '_read_all', t);
    execute format('create policy %I on public.%I for select to anon, authenticated using (true)', t || '_read_all', t);
    execute format('drop policy if exists %I on public.%I', t || '_write_authenticated', t);
    execute format('create policy %I on public.%I for all to authenticated using (true) with check (true)', t || '_write_authenticated', t);
  end loop;
end $$;
grant select on public.role_members, public.task_assignments to anon;
grant all on public.role_members, public.task_assignments to authenticated, service_role;
