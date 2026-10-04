-- Local teaching-stack credential; configure ENTERPRISE_READ_DSN for another deployment.
-- The MCP never needs the process service's postgres credential.
do $$ begin
  if not exists (select 1 from pg_roles where rolname='hyd_enterprise_reader') then
    create role hyd_enterprise_reader login password 'hyd-enterprise-read-local'
      nosuperuser nocreatedb nocreaterole noinherit noreplication nobypassrls;
  end if;
end $$;
alter role hyd_enterprise_reader set default_transaction_read_only = on;
alter role hyd_enterprise_reader set statement_timeout = '5s';
alter role hyd_enterprise_reader set search_path = pg_catalog, ent;
grant usage on schema ent to hyd_enterprise_reader;
grant select on all tables in schema ent to hyd_enterprise_reader;

-- Existing ent tables have RLS; a SELECT grant alone would silently return zero rows.
do $$ declare t text; begin
  for t in select tablename from pg_tables where schemaname='ent' loop
    execute format('drop policy if exists enterprise_mcp_reader on ent.%I',t);
    execute format('create policy enterprise_mcp_reader on ent.%I for select to hyd_enterprise_reader using (true)',t);
  end loop;
end $$;

-- PUBLIC EXECUTE is PostgreSQL's default for functions. Revoking only from
-- anon/authenticated did not remove that inherited grant on these write RPCs.
revoke execute on function ent.exec_skill(jsonb), ent.reset_executions() from public;
grant execute on function ent.exec_skill(jsonb), ent.reset_executions() to service_role;
grant execute on function ent.mes_orders(text), ent.erp_contract(text),
  ent.erp_inventory(text), ent.cmms_history(text), ent.qms_lots(text),
  ent.scm_suppliers(text), ent.ems_demand() to hyd_enterprise_reader;
