-- NULL means that an older instance has no recorded start snapshot. Never
-- backfill it from accumulated variables: those already contain task outputs.
alter table public.bpm_proc_inst add column if not exists initial_variables jsonb;
alter table public.bpm_proc_inst add column if not exists variable_sources jsonb not null default '{}';
alter table public.bpm_proc_inst add constraint initial_variables_object
  check (initial_variables is null or jsonb_typeof(initial_variables)='object');
alter table public.bpm_proc_inst add constraint variable_sources_object
  check (jsonb_typeof(variable_sources)='object');

create or replace function public.hyd_keep_initial_variables() returns trigger language plpgsql as $$
begin
  if new.initial_variables is distinct from old.initial_variables then
    raise exception 'stored initial variables are immutable';
  end if;
  return new;
end $$;
create trigger hyd_keep_initial_variables before update on public.bpm_proc_inst
  for each row execute function public.hyd_keep_initial_variables();
