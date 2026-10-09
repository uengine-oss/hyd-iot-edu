-- G2 (전체 과정 랩업, docs/handoff/verification/2026-10-09/capstone-lab.md 5.2): MCP 서버 설정의 비밀 자리표시자 ${SECRET:KEY} 값.
-- 서버 설정(public.tenants.mcp)에는 "Authorization": "Bearer ${SECRET:GOOGLE_TOKEN}" 처럼 이름만 둔다. 값은 이 표에만 있고,
-- process(연결 검사 · 도구 써 보기 · 승인 뒤 시스템 task)와 워커(에이전트 .mcp.json)가 실행 직전에 채운다(procsvc/mcp_secrets.py).
-- 포털 API 는 값을 쓰기만 하고 돌려주지 않는다(GET /api/mcp/secrets 는 이름 · 고친 시각 · 쓰는 서버만).
-- 참고: ProcessGPT mcp-hub catalog.py resolve_template(헤더의 ${SECRET:X} 치환). 다른 점: 저장된 연결정보에 값을 넣지 않고 실행 때마다 채운다.
-- POST /api/mcp/reset(기준으로 되돌리기)은 이 테넌트의 비밀 값도 지운다 — 수업 뒤 학생 자격 증명이 남지 않게(설계 6.2 마친 뒤 정리).
create table if not exists public.mcp_secrets (
  tenant_id text not null default 'hyd' references public.tenants(id) on update cascade on delete cascade,
  key text not null check (key ~ '^[A-Z][A-Z0-9_]{0,63}$'),
  value text not null,
  updated_by text,
  updated_at timestamptz not null default now(),
  primary key (tenant_id, key)
);
comment on table public.mcp_secrets is 'G2: MCP 서버 headers · env 의 ${SECRET:KEY} 값. 값은 API 로 돌려주지 않는다. process · 워커가 실행 직전에만 읽는다';

-- 권한 · RLS: 다른 표와 달리 anon · authenticated 읽기를 열지 않는다(비밀 값). process · 워커는 소유자 연결(postgres)로 읽고 쓴다.
alter table public.mcp_secrets enable row level security;
revoke all on public.mcp_secrets from anon, authenticated;
grant all on public.mcp_secrets to service_role;
