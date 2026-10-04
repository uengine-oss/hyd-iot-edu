-- Unknown is distinct from ready. Existing installations retain NULL until CMMS
-- records readiness. Fresh teaching fixtures declare their values in seed.sql.
alter table ent.maintenance_profiles add column if not exists standby_ready boolean;
comment on column ent.maintenance_profiles.standby_ready is
  'CMMS-confirmed standby pump readiness; NULL means not confirmed';
