-- B2 (확정 TODO B, DECISIONS 110 ①): MCP 서버 연결 검사 기록. 서버 설정 자체는 그대로 public.tenants.mcp(워커가 읽는 제품 형태)에 있다.
-- 서버마다 마지막 검사 한 줄(연결 · 도구 목록 · 읽기 전용 판정 · 실패 사유). 포털 등록 · 고치기 · "연결 검사" 때 덮어쓴다.
-- fingerprint = 검사한 설정의 해시(procsvc/mcp_registry.fingerprint). 설정이 바뀌면 지금 설정과 달라져 "다시 검사 필요"가 된다.
-- 기준 서버(seed: neo4j · enterprise · hyd-dmn)의 검사 기록도 여기 쌓이지만 기준 설정(tenants.mcp)은 바꾸지 않는다.
-- POST /api/mcp/reset 은 이 표의 그 테넌트 줄을 모두 지운다(학생이 돌린 검사 기록).
create table if not exists public.mcp_server_checks (
  tenant_id text not null default 'hyd' references public.tenants(id) on update cascade on delete cascade,
  server_name text not null,
  fingerprint text not null,
  status text not null check (status in ('ok', 'failed')),
  error text,
  error_kind text,
  transport text,
  server_info jsonb,
  tools jsonb not null default '[]'::jsonb,              -- [{name, title, description, annotations, read_only, reason}] — 입력 형식은 싣지 않는다
  elapsed_ms integer,
  checked_by text,
  checked_at timestamptz not null default now(),
  primary key (tenant_id, server_name)
);
comment on table public.mcp_server_checks is 'B2: MCP 서버 마지막 연결 검사. 통과(status=ok)하고 fingerprint 가 지금 설정과 같은 서버의 읽기 전용 도구만 에이전트 도구로 고를 수 있다';

-- 권한 · RLS: migration 000001 과 같은 교육 환경 정책(읽기 전체 허용 · 쓰기 authenticated). process 서비스는 소유자 연결로 쓴다.
alter table public.mcp_server_checks enable row level security;
drop policy if exists mcp_server_checks_read_all on public.mcp_server_checks;
create policy mcp_server_checks_read_all on public.mcp_server_checks for select to anon, authenticated using (true);
drop policy if exists mcp_server_checks_write_authenticated on public.mcp_server_checks;
create policy mcp_server_checks_write_authenticated on public.mcp_server_checks for all to authenticated using (true) with check (true);
grant select on public.mcp_server_checks to anon;
grant all on public.mcp_server_checks to authenticated, service_role;
