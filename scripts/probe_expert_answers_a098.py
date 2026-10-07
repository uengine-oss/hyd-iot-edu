"""A098 — the three expert questions (docs/expert-questions-a079.md) answered from industry sources and loaded through the
product paths: knowledge_a098.cypher (seed, applied live) and the real manual ingestion of HM-9 (oil degradation manual:
agent extraction → reviewed commit linking SOP-OIL-21 to fm:oil-degradation).

    .venv314/Scripts/python scripts/probe_expert_answers_a098.py .evidence/reaudit/a098-expert-<n>

Live: process :8080, a host worker (Claude Code), Neo4j. Checks are written before the run.
"""
import base64
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
import urllib.error
import urllib.request

PROCESS = "http://127.0.0.1:8080"
FIXTURE = Path(__file__).resolve().parents[1] / "tests/fixtures/manuals/HM-9_oil-degradation-manual.md"


def http(path, data=None):
    req = urllib.request.Request(PROCESS + path, data=None if data is None else json.dumps(data, ensure_ascii=False).encode(), headers={"Content-Type": "application/json"},
                                 method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}


def cypher(q):
    r = subprocess.run(["docker", "exec", "hyd-iot-edu-neo4j-1", "cypher-shell", "-u", "neo4j", "-p", "hydpass123", "--format", "plain", q],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return [l for l in r.stdout.strip().splitlines()[1:] if l.strip()]


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=False)
    report = {"started": datetime.now(timezone.utc).isoformat(), "checks": []}
    def save(n, v): (out / (n + ".json")).write_text(json.dumps(v, ensure_ascii=False, indent=2, default=str), encoding="utf8")
    def check(name, ok, detail=None):
        report["checks"].append({"name": name, "passed": bool(ok), "detail": detail}); save("result", report)
        print(("PASS " if ok else "FAIL ") + name, json.dumps(detail, ensure_ascii=False, default=str)[:220] if detail is not None else "", flush=True)
    # Q1: flow now reaches a performance measure
    rows = cypher("MATCH (s:Sensor {id:'sen:fs1'})-[:OBSERVES]->(:StateVariable)-[:INFLUENCES*1..4]->(m:Measure) RETURN DISTINCT m.id;")
    check("q1_flow_sensor_reaches_throughput", any("msr:throughput" in r for r in rows), rows)
    # Q3: trips are failure modes with patterns, reset skills, and a cause through the preceding failure
    rows = cypher("MATCH (p:AnomalyPattern) WHERE p.code IN ['LOW_PRESSURE_TRIP','HIGH_VIBRATION_TRIP'] MATCH (p)-[:DETECTS]->(sy:Symptom)-[:INDICATES]->(f:FailureMode)-[:MITIGATED_BY]->(k:Skill) RETURN p.code, f.id, k.id;")
    check("q3_both_trips_have_pattern_failure_mode_and_reset_skill", len(rows) >= 2, rows)
    rows = cypher("MATCH (c:Cause)-[:CAUSES]->(:FailureMode)-[:LEADS_TO]->(f:FailureMode) WHERE f.id IN ['fm:low-pressure-trip','fm:high-vibration-trip','fm:overheat-trip'] RETURN f.id, count(c);")
    check("q3_every_trip_has_a_cause_through_its_preceding_failure", len(rows) == 3, rows)
    rows = cypher("MATCH (r:Rule {id:'rule:cand-trip'}) RETURN r.when;")
    check("overheat_reset_card_is_now_limited_to_the_overheat_trip", any("OVERHEAT_TRIP" in r for r in rows), rows)
    # Q2 part 1: causes / symptom / pattern / dx rule from the seed
    rows = cypher("MATCH (c:Cause)-[:CAUSES]->(f:FailureMode {id:'fm:oil-degradation'}) RETURN c.id, c.prior ORDER BY c.prior DESC;")
    check("q2_oil_degradation_has_four_causes_with_priors", len(rows) == 4, rows)
    rows = cypher("MATCH (p:AnomalyPattern {code:'OIL_ANALYSIS'})-[:DETECTS]->(s:Symptom)-[:INDICATES]->(f:FailureMode {id:'fm:oil-degradation'}) MATCH (r:Rule {id:'rule:dx-oil'})-[:OUTPUTS]->(c:Cause) RETURN s.id, count(c);")
    check("q2_oil_analysis_symptom_pattern_and_diagnosis_rule", bool(rows), rows)
    # Q2 part 2: the oil manual through the real ingestion path (agent extraction → reviewed commit)
    before = cypher("MATCH (k:Skill {sopId:'SOP-OIL-21'}) RETURN k.id;")
    if before:
        check("q2_sop_oil_21_already_in_graph_skipping_ingestion", True, before)
    else:
        s, up = http("/api/kg/manuals/preview", {"filename": FIXTURE.name, "data": base64.b64encode(FIXTURE.read_bytes()).decode()}); assert s == 200, up
        root = "/api/kg/manuals/sources/" + up["source_id"]
        s, inst = http(root + "/extractions", {"request_id": str(uuid.uuid4())}); assert s == 200, inst
        pid = inst["instance"]; t0 = time.monotonic(); res = None
        while time.monotonic() - t0 < 1500:
            s, res = http(root + "/extractions/" + pid)
            if s == 200 and res["status"] in ("DONE", "FAILED", "CANCELLED", "PENDING") and (res.get("preview") or res["status"] != "DONE"):
                break
            time.sleep(5)
        save("extraction", res)
        pv = res.get("preview") or {}
        procs = {p["id"]: p for p in pv.get("procedures", [])}
        check("q2_agent_extracted_sop_oil_21_with_six_steps", "SOP-OIL-21" in procs and len(procs["SOP-OIL-21"]["steps"]) == 6, {"status": res.get("status"), "elapsed_s": round(time.monotonic() - t0, 1), "procs": {k: len(v["steps"]) for k, v in procs.items()}})
        links = {"SOP-OIL-21": {"failureMode": "fm:oil-degradation", "relation": "REMEDIED_BY", "kind": "work_order", "approver": "role:maint-mgr",
                                "affects": [{"target": "msr:oil-life", "sign": "+", "note": "A098: 작동유 교환으로 잔여 수명 회복"},
                                            {"target": "msr:maint-cost", "sign": "+", "note": "A098: 교환 작업비"}]}}
        for pid_, p in procs.items():                                            # the prose procedure of HM-9.2 (registration id) is an inspection: link as MITIGATED_BY
            if pid_ != "SOP-OIL-21":
                links[pid_] = {"failureMode": "fm:oil-degradation", "relation": "MITIGATED_BY", "kind": "work_order", "approver": "role:maint-mgr",
                               "affects": [{"target": "msr:oil-life", "sign": "+", "note": "A098: 점검으로 열화 진행을 늦춘다"}]}
        body = dict(pv, reviewed=True, by="A098 (업계 자료로 정한 답)", links=links)
        s, receipt = http("/api/kg/manuals/commit", body); save("commit-receipt", receipt)
        check("q2_reviewed_commit_links_the_oil_sop_to_the_failure_mode", s == 200 and receipt.get("procedures", 0) >= 1, {"status": s, "receipt": {k: receipt.get(k) for k in ("batch", "procedures", "candidate_activation", "detail")}})
    rows = cypher("MATCH (f:FailureMode {id:'fm:oil-degradation'})-[:REMEDIED_BY|MITIGATED_BY]->(k:Skill)-[:HAS_STEP]->(st:Step)-[:REFERS_TO]->(:ManualSection)-[:PART_OF]->(:KnowledgeSource) RETURN k.id, count(st);")
    check("q2_oil_degradation_now_has_a_traceable_remedy", bool(rows), rows)
    report["finished"] = datetime.now(timezone.utc).isoformat(); save("result", report)
    print("checks passed", sum(c["passed"] for c in report["checks"]), "/", len(report["checks"]), flush=True)


if __name__ == "__main__":
    main()
