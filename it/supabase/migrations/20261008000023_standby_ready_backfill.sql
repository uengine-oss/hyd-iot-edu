-- A133 (2026-10-08): ent.maintenance_profiles.standby_ready was NULL on all three assets in the live DB — the rows predate
-- migration 6 and seed.sql inserts with `on conflict do nothing`, so the seed's `true` never landed (found in A120 pump run:
-- rule:standby then treats the standby pump as "unconfirmed" and the recommendation tilts to derate-70). A fresh DB gets
-- `true` from the seed; this backfill makes an old DB match it. Additive, idempotent.
update ent.maintenance_profiles set standby_ready = true where standby_ready is null;
comment on column ent.maintenance_profiles.standby_ready is 'A133: NULL(미확인)은 시드 기본값 true로 보정됨 — 수업 환경은 예비 펌프 사용 가능이 기본';
