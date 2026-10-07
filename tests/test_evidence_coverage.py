"""A083 (R05, meeting L51~79): a window aggregate is evidence only when the window was observed.

The detector already refuses holds across observation gaps (hydcommon.daq_contract + Observations grace). Evidence SQL
(avg/max-min over N s) used to judge whatever samples were left: one sample in a two-minute window still passed or failed.
Now a declared window (tag + windowSeconds) is checked with the same contract; a gap makes the result UNKNOWN."""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentsvc.tools import mcp_tsdb
from agentsvc.tools.mcp_tsdb import observation_coverage

NOW = datetime(2026, 10, 7, 1, 0, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


def every(seconds, start, end):
    t, out = start, []
    while t <= end:
        out.append(t); t += timedelta(seconds=seconds)
    return out


def test_continuous_one_hertz_window_is_covered():
    ws = NOW - timedelta(seconds=120)
    cov = observation_coverage(every(1, ws - timedelta(seconds=2), NOW), ws, NOW, 3.0)
    assert cov['covered'] and cov['max_gap_s'] == 1.0 and cov['samples'] == 120


def test_a_hole_longer_than_the_contract_is_not_covered():
    ws = NOW - timedelta(seconds=120)
    times = [t for t in every(1, ws, NOW) if not (NOW - timedelta(seconds=70) < t < NOW - timedelta(seconds=60))]
    cov = observation_coverage(times, ws, NOW, 3.0)
    assert not cov['covered'] and cov['max_gap_s'] == 10.0


def test_stale_tail_and_single_sample_are_not_covered():
    ws = NOW - timedelta(seconds=120)
    assert not observation_coverage(every(1, ws, NOW - timedelta(seconds=20)), ws, NOW, 3.0)['covered']    # stopped 20 s ago
    assert not observation_coverage([NOW - timedelta(seconds=1)], ws, NOW, 3.0)['covered']                  # one sample "avg"
    assert not observation_coverage([], ws, NOW, 3.0)['covered']


def test_deadband_tag_silent_within_its_heartbeat_is_covered():
    ws = NOW - timedelta(seconds=120)
    times = every(10, ws - timedelta(seconds=9), NOW)      # TS4: report-by-exception + 10 s heartbeat
    cov = observation_coverage(times, ws, NOW, mcp_tsdb.reporting_interval('TS4', 'lite') + mcp_tsdb.OBSERVATION_GRACE_S)
    assert cov['covered'] and cov['limit_s'] == 12.0


class FakeCursor:
    def __init__(self, value, times):
        self.value, self.times, self.calls = value, times, []

    def __enter__(self): return self
    def __exit__(self, *a): return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params)); self.last = sql

    def fetchmany(self, n): return [(self.value,)]
    def fetchone(self): return (NOW, self.times)


class FakeConn:
    def __init__(self, cur): self.cur = cur
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def cursor(self): return self.cur


EVD = {'id': 'evd:ce-low', 'expect': 'lt', 'threshold': 70,
       'sql': "SELECT avg(value) AS value FROM tag_1s WHERE asset = %(asset)s AND name = 'CE' AND time > now() - interval '30 seconds'",
       'tag': 'CE', 'windowSeconds': 30}


def run(monkeypatch, evidence, times, value=60.0):
    cur = FakeCursor(value, times)
    db = mcp_tsdb.TimeSeriesDB()
    monkeypatch.setattr(db, '_conn', lambda: FakeConn(cur))
    return db.evaluate([evidence], 'HYD-01')[evidence['id']], cur


def test_evaluate_marks_a_gapped_window_unknown_and_keeps_the_partial_value(monkeypatch):
    ws = NOW - timedelta(seconds=30)
    r, cur = run(monkeypatch, EVD, [ws + timedelta(seconds=1), NOW - timedelta(seconds=1)])
    assert r['status'] == 'UNKNOWN' and r['passed'] is None and r['reason'] == 'OBSERVATION_GAP'
    assert r['value'] == 60.0 and r['coverage']['tag'] == 'CE' and r['coverage']['window_s'] == 30.0 and r['coverage']['max_gap_s'] > 3
    assert cur.calls[1][1] == ('HYD-01', 'CE', 33.0)        # window + contract limit, the same asset and tag


def test_evaluate_judges_a_covered_window(monkeypatch):
    ws = NOW - timedelta(seconds=30)
    r, _ = run(monkeypatch, EVD, every(1, ws - timedelta(seconds=1), NOW))
    assert r['status'] == 'PASS' and r['passed'] is True and r['coverage']['covered']


def test_undeclared_evidence_is_judged_but_records_no_window_check(monkeypatch):
    plain = {k: v for k, v in EVD.items() if k not in ('tag', 'windowSeconds')}
    r, cur = run(monkeypatch, plain, [])
    assert r['status'] == 'PASS' and r['coverage'] is None and len(cur.calls) == 1


@pytest.mark.parametrize('bad', [{'tag': 'CE'}, {'windowSeconds': 30}, {'tag': 'CE', 'windowSeconds': 0}, {'tag': 'CE', 'windowSeconds': True}])
def test_half_or_invalid_window_declaration_is_invalid(monkeypatch, bad):
    e = {k: v for k, v in EVD.items() if k not in ('tag', 'windowSeconds')} | bad
    r, _ = run(monkeypatch, e, [])
    assert r['status'] == 'UNKNOWN' and r['reason'] == 'QUERY_ERROR' and r['error_kind'] == 'INVALID'


def test_every_seed_evidence_declares_the_tag_and_window_its_sql_reads():
    text = (ROOT / 'it/neo4j/v2/instances.cypher').read_text(encoding='utf-8')
    rows = re.findall(r"\['(evd:[^']+)',.*?name = \\'(\w+)\\' AND time > now\(\) - interval \\'(\d+) (seconds|minutes)\\''\s*,\s*'(\w+)'\s*,\s*(\d+)\]", text)
    assert len(rows) == 7
    for eid, sql_tag, n, unit, tag, window in rows:
        assert tag == sql_tag and int(window) == int(n) * (60 if unit == 'minutes' else 1), eid
