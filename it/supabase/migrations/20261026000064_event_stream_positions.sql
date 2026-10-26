-- Assign stream order AFTER source transactions commit. A bigserial on events
-- alone still loses a low sequence whose transaction commits after the cursor.
create table public.event_stream_positions (
  event_id text primary key references public.events(id) on delete cascade,
  position bigint generated always as identity unique not null
);
alter table public.event_stream_positions enable row level security;
grant select, insert on public.event_stream_positions to service_role;
grant usage, select on sequence public.event_stream_positions_position_seq to service_role;
alter table public.events alter column timestamp set default clock_timestamp();
