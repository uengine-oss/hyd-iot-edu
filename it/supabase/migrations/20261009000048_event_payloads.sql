-- A161-G2 (처리 기록 블랙박스 2): events 행에 다 담지 못한 도구 결과 원문.
-- 워커는 도구 결과를 events.data.output 에 미리보기(4,000자)로만 싣고, Claude Code 는 약 150,000자를 넘는 MCP 결과를
-- "Error: result (N characters) exceeds maximum allowed tokens. Output has been saved to <임시 파일>" 로 바꿔 버린다.
-- 그 원문은 워커 PC 임시 파일에만 남아 처리 건에서 볼 수 없었다. 이제 워커가 원문을 이 표에 한 번 넣고
-- (id = sha256(처리 건 id + 원문 sha256): 한 처리 건 안의 같은 원문은 한 행, 다른 처리 건 · 테넌트는 각자 행 — 원문 sha256 은 meta.content_sha256.
--  process-gpt cli-agent core/journal.py:187-201 의 내용 주소 스냅숏과 같은 방식에 처리 건 범위를 더함, it/agent-worker/worker/payloads.py),
-- tool_usage_finished 행의 data.full_output.ref 로 가리킨다. 포털은 GET /api/event-payloads/{id} 로 펼쳐 읽는다.
-- 스택에는 Supabase Storage 가 꺼져 있어(config.toml [storage] enabled=false) 같은 DB 의 표로 둔다.
create table if not exists public.event_payloads (
  id           text primary key check (id ~ '^[0-9a-f]{64}$'),   -- sha256(proc_inst_id + sha256(content)) 16진수 (payloads.payload_id)
  content      text not null,                                   -- 도구 결과 원문(포장 해제한 텍스트, 최대 4,000,000자)
  chars        integer not null,
  content_type text not null default 'text',                    -- json | text
  source       text not null,                                   -- cli_saved_file (CLI 가 임시 파일로 뺀 결과) | event_text (미리보기로 자른 결과)
  tool         text,
  tool_use_id  text,
  job_id       text,
  todo_id      text,
  proc_inst_id text,
  meta         jsonb not null default '{}'::jsonb,              -- 원래 길이 · 잘림 여부 · CLI 임시 파일 경로(기록용)
  created_at   timestamptz not null default now()
);
create index if not exists ix_event_payloads_inst on public.event_payloads (proc_inst_id, created_at);
comment on table public.event_payloads is 'A161-G2: events 행이 가리키는 큰 도구 결과 원문 (워커가 쓰고 포털이 /api/event-payloads/{id} 로 읽음)';

-- 권한: events 와 같은 교육 환경 정책(읽기 전체 허용 · 쓰기 authenticated, migration 000001)
alter table public.event_payloads enable row level security;
drop policy if exists event_payloads_read_all on public.event_payloads;
create policy event_payloads_read_all on public.event_payloads for select to anon, authenticated using (true);
drop policy if exists event_payloads_write_authenticated on public.event_payloads;
create policy event_payloads_write_authenticated on public.event_payloads for all to authenticated using (true) with check (true);
grant select on public.event_payloads to anon;
grant all on public.event_payloads to authenticated, service_role;
