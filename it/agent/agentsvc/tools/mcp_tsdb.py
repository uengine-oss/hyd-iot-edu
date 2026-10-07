"""Read-only TimescaleDB metadata, generated sensor SQL and stored Evidence SQL.

The dedicated hyd_timeseries_reader reads tag_1s/feat_1s/tag_1m. All connections
use read-only transactions and a timeout; SQL AST rules restrict read surfaces.
Stored Evidence templates retain their %(asset)s parameter and scalar result.
"""
import os
import math
from datetime import timedelta

import psycopg
from hydcommon.daq_contract import reporting_interval
from hydcommon.sql_read import guard, READ_FUNCTIONS

from .. import card as cardlib

PG_DSN = os.getenv("TSDB_DSN", "postgresql://hyd_timeseries_reader:hyd-timeseries-read-local@timescaledb:5432/hyd")
TABLES = frozenset({'tag_1s', 'feat_1s', 'tag_1m'})
DAQ_PROFILE = os.getenv('DAQ_PROFILE', 'lite')
OBSERVATION_GRACE_S = 2.0          # the detector's Observations grace: one contract for "no gap"


def read_sql(sql):
    return guard(sql, schema='public', tables=TABLES, functions=READ_FUNCTIONS | {'TIME_BUCKET'})


def observation_coverage(times, window_start, now, limit_s):
    """A083 (R05, meeting L51~79): a window aggregate (avg/max-min over N s) is evidence only if the window was observed.
    Every instant of [window_start, now] must lie within limit_s after some sample — the detector's gap rule from
    hydcommon.daq_contract (deadband tags are legitimately silent up to their heartbeat). `times` are the tag's sample
    times from window_start - limit_s to now, ascending. Returns the coverage record kept with the result."""
    prior = [t for t in times if t <= window_start]
    inside = [t for t in times if window_start < t <= now]
    points = [prior[-1] if prior else window_start] + inside + [now]
    max_gap = max((b - a).total_seconds() for a, b in zip(points, points[1:]))
    return {'samples': len(inside), 'max_gap_s': round(max_gap, 3), 'limit_s': limit_s,
            'covered': bool(inside or prior) and max_gap <= limit_s}


