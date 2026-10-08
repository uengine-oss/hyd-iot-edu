-- B3 (확정 TODO B, DECISIONS 110 ②): bpmn.io 에서 그린 .bpmn 가져오기 → task 별 부품 · 담당 매핑 → 사전 검사 → 판본 등록.
-- origin: 'user' = 수강생이 포털에서 가져와 등록한 것. 비어 있으면 기준(파일 · 시드)이다. "기준으로 되돌리기"(POST /api/flows/reset)는
--   origin='user' 인 정의 · 판본 · 초안만 지운다.
-- 그림 원본: 제품(process-gpt-vue3 putRawDefinition)과 같은 칸 — proc_def.bpmn(마지막으로 등록한 그림), proc_def_version.snapshot(판본의 그림).
-- 등록은 proc_def.prod_version · definition(운영 판본 포인터)을 움직이지 않는다 — 배포는 B4.
alter table public.proc_def add column if not exists origin text;
alter table public.proc_def_version add column if not exists origin text;
create index if not exists ix_proc_def_version_origin on public.proc_def_version (tenant_id, origin) where origin is not null;

-- 가져온 그림과 고른 매핑(초안). 같은 흐름 id 로 다시 가져오면 같은 task id 의 매핑을 유지하는 원천이다.
create table if not exists public.proc_bpmn_draft (
  tenant_id text not null default 'hyd' references public.tenants(id) on update cascade on delete cascade,
  proc_def_id text not null,
  bpmn text not null,
  file_name text,
  mapping jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  constraint proc_bpmn_draft_pkey primary key (tenant_id, proc_def_id)
);
comment on table public.proc_bpmn_draft is 'B3: 포털로 가져온 .bpmn 원본과 task 별 부품 · 담당 · 조건 매핑(등록 전 초안). 기준으로 되돌리기에서 지운다';

-- 권한 · RLS: migration 000001 과 같은 교육 환경 정책(읽기 전체 허용 · 쓰기 authenticated). process 서비스는 소유자 연결로 쓴다.
do $$ begin
  execute 'alter table public.proc_bpmn_draft enable row level security';
  execute 'drop policy if exists proc_bpmn_draft_read_all on public.proc_bpmn_draft';
  execute 'create policy proc_bpmn_draft_read_all on public.proc_bpmn_draft for select to anon, authenticated using (true)';
  execute 'drop policy if exists proc_bpmn_draft_write_authenticated on public.proc_bpmn_draft';
  execute 'create policy proc_bpmn_draft_write_authenticated on public.proc_bpmn_draft for all to authenticated using (true) with check (true)';
end $$;
grant select on public.proc_bpmn_draft to anon;
grant all on public.proc_bpmn_draft to authenticated, service_role;
