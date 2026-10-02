"""mcp-tsdb (read-only): runs the Evidence nodes' SQL templates against TimescaleDB (tag_1s / feat_1s).

Only SQL stored on Evidence nodes is executed, with a single named parameter %(asset)s, through the
read-only 'grafana' role. Returns one numeric value per rule.
"""
import os

import psycopg

from .. import card as cardlib

PG_DSN = os.getenv("TSDB_DSN", os.getenv("PG_DSN", "postgresql://grafana:grafana@timescaledb:5432/hyd"))


class TimeSeriesDB:
    def __init__(self):
        self.dsn = PG_DSN

    def _conn(self):
        return psycopg.connect(self.dsn, autocommit=True, connect_timeout=5)

    def evaluate(self, evidence: list[dict], asset: str) -> dict[str, dict]:
        """evidence: [{id, sql, expect, threshold, ...}] -> {id: {"value", "passed", "sql"}}"""
        out: dict[str, dict] = {}
        with self._conn() as conn, conn.cursor() as cur:
            for e in evidence:
                if e["id"] in out or not e.get("sql"):
                    continue
                try:
                    cur.execute(e["sql"], {"asset": asset})
                    row = cur.fetchone()
                    value = None if row is None or row[0] is None else round(float(row[0]), 3)
                except Exception as ex:  # noqa: BLE001
                    out[e["id"]] = {"value": None, "passed": False, "error": str(ex)[:120], "sql": e["sql"]}
                    continue
                out[e["id"]] = {"value": value, "passed": cardlib.passes(e.get("expect"), value, float(e.get("threshold") or 0)),
                                "sql": e["sql"]}
        return out

    def fan100_hours(self, asset: str) -> float:
        """Hours the fan ran at ≥ 99 % in the last 48 h (time-weighted: each row lasts until the next row of the same tag)."""
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("""SELECT coalesce(sum(extract(epoch FROM (nxt - time))) / 3600.0, 0) FROM (
                             SELECT time, value, lead(time) OVER (ORDER BY time) AS nxt FROM tag_1s
                             WHERE asset = %s AND name = 'FanSpeedSP' AND time > now() - interval '48 hours') x
                           WHERE value >= 99 AND nxt IS NOT NULL""", (asset,))
            row = cur.fetchone()
        return round(float(row[0] or 0), 2)

    def latest(self, asset: str, name: str = "TS1") -> tuple[float | None, float | None]:
        """(value, age_seconds) of the newest tag row."""
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT value, extract(epoch FROM now() - time) FROM tag_1s WHERE asset=%s AND name=%s ORDER BY time DESC LIMIT 1",
                        (asset, name))
            row = cur.fetchone()
        return (None, None) if not row else (float(row[0]), float(row[1]))
