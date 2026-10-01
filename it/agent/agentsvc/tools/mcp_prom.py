"""mcp-prom (read-only): data-trust check before reasoning (v3: '이상이면 추론을 보류하고 데이터 신뢰 불가 카드').

Sources: newest tag age in TimescaleDB (end-to-end freshness) + connect-ingest /healthz (queue depth, lag).
"""
import json
import os
import urllib.request

INGEST_URL = os.getenv("INGEST_URL", "http://connect-ingest:8093/healthz")
MAX_AGE_S = float(os.getenv("FRESHNESS_MAX_AGE_S", "60"))


def freshness(tsdb, asset: str) -> dict:
    value, age = tsdb.latest(asset, "TS1")
    ingest = None
    try:
        with urllib.request.urlopen(INGEST_URL, timeout=3) as r:
            ingest = json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        ingest = {"ok": False, "error": type(e).__name__}
    ok = age is not None and 0 <= age <= MAX_AGE_S and (ingest or {}).get("ok") is True
    return {"ok": ok, "age_s": None if age is None else round(age, 1), "max_age_s": MAX_AGE_S, "latest_ts1": value,
            "ingest": ingest, "reason": None if ok else ("ingest unavailable" if (ingest or {}).get("ok") is not True
                        else "no data" if age is None else f"data age is {age:.0f} s")}
