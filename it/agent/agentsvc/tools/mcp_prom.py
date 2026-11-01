"""mcp-prom (read-only): data-trust check before reasoning (v3: '이상이면 추론을 보류하고 데이터 신뢰 불가 카드').

Despite the name this module does not query Prometheus (the `mcp_` prefix names the role — Prometheus is an optional
monitoring profile and no agent tool reads it). Sources: newest tag age in TimescaleDB (end-to-end freshness) + connect-ingest /healthz, whose `ok` is true only
while its MQTT leg and Kafka pump are both alive.
"""
import json
import os
import urllib.request

INGEST_URL = os.getenv("INGEST_URL", "http://connect-ingest:8093/healthz")
MAX_AGE_S = 60.0
# A107 (2026-10-07, agent RUN-0011): the newest row can carry a timestamp a few ms *after* the DB statement clock — plant-sim
# stamps the sample, the sink inserts it, and `now()` is read at a slightly different instant (rows were exactly 1 s apart, no
# row was future-dated, all container clocks equal; age_s came out -0.0). That is not stale data, so a small negative age is
# accepted; a timestamp further in the future than this skew is still a clock fault and reasoning stays withheld.
MAX_SKEW_S = 2.0


def freshness(tsdb, asset: str) -> dict:
    value, age = tsdb.latest(asset, "TS1")
    ingest = None
    try:
        with urllib.request.urlopen(INGEST_URL, timeout=3) as r:
            ingest = json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        ingest = {"ok": False, "error": type(e).__name__}
    ok = age is not None and -MAX_SKEW_S <= age <= MAX_AGE_S and (ingest or {}).get("ok") is True
    # 사유는 처리 기록 · 진단 결과에 그대로 보인다 — 학생이 읽는 말로(검진 G1-10)
    if ok:
        reason = None
    elif (ingest or {}).get("ok") is not True:
        reason = "설비 데이터 수집기(connect-ingest)가 정상이 아니라 최신 설비 값을 믿을 수 없습니다"
    elif age is None:
        reason = "이 설비의 유온(TS1) 값이 시계열 DB에 없습니다"
    elif age < -MAX_SKEW_S:
        reason = f"설비 값의 시각이 지금보다 {-age:.1f}초 앞서 있습니다(허용 {MAX_SKEW_S:g}초) — PC 시계를 확인하세요"
    else:
        reason = f"설비 값이 {age:.0f}초 전 것입니다(허용 {MAX_AGE_S:g}초) — 설비 시뮬레이터와 수집이 도는지 확인하세요"
    return {"ok": ok, "age_s": None if age is None else round(age, 1), "max_age_s": MAX_AGE_S, "max_skew_s": MAX_SKEW_S,
            "latest_ts1": value, "ingest": ingest, "reason": reason}
