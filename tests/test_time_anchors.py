"""A086 (R05, meeting L75~79): business times are stored as points in time and read as hours from now.

Before: ent.production_orders.due_in_h etc. were frozen numbers (the 6 h due set on 10-03 was still 6 h on 10-07). Now the
Supabase tables keep due_at · ship_at · night_window_at · performed_at, the RPC facts keep their names with current values,
the teaching reset re-anchors the scenario, DDL ingestion turns a timestamp column into signed hours from now, and the
consent compares the stored time (anchor) instead of the moving hours."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from agentsvc import decide
from agentsvc.tools import physical
from entsim import data, main as entmain
from procsvc import ingest

ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 10, 7, 0, 0, tzinfo=timezone.utc)


def test_memory_backend_hours_fall_with_time_and_reset_reanchors(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTERPRISE_STATE_PATH", str(tmp_path / "e.sqlite3"))
    data.reanchor(T0)
    monkeypatch.setattr(data, "_now", lambda: T0 + timedelta(hours=1))
    m = entmain.MemoryEnterprise()
    mes = m.read("mes_orders", asset="HYD-01")
    assert mes["facts"]["due_in_h"] == 5.0 and mes["facts"]["alt_free_h"] == 7.0
    assert mes["facts"]["due_at"] == (T0 + timedelta(hours=6)).isoformat() and mes["records"][0]["due_in_h"] == 5.0
    assert m.read("erp_inventory", asset="HYD-01")["facts"]["ship_in_h"] == 1.0
    cmms = m.read("cmms_history", asset="HYD-02")["facts"]
    assert cmms["last_clean_days"] == 21 and cmms["cleans_60d"] == 1 and cmms["night_in_h"] == 8.0       # history is the source
    monkeypatch.setattr(data, "_now", lambda: T0 + timedelta(days=30))
    assert m.read("cmms_history", asset="HYD-01")["facts"]["cleans_60d"] == 1                           # 51·68·85 days → one inside 60
    assert m.read("mes_orders", asset="HYD-01")["facts"]["due_in_h"] < 0                                # overdue, not frozen
    monkeypatch.setattr(data, "_now", lambda: datetime.now(timezone.utc))
    m.reset()
    assert m.read("mes_orders", asset="HYD-01")["facts"]["due_in_h"] == 6.0


def test_migration_keeps_the_old_columns_and_the_seed_reanchors():
    sql = (ROOT / "it/supabase/migrations/20261007000017_enterprise_time_anchors.sql").read_text(encoding="utf-8").lower()
    assert "drop column" not in sql and "drop table" not in sql                                          # data preserved
    assert "ent.hours_from_now(o.due_at)" in sql and "perform ent.reanchor_scenario_times()" in sql
    seed = (ROOT / "it/supabase/seed.sql").read_text(encoding="utf-8")
    assert "due_in_h" not in seed and seed.rstrip().endswith("select ent.reanchor_scenario_times();")


DDL = """create table ent.production_orders (   -- MES: 생산오더
  order_id text primary key, asset text not null, due_at timestamptz not null, remaining_qty integer not null);"""


def test_ddl_ingestion_reads_a_point_in_time_as_hours_from_now():
    p = ingest.plan(ingest.parse_ddl(DDL), filename="x.sql", batch="b", selection={"ent.production_orders": ["due_at", "remaining_qty"]})
    items = {i["column"]: i for i in p["inputs"]}
    assert items["due_at"]["derive"] == "hours_from_now" and items["due_at"]["typeRef"] == "number" and items["due_at"]["name"].endswith("(지금부터 h)")
    assert "derive" not in items["remaining_qty"] and items["remaining_qty"]["typeRef"] == "number"
    ingest.validate_plan(p)
    bad = dict(p, inputs=[dict(items["remaining_qty"], derive="hours_from_now")])
    with pytest.raises(ValueError, match="시각 열만"):
        ingest.validate_plan(bad)
    q = ingest.tests_to_sql([{"variable": items["due_at"]["variable"], "operator": "<", "value": 8}],
                            {items["due_at"]["variable"]: items["due_at"]})["queries"][0]["sql"]
    assert 'extract(epoch from ("due_at" - now())) / 3600' in q and "< %(v0)s" in q


class _Conn:
    def __init__(self, row): self.row, self.sql = row, []
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, query, params=None):
        self.sql.append(query); return self
    def fetchone(self): return ("postgres",)
    def fetchall(self): return [self.row]


def test_physical_read_returns_hours_and_keeps_the_stored_time_as_anchor(monkeypatch):
    due = datetime(2026, 10, 7, 3, 0, tzinfo=timezone.utc)
    conn = _Conn((due, Decimal("5.97")))
    monkeypatch.setenv("ENTERPRISE_READ_DSN", "postgresql://x")
    monkeypatch.setattr(physical, "reader_connection", lambda dsn: conn)
    item = dict(datasource="hyd-enterprise", catalog="postgres", schema="ent", table="production_orders", column="due_at",
                assetColumn="asset", typeRef="number", sqlType="timestamptz", derive="hours_from_now")
    value, anchor = physical.read_physical_fact(item, "HYD-01")
    assert value == "5.97" and anchor == due.isoformat()
    with pytest.raises(ValueError, match="derivation"):
        physical.read_physical_fact(dict(item, derive="days_since"), "HYD-01")


def test_gather_facts_records_the_anchor_of_a_derived_physical_input(monkeypatch):
    item = dict(id="in:x", variable="db_due", name="납기 (지금부터 h)", typeRef="number", source="sys:mes", sourceName="MES",
                sourceKind="System", datasource="hyd-enterprise", catalog="postgres", schema="ent", table="production_orders",
                column="due_at", assetColumn="asset", sqlType="timestamptz", derive="hours_from_now")
    monkeypatch.setattr(decide, "read_physical_fact", lambda i, asset: ("5.97", "2026-10-07T03:00:00+00:00"))
    facts, prov = decide.gather_facts([item], "HYD-01", {}, None)
    assert facts["db_due"] == "5.97" and prov[0]["anchor"] == "2026-10-07T03:00:00+00:00" and "환산" in prov[0]["how"]


class _Cur:
    def __init__(self, row): self.row = row
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, params=None): self.sql = sql
    def fetchone(self): return self.row


@pytest.mark.parametrize('row,expected', [
    ((None, None, None), None),                                                     # no sample: unknown, not 0 h
    ((60.0, T0, T0 - timedelta(hours=3)), 0.0),                                     # below 99 % now: no running streak
    ((100.0, T0, T0 - timedelta(hours=26)), 26.0),                                  # HM-7.3: continuous 26 h > 24 h
])
def test_fan100_hours_is_the_current_continuous_run(monkeypatch, row, expected):
    """A086: rule:fan-24h and HM-7.3 say *continuous* 100 % run; the engine used to sum 48 h of ≥ 99 % time."""
    from agentsvc.tools import mcp_tsdb
    db = mcp_tsdb.TimeSeriesDB()
    class C:
        def __enter__(s): return s
        def __exit__(s, *a): return False
        def cursor(s): return _Cur(row)
    monkeypatch.setattr(db, '_conn', lambda: C())
    assert db.fan100_hours('HYD-01') == expected
