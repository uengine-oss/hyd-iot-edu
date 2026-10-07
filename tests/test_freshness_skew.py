"""A107 — data-trust check: a few ms of negative age (sample stamped just after the DB statement clock) is fresh data,
a timestamp beyond the skew allowance is a clock fault, and the stale/no-data verdicts are unchanged."""
import io
import json

import pytest

from agentsvc.tools import mcp_prom


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _TSDB:
    def __init__(self, age):
        self.age = age

    def latest(self, asset, name="TS1"):
        return (57.23, self.age)


@pytest.fixture(autouse=True)
def _ingest_ok(monkeypatch):
    monkeypatch.setattr(mcp_prom.urllib.request, "urlopen", lambda url, timeout=3: _Resp(json.dumps({"ok": True}).encode()))


@pytest.mark.parametrize("age, ok, reason_part", [
    (0.7, True, None),                       # the usual case (A090 evidence: 0.1–0.9 s)
    (-0.02, True, None),                     # RUN-0011: stamped a few ms after the statement clock → still fresh
    (-2.0, True, None),                      # at the allowance
    (-5.0, False, "future-dated by 5.0 s"),  # beyond the allowance → clock fault, reasoning withheld
    (61.0, False, "data age is 61 s"),       # stale, unchanged verdict
    (None, False, "no data"),
])
def test_small_negative_age_is_fresh_but_future_dated_data_is_not(age, ok, reason_part):
    out = mcp_prom.freshness(_TSDB(age), "HYD-01")
    assert out["ok"] is ok and out["max_skew_s"] == 2.0
    if reason_part:
        assert reason_part in out["reason"]
    else:
        assert out["reason"] is None


def test_ingest_failure_still_wins(monkeypatch):
    def boom(url, timeout=3):
        raise OSError("down")
    monkeypatch.setattr(mcp_prom.urllib.request, "urlopen", boom)
    out = mcp_prom.freshness(_TSDB(-0.02), "HYD-01")
    assert out["ok"] is False and out["reason"] == "ingest unavailable"
