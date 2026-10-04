-- A source event opens at most one instance per tenant/definition, even after
-- completion or replay. Backfill preserves history; duplicate existing events
-- deliberately fail the unique index instead of silently deleting a record.
begin;
alter table public.bpm_proc_inst add column if not exists start_event_id text;
update public.bpm_proc_inst i
set start_event_id = (
  select v->>'value' from jsonb_array_elements(i.variables_data) v
  where v->>'key' = 'alert_id' limit 1
)
where start_event_id is null;
create unique index if not exists ux_proc_start_event
  on public.bpm_proc_inst (tenant_id, proc_def_id, start_event_id)
  where start_event_id is not null;
commit;
