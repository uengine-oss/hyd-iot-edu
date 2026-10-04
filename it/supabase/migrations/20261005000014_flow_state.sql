-- End arrivals are control-flow evidence, not user-produced process variables.
-- Old instances have no reconstructed arrival history.
alter table public.bpm_proc_inst
    add column if not exists flow_state jsonb not null default '{}'::jsonb;

alter table public.bpm_proc_inst
    add constraint bpm_proc_inst_flow_state_object
    check (jsonb_typeof(flow_state) = 'object');
