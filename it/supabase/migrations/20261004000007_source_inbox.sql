-- A033 source receipts. Kafka acknowledgement follows this commit, never precedes it.
-- Execution/claim/retry wiring is implemented separately; PENDING is not handled.
create table if not exists public.process_source_inbox (
  id bigint generated always as identity primary key,
  tenant_id text not null,
  source text not null check (source in ('kafka','http')),
  delivery_key text not null,
  topic text not null check (topic in ('alerts','plant.status')),
  partition_no integer check (partition_no >= 0),
  offset_no bigint check (offset_no >= 0),
  event_key text not null,
  asset text,
  kind text not null check (kind in ('RAISE','CLEAR','ACK','STATUS','INVALID')),
  payload jsonb not null,
  payload_sha text not null check (length(payload_sha)=64),
  semantic_sha text not null check (length(semantic_sha)=64),
  wire_kind text not null check (wire_kind in ('bytes','decoded','tombstone')),
  wire_base64 text not null,
  wire_sha text not null check (length(wire_sha)=64),
  policy jsonb not null,
  status text not null check (status in ('PENDING','CLAIMED','HANDLED','WAITING','FAILED','DUPLICATE','CONFLICT','INVALID')),
  parent_id bigint references public.process_source_inbox(id),
  attempts integer not null default 0 check (attempts >= 0),
  failures integer not null default 0 check (failures >= 0),
  owner text,
  claim_token uuid,
  lease_until timestamptz,
  next_attempt_at timestamptz not null default now(),
  error text,
  result jsonb,
  history jsonb not null default '[]',
  received_at timestamptz not null default now(),
  handled_at timestamptz,
  unique (tenant_id,topic,partition_no,offset_no),
  unique (tenant_id,delivery_key),
  check ((source='kafka' and partition_no is not null and offset_no is not null)
      or (source='http' and topic='alerts' and partition_no is null and offset_no is null)),
  check ((status in ('DUPLICATE','CONFLICT')) = (parent_id is not null))
);
create unique index if not exists source_inbox_event_identity
  on public.process_source_inbox(tenant_id,event_key) where parent_id is null;
create index if not exists source_inbox_pending
  on public.process_source_inbox(tenant_id,status,next_attempt_at,id);
alter table public.process_source_inbox enable row level security;
revoke all on public.process_source_inbox from public,anon,authenticated;
grant select,insert,update on public.process_source_inbox to service_role;
grant usage,select on sequence public.process_source_inbox_id_seq to service_role;

create table if not exists public.process_source_state (
  tenant_id text not null,
  asset text not null,
  source_time timestamptz not null,
  receipt_id bigint not null references public.process_source_inbox(id),
  payload jsonb not null,
  primary key(tenant_id,asset)
);
alter table public.process_source_state enable row level security;
revoke all on public.process_source_state from public,anon,authenticated;
grant select,insert,update on public.process_source_state to service_role;
