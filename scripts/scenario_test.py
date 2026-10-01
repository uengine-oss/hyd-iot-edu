"""End-to-end scenario test against the running stack (v3 section 9 + negative cases).

    python scripts/scenario_test.py            # full run (~6 min at TIME_SCALE=20)
    python scripts/scenario_test.py --quick    # happy path only

Every step prints PASS/FAIL with the observed value; exit code 1 if anything failed.
"""
import argparse
import json
import sys
import time
import urllib.request
import urllib.error

H = "http://localhost"
PLANT, GATEWAY, DETECTOR, AGENT, PROCESS, INGEST, SINK = (f"{H}:8000", f"{H}:8090", f"{H}:8092", f"{H}:8091", f"{H}:8080", f"{H}:8093", f"{H}:8094")
ENT = f"{H}:8095"
results: list[tuple[str, bool, str]] = []


def get(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def post(url, data=None, timeout=10):
    req = urllib.request.Request(url, data=json.dumps(data or {}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()[:200]}


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}  {detail}", flush=True)
    return ok


def wait_for(desc, fn, timeout, every=1.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            v = fn()
            if v:
                return v, time.time() - t0
        except Exception:  # noqa: BLE001
            pass
        time.sleep(every)
    return None, time.time() - t0


def plant_unit(asset="HYD-01"):
    return get(f"{PLANT}/api/state")["units"][asset]


def det(asset="HYD-01"):
    return get(f"{DETECTOR}/api/detector/state")["assets"].get(asset, {})


def open_incident(alert_id):
    for inc in get(f"{PROCESS}/api/incidents"):
        if inc["alertId"] == alert_id and not inc["terminal"]:
            return inc
    return None


def section(title):
    print(f"\n== {title}", flush=True)


def happy_path(require_llm=False):
    section("0. 서비스 상태")
    for name, url in (("plant-sim", PLANT), ("cmd-gateway", GATEWAY), ("detector", DETECTOR), ("agent", AGENT),
                      ("process", PROCESS), ("connect-ingest", INGEST), ("connect-sink", SINK), ("enterprise-sim", ENT)):
        try:
            h = get(f"{url}/healthz")
            check(f"{name} healthy", h.get("ok"), json.dumps({k: v for k, v in h.items() if k in ("mqtt", "kafka", "neo4j", "db")}))
        except Exception as e:  # noqa: BLE001
            check(f"{name} healthy", False, str(e))

    section("1. 초기화 → 쿨러 열화 주입 (HYD-01)")
    post(f"{PLANT}/api/reset")
    time.sleep(2)
    u = plant_unit()
    check("PLC REMOTE_AUTO · RUN", u["status"]["mode"] == "REMOTE_AUTO" and u["status"]["state"] == "RUN", f"TS1={u['tags']['TS1']}")
    r = post(f"{PLANT}/api/fault", {"asset": "HYD-01", "type": "cooler_degradation"})
    check("fault injected", r.get("kind") == "cooler_degradation", json.dumps(r))

    section("2. L4 탐지 → alerts RAISE → OT 알람 중계")
    d, dt = wait_for("RAISE", lambda: det() if det().get("phase") == "RAISED" else None, 200)
    check("detector RAISED", d is not None, f"after {dt:.0f}s TS1={d and d.get('ts1')} CE={d and d.get('ce')} score={d and d.get('score')}")
    alert_id = d["alert_id"] if d else None
    gw = get(f"{GATEWAY}/healthz")
    check("cmd-gateway relayed alert to OT", gw.get("alerts_relayed", 0) >= 1, f"alerts_relayed={gw.get('alerts_relayed')}")

    section("3. L8 에이전트: 온톨로지 T1/T2 + 증거 → 가이드 카드")
    run, dt = wait_for("agent run", lambda: next((r for r in get(f"{AGENT}/api/agent/runs") if r["alertId"] == alert_id and r["status"] != "RUNNING"), None), 90)
    check("agent run finished", run is not None and run["status"] == "SUBMITTED", f"status={run and run['status']} after {dt:.0f}s")
    full = get(f"{AGENT}/api/agent/runs/{run['id']}") if run else {}
    steps = {s["name"]: s for s in full.get("steps", [])}
    check("freshness ok", steps.get("freshness", {}).get("output", {}).get("ok") is True, json.dumps(steps.get("freshness", {}).get("output", {}).get("age_s")))
    t1 = steps.get("t1_causes", {}).get("output", [])
    check("T1 returned 4 cause candidates", len(t1) == 4, str([c["causeId"] for c in t1]))
    card = full.get("card") or {}
    if require_llm:
        source = card.get("summarySource")
        check("real LLM summary (no template fallback)", bool(source) and source != "template", str(source))
    check("top cause = cooler fin fouling", card.get("topCause") == "cause:cooler-fin-fouling", f"scores={[(c['id'], c['score']) for c in card.get('causes', [])]}")
    codes = [a["code"] for a in card.get("recommended", [])]
    check("recommended FAN_BOOST, REDUCE_LOAD, COOLER_CLEAN_WO", codes == ["FAN_BOOST", "REDUCE_LOAD", "COOLER_CLEAN_WO"], str(codes))
    check("SOP steps + manual refs attached", any(s.get("manual") for a in card.get("recommended", []) for s in a["sop"]["steps"]), "")
    check("guardrail passed", steps.get("guardrail", {}).get("status") == "DONE", json.dumps(steps.get("guardrail", {}).get("output")))
    check("citations present", len(card.get("citations", [])) >= 8, f"{len(card.get('citations', []))} ids")
    ent_step = steps.get("enterprise", {}).get("output") or []
    check("L7→L8: ontology linked this alert to enterprise decision scenarios", {e["scenario"] for e in ent_step} >= {"고객 납기 vs 설비 보전", "교체 부품 구매: 구매단가 vs 전사 이익", "과열 구간 생산 로트: 규정 vs 납기"},
          str([(e["scenario"], e["status"], e["recommended"]) for e in ent_step]))

    section("4. L9 프로세스: 승인 → action.cmd → 게이트웨이 검증 → cmd/auto → PLC ACK")
    inc, dt = wait_for("incident", lambda: open_incident(alert_id), 30)
    check("incident AWAITING_APPROVAL", inc is not None and inc["state"] == "AWAITING_APPROVAL", f"{inc and inc['id']} {inc and inc['state']}")
    r = post(f"{PROCESS}/api/incidents/{inc['id']}/approve", {"approvedBy": "OP-17", "actions": [{"code": "FAN_BOOST", "fan_pct": 100}, {"code": "REDUCE_LOAD", "load_pct": 80}]})
    check("approve accepted", r.get("state") == "AWAITING_ACK", json.dumps(r.get("cmd", r))[:160])
    cmd_id = (r.get("cmd") or {}).get("cmdId")
    st, dt = wait_for("ACK", lambda: get(f"{PROCESS}/api/incidents/{inc['id']}") if get(f"{PROCESS}/api/incidents/{inc['id']}")["state"] in ("RE_OBSERVING", "ESCALATED") else None, 40)
    check("PLC ACK DONE → RE_OBSERVING", st is not None and st["state"] == "RE_OBSERVING", f"state={st and st['state']} ack={st and st.get('ack')} after {dt:.1f}s")
    log = get(f"{GATEWAY}/api/gateway/log")
    entry = next((e for e in log if e["cmdId"] == cmd_id), None)
    check("gateway decision PASS", entry is not None and entry["ok"], json.dumps(entry))
    u = plant_unit()
    check("PLC applied fan 100 / load 80", u["status"]["fan_pct"] == 100 and u["status"]["load_pct"] == 80, f"fan={u['status']['fan_pct']} load={u['status']['load_pct']} cmdId={u['status']['cmdId']}")

    section("5. 회복 → alerts CLEAR → 재관측 통과 → 작업지시 → 종결")
    d, dt = wait_for("CLEAR", lambda: det() if det().get("phase") == "IDLE" else None, 200)
    check("detector CLEAR (IDLE)", d is not None, f"after {dt:.0f}s TS1={d and d.get('ts1')}")
    fin, dt = wait_for("CLOSED", lambda: get(f"{PROCESS}/api/incidents/{inc['id']}") if get(f"{PROCESS}/api/incidents/{inc['id']}")["terminal"] else None, 120)
    check("incident CLOSED", fin is not None and fin["state"] == "CLOSED", f"state={fin and fin['state']} reason={fin and fin.get('reason')} after {dt:.0f}s")
    check("work order created", bool(fin and fin.get("workOrder")), json.dumps(fin and fin.get("workOrder")))
    hist = [h["state"] for h in (fin or {}).get("history", [])]
    check("history order", hist == ["GUIDE_RECEIVED", "AWAITING_APPROVAL", "CMD_ISSUED", "AWAITING_ACK", "ACKED", "RE_OBSERVING", "RESOLVED", "WORK_ORDER_CREATED", "CLOSED"], str(hist))
    return alert_id, cmd_id, inc["id"]


def enterprise_checks(inc_id):
    section("5b. L7 → L8 → L9: 경보에서 자동 기동된 전사 판단 → 역할 승인 → 기업 시스템 실행")
    post(f"{ENT}/api/reset")
    decs = [d for d in get(f"{PROCESS}/api/decisions") if (d.get("origin") or {}).get("incident") == inc_id]
    by = {(d.get("scenario") or {}).get("id"): d for d in decs}
    check("process received decisions for the incident", len(decs) >= 3, str([(k, v["state"], v["recommended"]) for k, v in by.items()]))
    d1 = get(f"{PROCESS}/api/decisions/{by['sc:delivery-vs-maintenance']['id']}")
    check("SC1 recommends derate + night cleaning (not stop, not continue)", d1["recommended"] == "opt:sc1-derate", d1["explanation"][:120])
    cont = next(o for o in d1["options"] if o["id"] == "opt:sc1-continue")
    check("SC1 'continue' excluded by HARD policy 65 ℃", not cont["feasible"] and cont["violations"][0]["policy"] == "pol:ts1-limit", "")
    check("SC1 maintenance dept prefers a different option", d1["winners"].get("dept:maintenance") != d1["recommended"], json.dumps(d1["winners"], ensure_ascii=False))
    r = post(f"{PROCESS}/api/decisions/{d1['id']}/approve", {"option": "opt:sc1-stop", "by": "OP-17", "role": "role:operator"})
    check("operator may not approve a plant stop (needs 공장장)", r.get("error") == 403, r.get("body", "")[:100])
    r = post(f"{PROCESS}/api/decisions/{d1['id']}/approve", {"option": "opt:sc1-derate", "by": "이생산", "role": "role:prod-mgr"})
    ex = {x["skill"]: x for x in r.get("executions", [])}
    check("approved → CMMS work order executed, PLC part left to HITL", r.get("state") == "EXECUTED" and ex.get("skill:schedule-maintenance", {}).get("status") == "DONE"
          and ex.get("skill:cooling-adjust", {}).get("status") == "VIA_HITL", json.dumps({k: v["status"] for k, v in ex.items()}))
    d2 = get(f"{PROCESS}/api/decisions/{by['sc:part-procurement']['id']}")
    check("SC2 enterprise picks OEM while purchasing prefers the cheap supplier",
          d2["recommended"] == "opt:sc2-b" and d2["winners"].get("dept:purchasing") == "opt:sc2-a" and d2["naiveWinners"].get("dept:purchasing") == "opt:sc2-c", "")
    r = post(f"{PROCESS}/api/decisions/{d2['id']}/approve", {"option": "opt:sc2-b", "by": "박공장장", "role": "role:plant-mgr"})
    tx = get(f"{ENT}/api/transactions")
    check("ERP purchase request + CMMS work order in enterprise systems", {t["system"] for t in tx} >= {"sys:erp", "sys:cmms"}, str([(t["system"], t["ref"]) for t in tx]))
    audit = [a["event"] for a in get(f"{PROCESS}/api/audit")]
    check("audit has DECISION_SUBMITTED/DENIED/APPROVED/SKILL_EXECUTED", {"DECISION_SUBMITTED", "DECISION_DENIED", "DECISION_APPROVED", "SKILL_EXECUTED"} <= set(audit), "")
    import subprocess
    time.sleep(2)
    out = subprocess.run(["docker", "compose", "exec", "-T", "neo4j", "cypher-shell", "-u", "neo4j", "-p", "hydpass123", "--format", "plain",
                          f"MATCH (x:Decision {{id: '{d1['id']}'}})-[:DECIDED]->(o:Option) MATCH (x)-[:FOR]->(i:Incident) RETURN o.id, i.id"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    check("decision case written to the ontology (Decision -DECIDED-> Option, -FOR-> Incident)", "opt:sc1-derate" in out, out.strip().splitlines()[-1] if out.strip() else "")


def knowledge_admin_checks():
    section("5c. 지식 관리 (L9 → L7): 스킬 카탈로그 · 매뉴얼 인제스천 · HITL 선례 환류")
    import base64
    from pathlib import Path
    skills = get(f"{PROCESS}/api/kg/skills", timeout=20)
    check("skill catalog lists 8+ skills with description and detail", len(skills) >= 8 and all(k.get("description") and k.get("detail") for k in skills[:8]),
          str([k["name"] for k in skills][:4]))
    pk = next((k for k in skills if k["id"] == "skill:procure-part"), {})
    check("skill shows system · approver · policy from the ontology", (pk.get("system") or {}).get("id") == "sys:erp" and (pk.get("approver") or {}).get("id") == "role:purchasing-mgr"
          and any(p["id"] == "pol:avl" for p in pk.get("policies", [])), "")
    sample = Path(__file__).resolve().parents[1] / "docs" / "samples" / "HM-8_cooler-fan-manual.md"
    pv = post(f"{PROCESS}/api/kg/manuals/preview", {"filename": sample.name, "data": base64.b64encode(sample.read_bytes()).decode()}, timeout=30)
    check("manual preview: 2 sections, 2 SOPs, 8 steps", len(pv.get("sections", [])) == 2 and sum(p["stepCount"] for p in pv.get("procedures", [])) == 8,
          str([(p["id"], p.get("suggestedAction")) for p in pv.get("procedures", [])]))
    out = post(f"{PROCESS}/api/kg/manuals/commit", dict(pv, by="scenario_test"), timeout=30)
    check("manual committed to the ontology", out.get("procedures") == 2 and out.get("steps") == 8, json.dumps(out, ensure_ascii=False))
    d = post(f"{AGENT}/api/agent/decide", {"scenario": "sc:delivery-vs-maintenance", "asset": "HYD-01"}, timeout=60)
    prec = next((s_["output"] for s_ in d.get("steps", []) if s_["name"] == "precedents"), None)
    check("next decision reads the human precedent written in 5b", isinstance(prec, dict) and prec.get("opt:sc1-derate", {}).get("n", 0) >= 1,
          json.dumps(prec, ensure_ascii=False)[:160])


def db_checks(alert_id, cmd_id, inc_id):
    section("6. L5 저장소 확인 (TimescaleDB via docker exec)")
    import subprocess
    def q(sql):
        out = subprocess.run(["docker", "compose", "exec", "-T", "timescaledb", "psql", "-U", "hyd", "-d", "hyd", "-At", "-c", sql],
                             capture_output=True, text=True, cwd=__file__.rsplit("scripts", 1)[0])
        return out.stdout.strip()
    check("alerts row RAISE→CLEAR", "CLEAR" in q(f"SELECT state FROM alerts WHERE alert_id='{alert_id}'"), q(f"SELECT state, raised_at, cleared_at FROM alerts WHERE alert_id='{alert_id}'"))
    check("actions row with ACK DONE", "DONE" in q(f"SELECT ack_result FROM actions WHERE cmd_id='{cmd_id}'"), q(f"SELECT cmd_id, ack_result, approved_by FROM actions WHERE cmd_id='{cmd_id}'"))
    n = q(f"SELECT count(*) FROM audit WHERE incident='{inc_id}'")
    check("audit rows for incident", n.isdigit() and int(n) >= 6, f"{n} rows")
    check("feat_1s has anomaly scores", (q("SELECT count(*) FROM feat_1s WHERE sensor='TS1' AND score > 0.5") or "0").isdigit() and int(q("SELECT count(*) FROM feat_1s WHERE sensor='TS1' AND score > 0.5")) > 0, "")


def negative_manual_mode():
    section("7. 부정 시나리오: REMOTE_MANUAL 모드에서는 게이트웨이가 거부 → 에스컬레이션")
    post(f"{PLANT}/api/reset")
    time.sleep(2)
    post(f"{PLANT}/api/mode", {"asset": "HYD-02", "mode": "REMOTE_MANUAL"})
    post(f"{PLANT}/api/fault", {"asset": "HYD-02", "type": "cooler_degradation"})
    d, dt = wait_for("RAISE HYD-02", lambda: det("HYD-02") if det("HYD-02").get("phase") == "RAISED" else None, 200)
    check("HYD-02 RAISED", d is not None, f"after {dt:.0f}s")
    alert_id = d["alert_id"] if d else None
    inc, dt = wait_for("incident HYD-02", lambda: open_incident(alert_id), 90)
    check("incident for HYD-02", inc is not None, f"{inc and inc['id']}")
    r = post(f"{PROCESS}/api/incidents/{inc['id']}/approve", {"approvedBy": "OP-17", "actions": [{"code": "FAN_BOOST", "fan_pct": 100}]})
    cmd_id = (r.get("cmd") or {}).get("cmdId")
    log, dt = wait_for("gateway reject", lambda: next((e for e in get(f"{GATEWAY}/api/gateway/log") if e["cmdId"] == cmd_id), None), 20)
    check("gateway REJECTED with MODE", log is not None and not log["ok"] and log["check"] == "MODE", json.dumps(log))
    fin, dt = wait_for("escalation", lambda: get(f"{PROCESS}/api/incidents/{inc['id']}") if get(f"{PROCESS}/api/incidents/{inc['id']}")["terminal"] else None, 60)
    check("incident ESCALATED (ACK_TIMEOUT)", fin is not None and fin["state"] == "ESCALATED" and fin.get("reason") == "ACK_TIMEOUT", f"{fin and fin['state']} {fin and fin.get('reason')} after {dt:.0f}s")
    audit = get(f"{PROCESS}/api/audit")
    check("process audit has ACK_TIMEOUT", any(a["event"] == "ACK_TIMEOUT" and a["incident"] == inc["id"] for a in audit), "")
    import subprocess
    out = subprocess.run(["docker", "compose", "exec", "-T", "timescaledb", "psql", "-U", "hyd", "-d", "hyd", "-At", "-c",
                          f"SELECT detail->>'check' FROM audit WHERE event='CMD_REJECTED' AND detail->>'cmdId'='{cmd_id}'"],
                         capture_output=True, text=True, cwd=__file__.rsplit("scripts", 1)[0]).stdout.strip()
    check("Kafka audit → TimescaleDB has cmd-gateway CMD_REJECTED", out == "MODE", f"check={out!r}")
    post(f"{PLANT}/api/fault", {"asset": "HYD-02", "type": "restore", "ramp_sim_s": 30})
    post(f"{PLANT}/api/mode", {"asset": "HYD-02", "mode": "REMOTE_AUTO"})


def negative_trip():
    section("8. 부정 시나리오: 조치 없이 방치 → 65 ℃ 인터록 트립 → OVERHEAT_TRIP → RESET")
    post(f"{PLANT}/api/reset")
    time.sleep(2)
    post(f"{PLANT}/api/fault", {"asset": "HYD-03", "type": "cooler_degradation", "target_health": 0.3, "ramp_sim_s": 60})
    u, dt = wait_for("TRIP", lambda: plant_unit("HYD-03") if plant_unit("HYD-03")["status"]["state"] == "TRIP" else None, 240)
    check("PLC tripped at >65 C", u is not None and u["status"]["trip"] == "OVERTEMP", f"after {dt:.0f}s TS1={u and u['tags']['TS1']}")
    d, dt = wait_for("trip alert", lambda: det("HYD-03") if det("HYD-03").get("tripped") else None, 30)
    check("detector OVERHEAT_TRIP alert", d is not None, "")
    r = post(f"{PLANT}/api/manual", {"asset": "HYD-03", "writes": {"Reset": 1}})
    check("RESET rejected while hot", r.get("result") == "REJECTED" and r.get("reason") == "RESET_TOO_HOT", json.dumps(r))
    post(f"{PLANT}/api/fault", {"asset": "HYD-03", "type": "restore", "ramp_sim_s": 30})
    u, dt = wait_for("cool", lambda: plant_unit("HYD-03") if plant_unit("HYD-03")["tags"]["TS1"] < 55 else None, 200)
    r = post(f"{PLANT}/api/manual", {"asset": "HYD-03", "writes": {"Reset": 1}})
    check("RESET accepted below 55 C", r.get("result") == "DONE", json.dumps(r))
    post(f"{PLANT}/api/mode", {"asset": "HYD-03", "mode": "REMOTE_AUTO"})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--require-llm", action="store_true", help="fail if the card uses the template fallback")
    args = ap.parse_args()
    t0 = time.time()
    alert_id, cmd_id, inc_id = happy_path(require_llm=args.require_llm)
    enterprise_checks(inc_id)
    knowledge_admin_checks()
    if not args.quick:
        db_checks(alert_id, cmd_id, inc_id)
        negative_manual_mode()
        negative_trip()
    post(f"{PLANT}/api/reset")
    failed = [r for r in results if not r[1]]
    print(f"\n{'ALL PASS' if not failed else str(len(failed)) + ' FAILED'} — {len(results) - len(failed)}/{len(results)} checks in {time.time() - t0:.0f}s")
    for name, ok, detail in failed:
        print("  FAILED:", name, detail)
    sys.exit(1 if failed else 0)
