"""mcp-prom (read-only): data-trust check before reasoning (v3: '이상이면 추론을 보류하고 데이터 신뢰 불가 카드').

Despite the name this module does not query Prometheus (that is tools/prometheus.py, used by dmn-mcp's prometheus_*
tools). Sources: newest tag age in TimescaleDB (end-to-end freshness) + connect-ingest /healthz, whose `ok` is true only
while its MQTT leg and Kafka pump are both alive.
"""
import json
import os
import urllib.request

INGEST_URL = os.getenv("INGEST_URL", "http://connect-ingest:8093/healthz")
MAX_AGE_S = float(os.getenv("FRESHNESS_MAX_AGE_S", "60"))
# A107 (2026-10-07, agent RUN-0011): the newest row can carry a timestamp a few ms *after* the DB statement clock — plant-sim
# stamps the sample, the sink inserts it, and `now()` is read at a slightly different instant (rows were exactly 1 s apart, no
# row was future-dated, all container clocks equal; age_s came out -0.0). That is not stale data, so a small negative age is
# accepted; a timestamp further in the future than this skew is still a clock fault and reasoning stays withheld.
MAX_SKEW_S = float(os.getenv("FRESHNESS_MAX_SKEW_S", "2"))


def freshness(tsdb, asset: str) -> dict:
    value, age = tsdb.latest(asset, "TS1")
    ingest = None
    try:
        with urllib.request.urlopen(INGEST_URL, timeout=3) as r:
            ingest = json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        ingest = {"ok": False, "error": type(e).__name__}
    ok = age is not None and -MAX_SKEW_S <= age <= MAX_AGE_S and (ingest or {}).get("ok") is True
    if ok or (ingest or {}).get("ok") is not True:
        reason = None if ok else "ingest unavailable"
    elif age is None:
        reason = "no data"
    elif age < -MAX_SKEW_S:
        reason = f"data is future-dated by {-age:.1f} s (clock skew allowance {MAX_SKEW_S:g} s)"
    else:
        reason = f"data age is {age:.0f} s"
    return {"ok": ok, "age_s": None if age is None else round(age, 1), "max_age_s": MAX_AGE_S, "max_skew_s": MAX_SKEW_S,
            "latest_ts1": value, "ingest": ingest, "reason": reason}
