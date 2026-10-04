-- The intent and human submission commit together. Delivery is separately retryable.
-- Parent-instance locking in PgRepo serializes dispatch with engine transitions.
create table if not exists public.process_approval_outbox (
  todo_id uuid primary key references public.todolist(id) on delete cascade,
  proc_inst_id text not null references public.bpm_proc_inst(proc_inst_id) on delete cascade,
  tenant_id text not null references public.tenants(id) on delete cascade,
  decision_id text not null,
  payload jsonb not null check (jsonb_typeof(payload)='object'),
  status text not null check (status in ('PENDING','DELIVERED','FAILED')),
  attempts integer not null default 0 check (attempts>=0),
  results jsonb not null default '[]'::jsonb check (jsonb_typeof(results)='array'),
  error text,
  history jsonb not null default '[]'::jsonb check (jsonb_typeof(history)='array'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id,decision_id)
);
create index if not exists ix_approval_pending on public.process_approval_outbox(tenant_id,todo_id)
  where status='PENDING';
create index if not exists ix_approval_instance on public.process_approval_outbox(tenant_id,proc_inst_id);
alter table public.process_approval_outbox enable row level security;
revoke all on public.process_approval_outbox from public, anon, authenticated;
grant select,insert,update,delete on public.process_approval_outbox to service_role;
comment on table public.process_approval_outbox is
  'HYD process-owned approval snapshot and recoverable delivery; not a generic exactly-once bus';
