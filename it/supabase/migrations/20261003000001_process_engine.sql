-- ============================================================================
-- 프로세스 엔진 테이블 — ProcessGPT 제품 DB 와 같은 모양.
--
-- 원본: process-gpt/docker-infra/volumes/db/init.sql (enum L68~112 · proc_def L273~321 · bpm_proc_inst L361~387 ·
--       todolist L389~430 · events L651~662), process-gpt-agent-sdk/processgpt_agent_sdk/function.sql (fetch_pending_task ·
--       save_task_result · record_events_bulk · fetch_context_bundle). 열 이름·enum 값은 제품 그대로다.
--
-- 교육 요점 — 상태 흐름은 제품과 같다 (docs/handoff/REPO_GAP.md §1):
--   인스턴스 시작      닿을 수 있는 모든 활동을 TODO 로 미리 만든다 (예정 업무). 첫 활동은 IN_PROGRESS.
--   사람 작업          IN_PROGRESS (내 할일) → 폼 제출 → SUBMITTED → 엔진이 다음 작업을 만들고 DONE
--   에이전트 작업      IN_PROGRESS + agent_mode=COMPLETE → 워커가 fetch_pending_task 로 집음(draft_status STARTED)
--                      → save_task_result(final) → SUBMITTED → 엔진이 DONE
--   서비스 작업        닿는 즉시 SUBMITTED → 엔진(process 서비스)이 실행 → DONE
--   안 간 가지·바운더리 대안   CANCELLED      조건 미충족   PENDING (log 에 사유)
-- HYD 확장 열은 주석에 [HYD] 로 표시했다. 단일 테넌트 'hyd' 라 tenant_id 기본값을 둔다 (제품은 JWT 의 tenant_id()).
-- ============================================================================

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------- enums (제품 값 그대로)
do $$ begin
  if not exists (select 1 from pg_type where typname = 'process_status') then
    create type public.process_status as enum ('NEW', 'RUNNING', 'COMPLETED');
  end if;
  if not exists (select 1 from pg_type where typname = 'todo_status') then
    create type public.todo_status as enum ('NEW', 'TODO', 'IN_PROGRESS', 'SUBMITTED', 'PENDING', 'DONE', 'CANCELLED');
  end if;
  if not exists (select 1 from pg_type where typname = 'agent_mode') then
    create type public.agent_mode as enum ('DRAFT', 'COMPLETE');
  end if;
  if not exists (select 1 from pg_type where typname = 'draft_status') then
    create type public.draft_status as enum ('STARTED', 'CANCELLED', 'COMPLETED', 'FB_REQUESTED', 'HUMAN_ASKED', 'FAILED');
  end if;
  if not exists (select 1 from pg_type where typname = 'event_type_enum') then
    create type public.event_type_enum as enum ('task_started', 'task_completed', 'tool_usage_started', 'tool_usage_finished',
      'crew_completed', 'human_asked', 'human_response', 'human_checked', 'task_working', 'error', 'waiting_for_user',
      'task_cancelled', 'human_feedback_submitted');
  end if;
  if not exists (select 1 from pg_type where typname = 'event_status') then
    create type public.event_status as enum ('ASKED', 'APPROVED', 'REJECTED');
  end if;
end $$;

-- ---------------------------------------------------------------- tenants · users (제품 users: 사람과 에이전트가 한 테이블, is_agent 로 구분)
create table if not exists public.tenants (
  id text primary key,
  name text,
  owner text,
  mcp jsonb,                                            -- 테넌트가 등록한 MCP 서버 {"mcpServers": {name: {command,args,env} | {type:url,url,transport}}}
  created_at timestamptz not null default now()
);

