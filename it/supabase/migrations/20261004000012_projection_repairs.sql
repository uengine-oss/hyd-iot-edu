-- Operator-reviewed derived graph repairs; business rows are never rewound.
create table public.projection_repairs (
    request_id uuid primary key,
    tenant_id text not null,
    proc_inst_id text not null,
    fingerprint text not null,
    result jsonb not null,
    created_at timestamptz not null default now()
);
alter table public.projection_repairs enable row level security;
revoke all on public.projection_repairs from anon,authenticated;
