-- Independent laptop grouping only; this is not student authentication/ownership.
create table if not exists public.hyd_student_case_tags (
  tenant_id text not null references public.tenants(id) on delete cascade,
  kind text not null check (kind in ('flows','agents','skills','mcp_servers')),
  asset_id text not null,
  label text not null check (char_length(label) between 1 and 60),
  primary key (tenant_id, kind, asset_id)
);
alter table public.hyd_student_case_tags enable row level security;
revoke all on public.hyd_student_case_tags from anon, authenticated;
grant all on public.hyd_student_case_tags to service_role;