class TimeSeriesDB:
    def __init__(self):
        self.dsn = PG_DSN

    def _conn(self):
        return psycopg.connect(self.dsn, autocommit=True, connect_timeout=5,
                               options='-c default_transaction_read_only=on -c statement_timeout=5000 -c search_path=pg_catalog,public')

    def describe_schema(self):
        """Actual columns plus observed tag identities; never invent sensor metrics."""
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute('''select table_name,column_name,data_type,is_nullable from information_schema.columns
                where table_schema='public' and table_name=any(%s) order by table_name,ordinal_position''',(sorted(TABLES),))
            tables={}
            for table,column,dtype,nullable in cur.fetchall():
                tables.setdefault(table,[]).append(dict(name=column,type=dtype,nullable=nullable=='YES'))
            cur.execute('''select asset,name,max(time) as newest from public.tag_1s
                where time > now()-interval '5 minutes' group by asset,name order by asset,name limit 201''')
            series=[dict(asset=a,name=n,newest=t.isoformat()) for a,n,t in cur.fetchall()]
        return dict(source='hyd-timeseries',dialect='postgresql',schema='public',tables=tables,
                    recent_series=series[:200],series_truncated=len(series)>200,
                    series_window_seconds=300,query_tool='timeseries_query',
                    note='Series are observed in the last 5 minutes; absence is not proof the sensor never existed. tag_1m is a delayed one-minute aggregate; continuous duration needs timestamps, gaps and freshness checks.')

    def query(self, sql):
        statement=read_sql(sql)
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(statement)
            columns=[d.name for d in cur.description]
            rows=[list(r) for r in cur.fetchall()]
        return dict(source='hyd-timeseries',dialect='postgresql',statement=statement,
                    columns=columns,rows=rows,row_count=len(rows),row_limit=200,
                    at_row_limit=len(rows)==200)

    def evaluate(self, evidence: list[dict], asset: str) -> dict[str, dict]:
        """Scalar evidence: PASS/FAIL are observed predicates; UNKNOWN never means false."""
        out: dict[str, dict] = {}
        with self._conn() as conn, conn.cursor() as cur:
            for e in evidence:
                if e["id"] in out:
                    continue
                result = {"value": None, "passed": None, "status": "UNKNOWN", "sql": e.get("sql")}
                out[e['id']] = result
                try:
                    if not e.get('sql'):
                        raise ValueError('Evidence has no SQL')
                    if e.get('expect') not in {'lt', 'lte', 'gt', 'gte', 'eq'}:
                        raise ValueError('Unsupported Evidence comparator')
                    threshold = float(e['threshold'])
                    if isinstance(e['threshold'], bool) or not math.isfinite(threshold):
                        raise ValueError('Evidence threshold must be finite')
                    cur.execute(read_sql(e["sql"]), {"asset": asset})
                    rows = cur.fetchmany(2)
                    if not rows or (len(rows) == 1 and len(rows[0]) == 1 and rows[0][0] is None):
                        result['reason'] = 'NO_DATA'
                        continue
                    if len(rows) != 1 or len(rows[0]) != 1:
                        raise ValueError('Evidence SQL must return exactly one scalar')
                    raw = rows[0][0]
                    value = float(raw)
                    if isinstance(raw, (bool, str)) or not math.isfinite(value):
                        raise ValueError('Evidence SQL must return a finite numeric scalar')
                    if e.get('tag') is None and e.get('windowSeconds') is None:
                        result['coverage'] = None          # not a declared window predicate: nothing to prove
                    else:
                        tag, window = e.get('tag'), e.get('windowSeconds')
                        if not isinstance(tag, str) or not tag or isinstance(window, bool) or not isinstance(window, (int, float)) \
                                or not math.isfinite(window) or window <= 0:
                            raise ValueError('Evidence window needs both tag and a positive windowSeconds')
                        limit = reporting_interval(tag, DAQ_PROFILE) + OBSERVATION_GRACE_S
                        cur.execute("SELECT now(), coalesce(array_agg(time ORDER BY time), '{}') FROM tag_1s WHERE asset = %s AND name = %s "
                                    "AND time > now() - make_interval(secs => %s) AND time <= now()", (asset, tag, float(window) + limit))
                        now, times = cur.fetchone()
                        cov = observation_coverage(list(times), now - timedelta(seconds=float(window)), now, limit)
                        result['coverage'] = dict(cov, tag=tag, window_s=float(window))
                        if not cov['covered']:
                            result.update(value=value, reason='OBSERVATION_GAP')   # the partial aggregate is kept, never judged
                            continue
                except Exception as ex:  # noqa: BLE001
                    invalid = isinstance(ex, (ValueError, TypeError, KeyError)) or (isinstance(ex, psycopg.Error) and (ex.sqlstate or '').startswith('42'))
                    result.update(reason='QUERY_ERROR', error_kind='INVALID' if invalid else 'UNKNOWN', error=str(ex)[:120])
                    continue
                # Compare the original value; rounding at the threshold changes truth.
                passed = cardlib.passes(e['expect'], value, threshold)
                result.update(value=value, passed=passed, status='PASS' if passed else 'FAIL')
        return out

    def fan100_hours(self, asset: str) -> float | None:
        """Length of the fan's current continuous run at ≥ 99 % in hours (HM-7.3 "100 % 연속 운전은 24시간 이내", rule:fan-24h).
        0 when the newest sample is below 99 %; None when there is no sample in the last 48 h (no data is not 0 h).
        A086: this used to be the 48 h *cumulative* time, a different quantity from the rule and the manual."""
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("""WITH s AS (SELECT time, value FROM tag_1s WHERE asset = %s AND name = 'FanSpeedSP' AND time > now() - interval '48 hours'),
                                newest AS (SELECT time, value FROM s ORDER BY time DESC LIMIT 1),
                                broke AS (SELECT max(time) AS t FROM s WHERE value < 99)
                           SELECT (SELECT value FROM newest), (SELECT time FROM newest),
                                  (SELECT min(time) FROM s WHERE time > coalesce((SELECT t FROM broke), '-infinity'::timestamptz))""", (asset,))
            value, newest, run_start = cur.fetchone()
        if value is None:
            return None
        if float(value) < 99 or run_start is None:
            return 0.0
        return round((newest - run_start).total_seconds() / 3600, 2)

    def latest(self, asset: str, name: str = "TS1") -> tuple[float | None, float | None]:
        """(value, age_seconds) of the newest tag row."""
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT value, extract(epoch FROM now() - time) FROM tag_1s WHERE asset=%s AND name=%s ORDER BY time DESC LIMIT 1",
                        (asset, name))
            row = cur.fetchone()
        return (None, None) if not row else (float(row[0]), float(row[1]))