create table if not exists public.users (
  id text primary key,                                  -- 사람: role:operator … / 에이전트: sys:agent … (온톨로지 id 와 같다)
  email text,
  username text,
  role text,
  is_admin boolean not null default false,
  is_agent boolean not null default false,
  agent_type text,                                      -- agent | pgagent (제품) | system [HYD: SCADA·프로세스·CMMS 같은 시스템 수행자]
  alias text,
  goal text,
  persona text,
  model text,
  endpoint text,
  tools text,
  department_id text,
  is_draft boolean not null default false,
  tenant_id text not null default 'hyd' references public.tenants(id) on update cascade on delete cascade,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------- proc_def · proc_def_version · form_def
create table if not exists public.proc_def (
  id text not null,                                     -- processDefinitionId (anomaly_response)
  name text,
  definition jsonb,                                     -- it/process/definitions/*.json 원문
  bpmn text,
  prod_version text,
  uuid uuid not null default gen_random_uuid(),
  tenant_id text not null default 'hyd' references public.tenants(id) on update cascade on delete cascade,
  isdeleted boolean not null default false,
  owner text,
  agent_id text,
  type text default 'bpmn',                             -- bpmn | dmn
  is_draft boolean not null default false,
  ontology_ref text,                                    -- [HYD] 온톨로지 Process 노드 id (proc:anomaly-response)
  updated_at timestamptz not null default now(),
  constraint proc_def_pkey primary key (uuid)
);
create unique index if not exists ux_proc_def_id_tenant on public.proc_def (id, tenant_id) where isdeleted = false;

create table if not exists public.proc_def_version (
  arcv_id text not null,                                -- '{proc_def_id}_{version}'
  proc_def_id text not null,
  version text not null,
  version_tag text,
  snapshot text,
  definition jsonb,
  "timeStamp" timestamp without time zone default current_timestamp,
  diff text,
  message text,
  uuid uuid not null default gen_random_uuid(),
  tenant_id text not null default 'hyd' references public.tenants(id) on update cascade on delete cascade,
  parent_version text,
  source_todolist_id uuid,
  is_draft boolean not null default false,
  constraint proc_def_version_pkey primary key (uuid)
);

create table if not exists public.form_def (
  id text not null,                                     -- tool 'formHandler:<id>' 의 <id>
  tenant_id text not null default 'hyd' references public.tenants(id) on update cascade on delete cascade,
  proc_def_id text,
  activity_id text,
  fields_json jsonb,                                    -- [{key, type, text, items?}] — 에이전트의 결과 제출 계약 · 사람의 입력 폼
  html text,
  uuid uuid not null default gen_random_uuid(),
  constraint form_def_pkey primary key (uuid)
);
create unique index if not exists ux_form_def_id_tenant on public.form_def (id, tenant_id);

-- ---------------------------------------------------------------- bpm_proc_inst (프로세스 인스턴스)
create table if not exists public.bpm_proc_inst (
  proc_def_id text,
  proc_inst_id text not null,                           -- '{proc_def_id}.{uuid}'
  proc_inst_name text,
  root_proc_inst_id text,
  parent_proc_inst_id text,
  execution_scope text,
  current_activity_ids text[],
  participants text[],                                  -- 참여한 user_id 들 (todolist 에서 모음)
  role_bindings jsonb,                                  -- [{name, endpoint, resolutionRule}]
  variables_data jsonb,                                 -- [{key, name, value}] (제품 모양)
  status public.process_status,
  tenant_id text not null default 'hyd' references public.tenants(id) on update cascade on delete cascade,
  proc_def_version text,
  version_tag text,
  version text,
  project_id uuid,
  start_date timestamp without time zone,
  end_date timestamp without time zone,
  due_date timestamp without time zone,
  updated_at timestamptz default now(),
  is_deleted boolean not null default false,
  deleted_at timestamptz,
  is_clean_up boolean not null default false,
  end_event text,                                       -- [HYD] 종료 이벤트 id (ev:closed | ev:escalated)
  constraint bpm_proc_inst_pkey primary key (proc_inst_id)
);
create index if not exists ix_proc_inst_status on public.bpm_proc_inst (tenant_id, status, start_date desc);

-- ---------------------------------------------------------------- todolist (= 워크아이템 한 줄 = 작업 하나)
create table if not exists public.todolist (
  id uuid not null default gen_random_uuid(),
  user_id text,                                         -- 수행자 user id (쉼표 구분 가능). 사람 role:operator / 에이전트 sys:agent / 시스템 sys:scada …
  username text,
  proc_inst_id text references public.bpm_proc_inst(proc_inst_id) on delete cascade,
  root_proc_inst_id text,
  execution_scope text,
  proc_def_id text,
  version_tag text,
  version text,
  activity_id text,
  activity_name text,
  start_date timestamp without time zone,
  end_date timestamp without time zone,
  status public.todo_status,
  description text,
  tool text,                                            -- formHandler:<form_id> (사람·에이전트 폼) | hyd-dmn:… | incident:… | enterprise:…
  due_date timestamp without time zone,
  tenant_id text not null default 'hyd' references public.tenants(id) on update cascade on delete cascade,
  reference_ids text[],
  adhoc boolean default false,
  assignees jsonb,                                      -- 이 활동 역할의 role binding [{name, endpoint, resolutionRule}]
  duration integer,
  output jsonb,                                         -- 제출된 결과 (폼 값 · 에이전트 JSON · 서비스 tool_results)
  retry integer default 0,
  consumer text,                                        -- 지금 이 행을 처리 중인 워커/엔진 (pod · host:pid)
  log text,
  project_id uuid,
  draft jsonb,                                          -- agent_mode=DRAFT 의 초안 (사람 검토 뒤 제출)
  agent_mode public.agent_mode,                         -- NULL = 사람이 한다 · COMPLETE = 에이전트가 끝까지 · DRAFT = 에이전트 초안 + 사람 제출
  agent_orch text,                                      -- 어느 워커가 집는가: cliagents | hyd-process(서비스) | NULL
  feedback jsonb,
  draft_status public.draft_status,                     -- 워커 진행: STARTED → COMPLETED | FAILED | HUMAN_ASKED | CANCELLED | FB_REQUESTED
  updated_at timestamptz default now(),
  temp_feedback text,
  output_url text,
  rework_count integer default 0,
  query text,                                           -- 에이전트에게 주는 지시문 ([Description] [Instruction] [InputData])
  feedback_status text,
  gateway_decisions jsonb,                              -- 이 작업 뒤 게이트웨이 판정 {gw: {selected:[seq], sequences:{seq:{target, condition, eval, reason}}}}
  constraint todolist_pkey primary key (id)
);
create index if not exists idx_todolist_inprog on public.todolist (agent_orch, tenant_id, start_date) where status = 'IN_PROGRESS';
create index if not exists idx_todolist_submitted on public.todolist (tenant_id, start_date) where status = 'SUBMITTED';
create index if not exists idx_todolist_procinst on public.todolist (proc_inst_id);
create index if not exists ix_todolist_user on public.todolist (tenant_id, user_id, status);

create or replace function public.update_updated_at_column() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;
drop trigger if exists set_updated_at on public.todolist;
create trigger set_updated_at before update on public.todolist for each row execute function public.update_updated_at_column();
drop trigger if exists trg_proc_inst_updated on public.bpm_proc_inst;
create trigger trg_proc_inst_updated before update on public.bpm_proc_inst for each row execute function public.update_updated_at_column();

create or replace function public.update_bpm_proc_inst_updated_at() returns trigger language plpgsql as $$
begin
  if new.proc_inst_id is not null then
    update public.bpm_proc_inst set updated_at = now() where proc_inst_id = new.proc_inst_id;
  end if;
  return new;
end $$;
drop trigger if exists trigger_update_bpm_proc_inst_updated_at on public.todolist;
create trigger trigger_update_bpm_proc_inst_updated_at after update on public.todolist for each row execute function public.update_bpm_proc_inst_updated_at();

-- ---------------------------------------------------------------- events (에이전트 실행 이벤트 스트림) · notifications · proc_inst_source
create table if not exists public.events (
  id text not null,
  job_id text not null,                                 -- 실행 단위 id (워커 run / human_asked_<uuid> / TASK_ERROR)
  todo_id text,
  proc_inst_id text,
  event_type public.event_type_enum not null,
  status public.event_status,
  crew_type text,                                       -- result | agent | tool | … (화면이 카드 모양을 고르는 기준)
  data jsonb not null,
  timestamp timestamptz default now(),
  constraint events_pkey primary key (id)
);
create index if not exists ix_events_todo on public.events (todo_id, timestamp);
create index if not exists ix_events_inst on public.events (proc_inst_id, timestamp);

create table if not exists public.notifications (
  id uuid not null default gen_random_uuid(),
  title text,
  type text,                                            -- workitem_bpm …
  description text,
  user_id text,
  tenant_id text not null default 'hyd' references public.tenants(id) on update cascade on delete cascade,
  url text,                                             -- /todolist/<id>
  from_user_id text,
  is_read boolean not null default false,
  created_at timestamptz not null default now(),
  constraint notifications_pkey primary key (id)
);

create table if not exists public.proc_inst_source (
  id uuid not null default gen_random_uuid(),
  proc_inst_id text,
  file_name text,
  file_path text,
  tenant_id text not null default 'hyd' references public.tenants(id) on update cascade on delete cascade,
  constraint proc_inst_source_pkey primary key (id)
);

-- ============================================================================
-- RPC — 에이전트 워커 쪽 (process-gpt-agent-sdk function.sql 그대로)
-- ============================================================================
drop function if exists public.fetch_pending_task(text, text, integer, text);
create or replace function public.fetch_pending_task(p_agent_orch text, p_consumer text, p_limit integer, p_env text)
returns setof public.todolist
language plpgsql
volatile
as $$
begin
  return query
    with cte as (
      select t.id
      from public.todolist as t
      where t.status = 'IN_PROGRESS'
        and (p_agent_orch is null or p_agent_orch = '' or t.agent_orch::text = p_agent_orch)
        and (
          (t.agent_mode in ('DRAFT', 'COMPLETE') and t.draft is null and t.draft_status is null)
          or t.draft_status = 'FB_REQUESTED'
        )
      order by t.start_date
      limit p_limit
      for update skip locked
    ),
    upd as (
      update public.todolist as t
         set draft_status = 'STARTED',
             consumer     = p_consumer
        from cte
       where t.id = cte.id
       returning t.*
    )
    select * from upd;
end;
$$;

drop function if exists public.save_task_result(uuid, jsonb, boolean);
create or replace function public.save_task_result(p_todo_id uuid, p_payload jsonb, p_final boolean)
returns void language plpgsql volatile as $$
declare v_mode text;
begin
  select agent_mode into v_mode from public.todolist where id = p_todo_id;
  if p_final then
    if v_mode = 'COMPLETE' then
      update public.todolist
         set output = p_payload, status = 'SUBMITTED', draft_status = 'COMPLETED', consumer = null
       where id = p_todo_id;
    else
      update public.todolist
         set draft = p_payload, draft_status = 'COMPLETED', consumer = null
       where id = p_todo_id;
    end if;
  else
    update public.todolist set draft = p_payload where id = p_todo_id;
  end if;
end;
$$;

drop function if exists public.record_events_bulk(jsonb);
create or replace function public.record_events_bulk(p_events jsonb)
returns void language plpgsql volatile as $$
begin
  insert into public.events (id, job_id, todo_id, proc_inst_id, crew_type, event_type, data, status)
  select coalesce(e->>'id', gen_random_uuid()::text),
         e->>'job_id',
         e->>'todo_id',
         e->>'proc_inst_id',
         e->>'crew_type',
         (e->>'event_type')::public.event_type_enum,
         coalesce(e->'data', '{}'::jsonb),
         nullif(e->>'status', '')::public.event_status
    from jsonb_array_elements(coalesce(p_events, '[]'::jsonb)) as e;
end;
$$;

drop function if exists public.fetch_context_bundle(text, text, text, text);
create or replace function public.fetch_context_bundle(p_proc_inst_id text, p_tenant_id text, p_tool text, p_user_ids text)
returns table (notify_emails text, tenant_mcp jsonb, form_id text, form_fields jsonb, form_html text, agents jsonb)
language plpgsql volatile as $$
declare v_form_id text;
begin
  select string_agg(u.email, ',') into notify_emails
    from public.todolist t
    join public.users u on u.id = any(string_to_array(t.user_id, ','))
   where t.proc_inst_id = p_proc_inst_id and (u.is_agent is null or u.is_agent = false);

  select mcp into tenant_mcp from public.tenants where id = p_tenant_id;

  v_form_id := case when p_tool like 'formHandler:%' then substring(p_tool from 13) else p_tool end;
  select v_form_id,
         coalesce(fd.fields_json, jsonb_build_array(jsonb_build_object('key', v_form_id, 'type', 'default', 'text', ''))),
         fd.html
    into form_id, form_fields, form_html
    from public.form_def fd
   where fd.id = v_form_id and fd.tenant_id = p_tenant_id;
  if form_id is null then
    form_id := v_form_id;
    form_fields := jsonb_build_array(jsonb_build_object('key', coalesce(v_form_id, 'freeform'), 'type', 'default', 'text', ''));
  end if;

  with want_ids as (select unnest(string_to_array(coalesce(p_user_ids, ''), ',')) as idtxt)
  select jsonb_agg(to_jsonb(u)) into agents
    from public.users u
   where u.is_agent = true
     and ((select count(*) from want_ids where idtxt <> '') = 0 or u.id in (select idtxt from want_ids));
  return next;
end;
$$;

-- ============================================================================
-- RPC — 엔진 쪽 (process-gpt-completion polling_service/database.py 909~1047 의 PostgREST 조건부 update 를 SQL 로)
-- ============================================================================
-- SUBMITTED 이고 consumer 가 비어 있는 행을 FOR UPDATE SKIP LOCKED 로 잠가 consumer 를 채운다 (엔진 폴링 점유).
create or replace function public.claim_submitted_workitems(p_consumer text, p_limit integer default 10)
returns setof public.todolist
language plpgsql volatile as $$
begin
  return query
    update public.todolist t
       set consumer = p_consumer
     where t.id in (
           select id from public.todolist
            where status = 'SUBMITTED' and consumer is null
            order by start_date
            limit p_limit
            for update skip locked)
    returning t.*;
end;
$$;

-- 30 분 넘게 붙잡힌 SUBMITTED 의 consumer 를 푼다 (제품 cleanup_stale_consumers).
create or replace function public.cleanup_stale_consumers(p_minutes integer default 30)
returns integer language plpgsql volatile as $$
declare n integer;
begin
  update public.todolist
     set consumer = null
   where status = 'SUBMITTED' and consumer is not null and updated_at < now() - make_interval(mins => p_minutes);
  get diagnostics n = row_count;
  return n;
end;
$$;

-- ---------------------------------------------------------------- 권한 · RLS (교육 환경: 단일 테넌트, 허용 정책을 명시해 두고 멀티테넌트 때 정책만 바꾼다)
do $$ declare t text; begin
  foreach t in array array['tenants', 'users', 'proc_def', 'proc_def_version', 'form_def', 'bpm_proc_inst', 'todolist', 'events', 'notifications', 'proc_inst_source'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists %I on public.%I', t || '_read_all', t);
    execute format('create policy %I on public.%I for select to anon, authenticated using (true)', t || '_read_all', t);
    execute format('drop policy if exists %I on public.%I', t || '_write_authenticated', t);
    execute format('create policy %I on public.%I for all to authenticated using (true) with check (true)', t || '_write_authenticated', t);
  end loop;
end $$;
grant usage on schema public to anon, authenticated, service_role;
grant select on all tables in schema public to anon;
grant all on all tables in schema public to authenticated, service_role;
grant execute on all functions in schema public to anon, authenticated, service_role;
