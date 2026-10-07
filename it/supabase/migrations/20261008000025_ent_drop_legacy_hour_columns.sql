-- A143 (remaining-sweep 11; DECISIONS 103): drop the frozen hour/day columns that A086 (migration 000017) replaced with
-- *_at timestamps. Since 000017 nothing reads them: the read RPCs compute due_in_h / alt_free_h / ship_in_h / night_in_h /
-- last_clean_days / cleans_60d / days_ago from due_at / alt_free_at / ship_at / night_window_at / performed_at
-- (000017:56-90), seed.sql inserts only the *_at columns, enterprise-sim's Supabase backend strips them from to_jsonb()
-- (entsim/supabase_backend.py snapshot), and the only INSERT that named days_ago was the one-off backfill in 000017:21
-- (already executed). Verified on an empty database: migrations 1..25 apply in order and the read RPCs still answer
-- (`.evidence/a143/repro_lease_lock_order.py` → `ent_legacy_columns_left: []`). The data was copied into the *_at columns
-- by 000017:15-19 before this drop, so no scenario value is lost; ent.reanchor_scenario_times() restores the teaching times.
alter table ent.production_orders drop column if exists due_in_h, drop column if exists alt_free_h;
alter table ent.fg_inventory drop column if exists ship_in_h;
alter table ent.maintenance_profiles drop column if exists night_in_h, drop column if exists last_clean_days, drop column if exists cleans_60d;
alter table ent.maintenance_history drop column if exists days_ago;
