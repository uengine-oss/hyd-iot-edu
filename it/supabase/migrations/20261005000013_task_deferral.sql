-- HYD task deferral is not a successful task_completed event. Keep the
-- assessment and explicit new request as separate durable history entries.
alter type public.event_type_enum add value if not exists 'task_deferred';
alter type public.event_type_enum add value if not exists 'task_reassessment_requested';
create index if not exists events_task_receipt_idx on public.events(todo_id,job_id,event_type);
