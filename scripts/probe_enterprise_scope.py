"""Live DB privileges and deployed HTTP MCP; run inside enterprise-mcp image.

Reads compare against local admin values. Denied writes use WHERE false and a
transaction that always rolls back. No process/enterprise business data changes.
"""
import asyncio
import json
import os
from pathlib import Path

import psycopg
from psycopg import sql
from fastmcp import Client

READER = os.environ['ENTERPRISE_DSN']
ADMIN = 'postgresql://postgres:postgres@host.docker.internal:54322/postgres'
report = {'checks': [], 'passed': False}


def check(name, condition, detail=None):
    report['checks'].append({'name': name, 'passed': bool(condition), 'detail': detail})
    assert condition, (name, detail)


def db_checks():
    with psycopg.connect(ADMIN) as admin, psycopg.connect(READER) as reader:
        role = reader.execute("select current_user,current_setting('transaction_read_only'),current_setting('statement_timeout')").fetchone()
        check('reader role and defaults', role == ('hyd_enterprise_reader', 'on', '5s'), role)
        tables = admin.execute("select tablename from pg_tables where schemaname='ent' order by tablename").fetchall()
        for (name,) in tables:
            q = sql.SQL('select count(*) from ent.{}').format(sql.Identifier(name))
            a, r = admin.execute(q).fetchone()[0], reader.execute(q).fetchone()[0]
            check('RLS visible: '+name, a == r, {'admin': a, 'reader': r})
        for fn in ('ent.exec_skill(jsonb)', 'ent.reset_executions()'):
            values = admin.execute('select has_function_privilege(%s,%s,\'EXECUTE\'),has_function_privilege(%s,%s,\'EXECUTE\')',
                                   ('hyd_enterprise_reader',fn,'service_role',fn)).fetchone()
            check('write RPC privileges: '+fn, values == (False,True), values)
    # Turn off the default read-only mode to test actual privileges, not just a setting.
    for query in ('select count(*) from public.todolist', 'update ent.assets set code=code where false',
                  'delete from ent.assets where false', 'set role postgres',
                  "select ent.exec_skill('{}'::jsonb)", 'select ent.reset_executions()'):
        with psycopg.connect(READER) as c:
            try:
                c.execute('set transaction read write')
                c.execute(query)
            except psycopg.Error as e:
                check('DB denied: '+query, e.sqlstate == '42501', {'sqlstate':e.sqlstate,'message':str(e).splitlines()[0]})
            else:
                check('DB denied: '+query, False)
            finally:
                c.rollback()
    from enterprise_mcp import server
    saved = server.DSN
    try:
        server.DSN = ADMIN
        try:
            conn = server.reader_connection()
        except RuntimeError as e:
            check('server refuses admin DSN', True, str(e))
        else:
            conn.close()
            check('server refuses admin DSN', False)
    finally:
        server.DSN = saved


async def mcp_checks():
    async with Client('http://127.0.0.1:8199/mcp') as client:
        async def call(name, arguments):
            result = await client.call_tool(name, arguments)
            if result.structured_content is not None:
                return result.structured_content
            return result.content[0].text
        ddl = await call('describe_schema', {})
        check('MCP schema', 'ent.assets' in str(ddl) and 'public.todolist' not in str(ddl))
        for name, args in [('mes_orders',{'asset':'HYD-01'}), ('erp_contract',{'asset':'HYD-01'}),
                           ('erp_inventory',{'asset':'HYD-01'}), ('cmms_history',{'asset':'HYD-01'}),
                           ('qms_lots',{'asset':'HYD-01'}), ('scm_suppliers',{'part':'P-CLR-CORE'}), ('ems_demand',{})]:
            value = await call(name,args)
            check('MCP facts: '+name, value['result']=='ok' and bool(value['document']['facts']), value)
        valid = [
            ("select count(*) from assets", [[3]]),
            ("select count(*) from assets where code='missing'", [[0]]),
            ("select code from assets where code='missing'", []),
            ("select 'delete; -- /* keep this */' as note from assets limit 1", [['delete; -- /* keep this */']]),
            ("with a as (select code from assets) select sum(case when code='HYD-01' then 1 else 0 end) from a", [[1]]),
        ]
        for query, expected in valid:
            value = await call('query',{'sql':query})
            check('MCP normal: '+query, value.get('result')=='ok' and value['document']['rows']==expected, value)
        value = await call('query',{'sql':'select * from (select code from assets limit 1) a union all select code from assets limit 900 offset 1'})
        check('MCP nested/outer LIMIT and OFFSET', value.get('result')=='ok' and value['document']['row_count']==3 and value['document']['statement'].endswith('LIMIT 200 OFFSET 1'),value)
        for query in ('select * from public.todolist', 'with x as (select * from public.todolist) select * from x',
                      "select ent.exec_skill('{}'::jsonb)", "select pg_read_file('/tmp/x')",
                      "select set_config('search_path','public',true)", 'select * from assets for share',
                      'select * into temporary copied_assets from assets', 'delete from assets'):
            value = await call('query',{'sql':query})
            check('MCP rejected: '+query, value.get('result')=='error' and value.get('error_kind')=='INVALID',value)
        value = await call('query',{'sql':'select obsolete_column from assets'})
        check('MCP DB failure stays error',value.get('result')=='error' and value.get('error_kind')=='UNKNOWN',value)


if __name__ == '__main__':
    try:
        db_checks()
        asyncio.run(mcp_checks())
        report['passed'] = True
    finally:
        print(json.dumps(report,ensure_ascii=False,indent=2))
