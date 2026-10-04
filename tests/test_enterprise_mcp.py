"""enterprise-mcp: the SQL guard (pure) and the tools against a fake connection."""
import json

import pytest

from enterprise_mcp import sql_guard
from enterprise_mcp.tools import EnterpriseTools


def test_guard_accepts_single_select_and_adds_limit():
    assert sql_guard.guard("select order_id, due_in_h from ent.production_orders where asset = 'HYD-01'") == \
        "SELECT order_id, due_in_h FROM ent.production_orders WHERE asset = 'HYD-01' LIMIT 200"
    assert sql_guard.guard("SELECT 1 LIMIT 5;") == "SELECT 1 LIMIT 5"
    assert sql_guard.guard("with x as (select 1) select * from x") == "WITH x AS (SELECT 1) SELECT * FROM x LIMIT 200"
    assert sql_guard.guard("select * from ent.suppliers limit 9999").endswith("LIMIT 200")
    assert sql_guard.guard("-- 납기\nselect due_in_h from ent.production_orders /* c */") == "SELECT due_in_h FROM ent.production_orders LIMIT 200"


@pytest.mark.parametrize("bad", [
    "", "delete from ent.work_orders", "select 1; drop table ent.assets", "update ent.production_orders set due_in_h = 0",
    "select * from pg_catalog.pg_tables", "select * from auth.users", "set role postgres", "explain select 1",
    "select 1 union all select 2; select 3", "copy ent.assets to '/tmp/x'", "create table t (a int)",
])
def test_guard_rejects_writes_multistatements_and_system_schemas(bad):
    with pytest.raises(sql_guard.SqlRejected):
        sql_guard.guard(bad)


@pytest.mark.parametrize('sql', [
    'select count(*) from public.todolist',
    'with x as (select * from public.todolist) select count(*) from x',
    'select * from otherdb.ent.assets',
    'select * from "ENT".assets',
    "select ent.exec_skill('{}'::jsonb)",
    "select pg_read_file('/tmp/x')",
    "select set_config('search_path','public',true)",
    "select pg_catalog.set_config('search_path','public',true)",
    "select nextval('ent.some_sequence')",
    'select * from ent.assets for share',
    'select * into temporary copied_assets from ent.assets',
    'with x as (delete from ent.assets returning *) select * from x',
])
def test_guard_rejects_sources_and_effects_outside_business_reads(sql):
    with pytest.raises(sql_guard.SqlRejected):
        sql_guard.guard(sql)


def test_guard_preserves_sql_words_and_comment_markers_inside_values():
    statement = sql_guard.guard("select 'delete; -- /* keep this */' as note from ent.assets")
    assert "'delete; -- /* keep this */'" in statement


def test_guard_preserves_case_expression_and_resolves_cte_before_table_scope():
    statement = sql_guard.guard("with a as (select code from assets) select case when code='HYD-01' then 1 else 0 end as matched from a")
    assert 'ent.assets' in statement and 'ent.a ' not in statement


def test_guard_caps_outer_union_without_changing_nested_limit():
    statement = sql_guard.guard('select * from (select code from ent.assets limit 1) a union all select code from ent.assets limit 900 offset 1')
    assert statement.upper().endswith('LIMIT 200 OFFSET 1')
    assert 'LIMIT 1)' in statement.upper()


class FakeCursor:
    def __init__(self, log, rows, description=None):
        self.log, self.rows, self.description = log, rows, description

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, args=None):
        self.log.append((sql.strip(), args))

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class FakeConn:
    def __init__(self, log, rows, description=None):
        self.cur = FakeCursor(log, rows, description)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return self.cur


class D:
    def __init__(self, name):
        self.name = name


def test_read_calls_the_named_rpc_with_its_arguments():
    log = []
    tools = EnterpriseTools(lambda: FakeConn(log, [({"system": "MES", "facts": {"due_in_h": 6}, "records": []},)]))
    out = tools.read("mes_orders", asset="HYD-01")
    assert out["result"] == "ok" and out["document"]["facts"]["due_in_h"] == 6 and log[-1] == ("select ent.mes_orders(%s)", ["HYD-01"])
    assert log[0][0] == 'set transaction read only'
    tools2 = EnterpriseTools(lambda: FakeConn(log, [(json.dumps({"system": "EMS", "facts": {}, "records": []}),)]))
    assert tools2.read("ems_demand")["document"]["system"] == "EMS" and log[-1] == ("select ent.ems_demand()", [])
    with pytest.raises(KeyError):
        tools.read("drop_everything")


def test_describe_schema_renders_ddl_like_text():
    catalog = {'catalog':'postgres','schema':'ent','relations':[
        {'name':'work_orders','kind':'r','comment':None,'constraints':[], 'columns':[
            {'name':'status','type':'text','nullable':False,'default':"'배정됨'::text",'comment':None},
            {'name':'decision_id','type':'text','nullable':True,'default':None,'comment':None}]}]}
    ddl = EnterpriseTools(lambda: FakeConn([], [(catalog,)])).describe_schema()
    assert 'create table "ent"."work_orders" (' in ddl
    assert '  "status" text default \'배정됨\'::text not null' in ddl
    assert '  "decision_id" text\n' in ddl


def test_query_runs_guarded_statement_on_a_read_only_time_boxed_transaction():
    log = []
    conn = FakeConn(log, [("MO-0930-0412", 6)], description=[D("order_id"), D("due_in_h")])
    out = EnterpriseTools(lambda: conn, statement_timeout_ms=1234).query("select order_id, due_in_h from production_orders where asset='HYD-01'")
    assert [s for s, _ in log[:3]] == ["set transaction read only", "set local statement_timeout = 1234", "set local search_path = pg_catalog, ent"]
    doc = out["document"]
    assert out["result"] == "ok" and log[3][0].endswith("LIMIT 200") and doc["columns"] == ["order_id", "due_in_h"] and doc["rows"] == [["MO-0930-0412", 6]] and doc["row_count"] == 1
    with pytest.raises(sql_guard.SqlRejected):
        EnterpriseTools(lambda: conn).query("delete from ent.assets")
