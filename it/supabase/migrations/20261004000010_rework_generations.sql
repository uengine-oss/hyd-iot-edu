-- Explicit generations are independent from same-request CMMS retry counters.
alter table public.bpm_proc_inst add column rework_generation integer not null default 0 check (rework_generation >= 0);
alter table public.bpm_proc_inst add column rework_request_id uuid;
alter table public.todolist add column generation integer not null default 0 check (generation >= 0);
alter table public.todolist add column rework_request_id uuid;
alter table public.todolist add column supersedes_id uuid references public.todolist(id);

create table public.process_rework_receipt (
    tenant_id text not null,
    proc_inst_id text not null references public.bpm_proc_inst(proc_inst_id),
    request_id uuid not null,
    generation integer not null check (generation > 0),
    request jsonb not null check (jsonb_typeof(request)='object'),
    result jsonb not null check (jsonb_typeof(result)='object'),
    created_at timestamptz not null default now(),
    primary key (tenant_id, proc_inst_id, request_id),
    unique (tenant_id, proc_inst_id, generation)
);
alter table public.todolist add constraint rework_request_owner
    foreign key (tenant_id,proc_inst_id,rework_request_id)
    references public.process_rework_receipt(tenant_id,proc_inst_id,request_id)
    deferrable initially deferred;
alter table public.bpm_proc_inst add constraint instance_rework_request_owner
    foreign key (tenant_id,proc_inst_id,rework_request_id)
    references public.process_rework_receipt(tenant_id,proc_inst_id,request_id)
    deferrable initially deferred;

create function public.hyd_keep_rework_identity() returns trigger language plpgsql as $$
begin
  if row(new.generation,new.rework_request_id,new.supersedes_id)
     is distinct from row(old.generation,old.rework_request_id,old.supersedes_id) then
    raise exception 'stored workitem generation identity is immutable';
  end if;
  return new;
end $$;
create trigger hyd_keep_rework_identity before update on public.todolist
    for each row execute function public.hyd_keep_rework_identity();

create function public.hyd_keep_rework_receipt() returns trigger language plpgsql as $$
begin
  raise exception 'stored rework receipt is immutable';
end $$;
create trigger hyd_keep_rework_receipt before update on public.process_rework_receipt
    for each row execute function public.hyd_keep_rework_receipt();
