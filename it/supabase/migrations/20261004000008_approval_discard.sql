-- Preserve failed consent and distinguish explicit cancellation from success.
alter type public.process_status add value if not exists 'CANCELLED';
alter table public.process_approval_outbox drop constraint if exists process_approval_outbox_status_check;
alter table public.process_approval_outbox add constraint process_approval_outbox_status_check
  check (status in ('PENDING','DELIVERED','FAILED','DISCARDED'));
