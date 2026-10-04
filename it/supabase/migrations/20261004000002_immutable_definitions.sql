-- Published HYD definitions are immutable by tenant/definition/version.
-- Existing product major/minor records remain independent of this adapter.
create unique index if not exists ux_hyd_immutable_definition
on public.proc_def_version (tenant_id, proc_def_id, version)
where version_tag = 'hyd-immutable';

-- Preserve the current definition before introducing version-aware execution.
-- This is NOT proof that historical runs used these exact bytes; the old
-- implementation did not keep snapshots. That limitation remains in message.
insert into public.proc_def_version
  (arcv_id, proc_def_id, version, version_tag, tenant_id, definition, message)
select id || '_' || (definition->>'version'), id, definition->>'version',
       'hyd-immutable', tenant_id, definition,
       'Legacy current-definition backfill; historical execution bytes were not recorded'
from public.proc_def
where not isdeleted and definition is not null
  and coalesce(definition->>'version', '') <> ''
on conflict (tenant_id,proc_def_id,version) where version_tag='hyd-immutable' do nothing;
