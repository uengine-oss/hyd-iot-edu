-- Derived graphs must be recoverable after source commit or graph outage.
-- Append-only enqueue avoids child->outbox / parent->child lock inversion.
create sequence public.hyd_projection_revision;
create table public.execution_projection_outbox (
    id bigserial primary key,
    tenant_id text not null,
    proc_inst_id text not null,
    created_at timestamptz not null default clock_timestamp(),
    processed_at timestamptz,
    revision bigint,
    attempts integer not null default 0,
    last_error text,
    retry_at timestamptz not null default now()
);
create index execution_projection_pending on public.execution_projection_outbox
    (tenant_id, retry_at, id) where processed_at is null;
create index execution_projection_instance on public.execution_projection_outbox
    (tenant_id, proc_inst_id, id);
alter table public.execution_projection_outbox enable row level security;
revoke all on public.execution_projection_outbox from anon, authenticated;
revoke all on sequence public.execution_projection_outbox_id_seq, public.hyd_projection_revision from anon, authenticated;

create function public.hyd_enqueue_execution_projection() returns trigger
language plpgsql security definer set search_path = pg_catalog, public as $$
declare item record;
begin
    if TG_OP = 'UPDATE' and NEW is not distinct from OLD then return NEW; end if;
    if TG_OP = 'DELETE' then item := OLD; else item := NEW; end if;
    if item.proc_inst_id is not null then
        insert into public.execution_projection_outbox(tenant_id,proc_inst_id)
            values(item.tenant_id,item.proc_inst_id);
    end if;
    -- Moving a child must also reconcile its former owner's graph.
    if TG_OP = 'UPDATE' and (OLD.proc_inst_id,OLD.tenant_id) is distinct from (NEW.proc_inst_id,NEW.tenant_id)
       and OLD.proc_inst_id is not null then
        insert into public.execution_projection_outbox(tenant_id,proc_inst_id)
            values(OLD.tenant_id,OLD.proc_inst_id);
    end if;
    return null;
end $$;
create trigger hyd_execution_instance after insert or update or delete on public.bpm_proc_inst
    for each row execute function public.hyd_enqueue_execution_projection();
create trigger hyd_execution_workitem after insert or update or delete on public.todolist
    for each row execute function public.hyd_enqueue_execution_projection();
-- Reconcile pre-migration instances, including soft-deleted sources.
insert into public.execution_projection_outbox(tenant_id,proc_inst_id)
    select tenant_id,proc_inst_id from public.bpm_proc_inst;
