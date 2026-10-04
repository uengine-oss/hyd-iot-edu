"""DDL → ontology ingestion (pure): parsing the real enterprise migration, the System · InputData plan with provenance,
idempotent/reversible Cypher, and a rule's TESTS turned into SQL (회의 2번 · 6번)."""
from datetime import datetime, timezone
from pathlib import Path

from procsvc import ingest

DDL = (Path(__file__).resolve().parents[1] / "it" / "supabase" / "migrations" / "20261003000002_enterprise.sql").read_text(encoding="utf-8")
NOW = datetime(2026, 10, 4, 1, 0, tzinfo=timezone.utc)


def test_parse_the_real_enterprise_ddl():
    tables = {t.qualified: t for t in ingest.parse_ddl(DDL)}
    assert len(tables) == 16 and "ent.production_orders" in tables and "ent.work_orders" in tables
    po = tables["ent.production_orders"]
    assert po.comment.startswith("MES:") and po.system_hint == ("sys:mes", "MES")
    cols = {c.name: c for c in po.columns}
    assert cols["order_id"].primary_key and cols["asset"].references == "ent.assets(code)" and not cols["asset"].nullable
    assert cols["due_in_h"].type == "numeric" and cols["due_in_h"].type_ref == "number" and "납기까지 남은 시간" in cols["due_in_h"].comment
    assert cols["status"].default == "'RUNNING'" and cols["moved_from"].nullable and cols["updated_at"].type_ref == "date"
    assert "primary key" not in [c.name for c in po.columns]                       # constraint lines are not columns
    sc = tables["ent.sales_contracts"]
    assert sc.system_hint == ("sys:erp", "ERP") and {c.name for c in sc.columns} >= {"penalty_per_h", "customer_tier", "failure_cost"}


def test_parse_handles_quotes_dollar_blocks_and_missing_comments():
    text = """-- a function body must not split the DDL
    create or replace function f() returns void language plpgsql as $$ begin perform 1; end $$;
    CREATE TABLE IF NOT EXISTS public.widgets (
      id uuid primary key default gen_random_uuid(),
      "weight" numeric(10,2) not null, -- 무게 (kg)
      note text default 'a;b',
      ok boolean,
      constraint widgets_ok check (ok is not null)
    );"""
    (t,) = ingest.parse_ddl(text)
    assert t.schema == "public" and t.name == "widgets" and t.comment == "" and t.system_hint is None
    names = [c.name for c in t.columns]
    assert names == ["id", "weight", "note", "ok"]
    w = t.columns[1]
    assert w.type == "numeric(10,2)" and w.type_ref == "number" and w.comment == "무게 (kg)" and not w.nullable
    assert t.columns[2].default == "'a;b'" and t.columns[3].type_ref == "boolean"


def test_plan_makes_systems_and_inputdata_with_provenance_and_default_selection():
    tables = ingest.parse_ddl(DDL)
    sel = ingest.default_selection(tables)
    assert "order_id" not in sel["ent.production_orders"] and "asset" not in sel["ent.production_orders"] and "due_in_h" in sel["ent.production_orders"]
    p = ingest.plan(tables, filename="20261003000002_enterprise.sql", batch="ingest:ddl:t1")
    systems = {s["id"]: s for s in p["systems"]}
    assert {"sys:mes", "sys:erp", "sys:cmms", "sys:qms", "sys:scm", "sys:ems"} <= set(systems) and systems["sys:mes"]["zone"] == "IT"
    due = next(i for i in p["inputs"] if i["table"] == "production_orders" and i["column"] == "due_in_h")
    assert due == {"id": "in:db:hyd-enterprise:postgres:ent:production_orders:due_in_h", "name": "납기까지 남은 시간(h). 교육용 고정값; 실습 clock 기준", "typeRef": "number", "variable": due["variable"],
                   "system": "sys:mes", "schema": "ent", "table": "production_orders", "column": "due_in_h", "sqlType": "numeric",
                   "datasource": "hyd-enterprise", "catalog": "postgres", "assetColumn": "asset",
                   "source_id": "20261003000002_enterprise.sql#ent.production_orders.due_in_h"}
    assert p["batch"] == "ingest:ddl:t1" and any(t["table"] == "ent.assets" and t["system"] == "sys:db-hyd-enterprise" for t in p["tables"])
    assert any("sys:db-hyd-enterprise" in w for w in p["warnings"])


def test_plan_respects_the_lecturers_selection_and_system_overrides():
    tables = ingest.parse_ddl(DDL)
    p = ingest.plan(tables, filename="x.sql", batch="b", selection={"ent.assets": ["line"]}, systems={"ent.assets": "sys:erp"})
    assert [i["id"] for i in p["inputs"]] == ["in:db:hyd-enterprise:postgres:ent:assets:line"] and p["inputs"][0]["system"] == "sys:erp"
    assert [s["id"] for s in p["systems"]] == ["sys:erp"]


def test_commit_plan_validates_identity_and_unique_batch_ids():
    import pytest
    p = ingest.plan(ingest.parse_ddl(DDL), filename="x.sql", batch="b", selection={"ent.production_orders": ["due_in_h"]})
    ingest.validate_plan(p)
    p["inputs"][0]["id"] = "in:wrong"
    with pytest.raises(ValueError, match="식별자"):
        ingest.validate_plan(p)
    assert ingest.new_batch_id("ddl", NOW).startswith("ingest:ddl:20261004T010000Z:")
    assert ingest.new_batch_id("ddl", NOW) != ingest.new_batch_id("ddl", NOW)


def test_rule_tests_become_sql_against_the_ingested_columns():
    inputs = {"production_orders_due_in_h": {"schema": "ent", "table": "production_orders", "column": "due_in_h"},
              "production_orders_remaining_qty": {"schema": "ent", "table": "production_orders", "column": "remaining_qty"},
              "sales_contracts_customer_tier": {"schema": "ent", "table": "sales_contracts", "column": "customer_tier"},
              "ts1": {"source": "sen:ts1"}}
    tests = [{"variable": "production_orders_due_in_h", "operator": "<", "value": 8}, {"variable": "production_orders_remaining_qty", "operator": ">=", "value": 1000},
             {"variable": "sales_contracts_customer_tier", "operator": "==", "value": "OEM"}, {"variable": "ts1", "operator": ">", "value": 55}]
    for src in inputs.values():
        if "table" in src:
            src.update(datasource="hyd-enterprise", catalog="postgres")
    out = ingest.tests_to_sql(tests, inputs)
    assert out["unmapped"] == ["ts1"]
    assert [q["sql"] for q in out["queries"]] == [
        'select "asset", "due_in_h", "remaining_qty" from "ent"."production_orders" where "asset" = %(asset)s and "due_in_h" < %(v0)s and "remaining_qty" >= %(v1)s',
        'select "asset", "customer_tier" from "ent"."sales_contracts" where "asset" = %(asset)s and "customer_tier" = %(v0)s']
    assert out["queries"][0]["params"] == {"asset": "<asset>", "v0": 8, "v1": 1000}
    assert out["queries"][1]["params"]["v0"] == "OEM"
