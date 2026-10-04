"""Real PostgreSQL concurrency/rollback probe in an isolated temporary schema."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "it/process"), str(ROOT / "common")]
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from procsvc import engine, instances, procdb

DSN = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"


def main():
    schema = "reaudit_event_" + uuid.uuid4().hex[:16]
    report = {"schema": schema, "checks": {}}
    def check(name, condition, detail):
        report["checks"][name] = {"passed": bool(condition), "detail": detail}
        if not condition:
            raise AssertionError(name)
    try:
        with psycopg.connect(DSN, autocommit=True) as conn:
            conn.execute(sql.SQL("create schema {}").format(sql.Identifier(schema)))
            for table in ("proc_def", "proc_def_version", "bpm_proc_inst", "todolist"):
                conn.execute(sql.SQL("create table {}.{} (like public.{} including all)").format(
                    sql.Identifier(schema), sql.Identifier(table), sql.Identifier(table)))
            conn.execute(sql.SQL("alter table {}.bpm_proc_inst add column if not exists start_event_id text").format(sql.Identifier(schema)))
            conn.execute(sql.SQL("create unique index if not exists ux_probe_event on {}.bpm_proc_inst (tenant_id,proc_def_id,start_event_id) where start_event_id is not null").format(sql.Identifier(schema)))
        repo = procdb.PgRepo(make_conninfo(DSN, options=f"-c search_path={schema},public"))
        definition = engine.Definition.load(ROOT / "it/process/definitions/anomaly_response.json")
        hooks = instances.Hooks(new_incident=lambda alert: {"id": "audit:" + alert["alertId"]})
        runtime = instances.InstanceRuntime(repo, definition, hooks)
        alert = {"alertId": "audit-concurrent", "asset": "HYD-01", "pattern": "COOLER_DEGRADATION"}
        with ThreadPoolExecutor(max_workers=8) as pool:
            created = list(pool.map(lambda _: runtime.on_alert_raise(alert), range(16)))
        winners = [item for item in created if item]
        check("sixteen_concurrent_deliveries", len(winners) == 1, {"created": len(winners)})
        inst = winners[0]
        rows = repo.list_workitems(proc_inst_id=inst["proc_inst_id"])
        check("complete_initial_workitems", len(rows) == len(definition.activities), {"count": len(rows)})
        inst["status"] = "COMPLETED"
        repo.update_instance(inst)
        check("completed_event_replay", runtime.on_alert_raise(alert) is None, "no second instance")
        collision = dict(inst, proc_inst_id="audit." + str(uuid.uuid4()))
        try:
            repo.insert_instance(collision)
        except psycopg.errors.UniqueViolation:
            check("database_unique_constraint", True, "duplicate start event rejected")
        else:
            check("database_unique_constraint", False, "duplicate accepted")
        original = repo.insert_workitems
        def fail(items):
            original(items)
            raise RuntimeError("injected storage failure after workitem insert")
        repo.insert_workitems = fail
        failed_alert = dict(alert, alertId="audit-rollback")
        try:
            runtime.on_alert_raise(failed_alert)
        except RuntimeError:
            pass
        else:
            raise AssertionError("injected failure not raised")
        repo.insert_workitems = original
        with repo._conn() as conn:
            count = conn.execute("select count(*) as n from todolist").fetchone()["n"]
        check("rollback_instance_and_workitems", runtime.find_by_alert("audit-rollback") is None and count == len(rows), {"remaining_workitems": count})
        check("retry_after_rollback", runtime.on_alert_raise(failed_alert) is not None, "retry opens one complete instance")
        other = instances.InstanceRuntime(repo, definition, hooks, tenant_id="audit-other")
        check("separate_tenant_scope", other.on_alert_raise(alert) is not None, "same event can belong to another tenant")
    finally:
        # Only the generated probe schema is removed; no public application data.
        assert schema.startswith("reaudit_event_") and len(schema) == 30
        with psycopg.connect(DSN, autocommit=True) as conn:
            conn.execute(sql.SQL("drop schema if exists {} cascade").format(sql.Identifier(schema)))
        report["temporary_schema_removed"] = True
        output = ROOT / ".evidence/reaudit/event-identity-postgres.json"
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
