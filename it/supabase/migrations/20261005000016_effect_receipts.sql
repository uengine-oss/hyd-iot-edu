-- A072 (2026-10-05): durable receipts for the external effects of a retired generation.
-- kind=compensation: the business systems' exact inverses were requested (PENDING → DELIVERED | FAILED, replayed by request_id).
-- kind=review: a person acknowledged irreversible effects (PLC command, shipped lot …) — RECORDED, immutable.
-- Rework admission reads these rows and the enterprise ledger; nothing here reverses a PLC command.
create table if not exists public.process_effect_receipt (
  tenant_id text not null references public.tenants(id) on delete cascade,
  proc_inst_id text not null references public.bpm_proc_inst(proc_inst_id) on delete cascade,
  request_id uuid not null,
  kind text not null check (kind in ('compensation','review')),
  status text not null check (status in ('PENDING','DELIVERED','FAILED','RECORDED')),
  request jsonb not null check (jsonb_typeof(request)='object'),
  effects jsonb not null check (jsonb_typeof(effects)='array'),
  results jsonb not null default '[]'::jsonb check (jsonb_typeof(results)='array'),
  error text,
  history jsonb not null default '[]'::jsonb check (jsonb_typeof(history)='array'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, proc_inst_id, request_id),
  constraint effect_receipt_kind_status check (
    (kind = 'review' and status = 'RECORDED') or (kind = 'compensation' and status in ('PENDING','DELIVERED','FAILED')))
);
create index if not exists ix_effect_receipt_instance on public.process_effect_receipt(tenant_id, proc_inst_id);

create or replace function public.hyd_keep_effect_receipt() returns trigger language plpgsql as $$
begin
  if row(new.tenant_id, new.proc_inst_id, new.request_id, new.kind, new.request, new.effects, new.created_at)
     is distinct from row(old.tenant_id, old.proc_inst_id, old.request_id, old.kind, old.request, old.effects, old.created_at) then
    raise exception 'effect receipt identity and request are immutable';
  end if;
  if old.kind = 'review' and new.status <> 'RECORDED' then
    raise exception 'a recorded review cannot change status';
  end if;
  return new;
end $$;
drop trigger if exists hyd_keep_effect_receipt on public.process_effect_receipt;
create trigger hyd_keep_effect_receipt before update on public.process_effect_receipt
  for each row execute function public.hyd_keep_effect_receipt();

alter table public.process_effect_receipt enable row level security;
revoke all on public.process_effect_receipt from public, anon, authenticated;
grant select,insert,update,delete on public.process_effect_receipt to service_role;
comment on table public.process_effect_receipt is
  'HYD A072: compensation deliveries and human acknowledgements of a retired generation''s external effects; replayed by request_id';
