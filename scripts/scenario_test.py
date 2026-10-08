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

    section("3. L8 에이전트: 온톨로지 v2 T1/T2 + 증거 → 가이드 카드 → 조치 카드(스킬 = SOP)")
    run, dt = wait_for("agent run", lambda: next((r for r in get(f"{AGENT}/api/agent/runs") if r["alertId"] == alert_id and r["status"] != "RUNNING"), None), 90)
    check("agent run finished", run is not None and run["status"] == "SUBMITTED", f"status={run and run['status']} after {dt:.0f}s")
    full = get(f"{AGENT}/api/agent/runs/{run['id']}") if run else {}
    steps = {s["name"]: s for s in full.get("steps", [])}
    check("freshness ok", steps.get("freshness", {}).get("output", {}).get("ok") is True, json.dumps(steps.get("freshness", {}).get("output", {}).get("age_s")))
    t1 = steps.get("t1_causes", {}).get("output", [])
    check("T1 returned the cooling-loss causes (fin fouling, high ambient)", {c["causeId"] for c in t1} == {"cause:cooler-fin-fouling", "cause:high-ambient"}, str([c["causeId"] for c in t1]))
    card = full.get("card") or {}
    if require_llm:
        source = card.get("summarySource")
        check("real LLM summary (no template fallback)", bool(source) and source != "template", str(source))
    check("top cause = cooler fin fouling (failure mode cooling loss)", card.get("topCause") == "cause:cooler-fin-fouling" and card.get("failureMode") == "fm:cooling-loss",
          f"scores={[(c['id'], c['score']) for c in card.get('causes', [])]}")
    codes = [a["code"] for a in card.get("recommended", [])]
    check("guide card actions = atomic actions of the SOP skills (FAN_SET, LOAD_SET, WO_CREATE)", codes == ["FAN_SET", "LOAD_SET", "WO_CREATE"], str(codes))
    check("SOP skills of the failure mode on the card", [k["sopId"] for k in card.get("skills", [])] == ["SOP-COOL-01", "SOP-COOL-02", "SOP-COOL-03", "SOP-COOL-04"],
          str([k["sopId"] for k in card.get("skills", [])]))
    check("SOP steps + manual refs attached", any(s.get("manual") for a in card.get("recommended", []) for s in a["sop"]["steps"]), "")
    check("guardrail passed", steps.get("guardrail", {}).get("status") == "DONE", json.dumps(steps.get("guardrail", {}).get("output")))
    check("citations present", len(card.get("citations", [])) >= 8, f"{len(card.get('citations', []))} ids")
    cs = steps.get("cards", {}).get("output") or {}
    check("action cards submitted: 3 SOP cards, SOP-COOL-02 recommended", cs.get("status") == "SUBMITTED" and cs.get("recommended") == "skill:fan-max-derate"
          and len(cs.get("cards", [])) == 3, json.dumps(cs, ensure_ascii=False)[:200])

    section("4. HITL: 사람이 카드 하나 선택 → 역할 권한 → action.cmd → 게이트웨이 검증 → cmd/auto → PLC ACK")
    inc, dt = wait_for("incident", lambda: open_incident(alert_id), 30)
    check("incident AWAITING_APPROVAL", inc is not None and inc["state"] == "AWAITING_APPROVAL", f"{inc and inc['id']} {inc and inc['state']}")
    dec = next((d for d in get(f"{PROCESS}/api/decisions") if (d.get("origin") or {}).get("incident") == inc["id"]), None)
    check("process holds the action-card decision for the incident", dec is not None and dec["state"] == "PENDING_APPROVAL", json.dumps(dec, ensure_ascii=False)[:160])
    r = post(f"{PROCESS}/api/incidents/{inc['id']}/decide", {"decision": dec["id"], "option": "skill:fan-max-derate", "by": "[회귀 검사] 운전원", "role": "role:operator", "reason": "[회귀 검사] 권한 밖 승인 시도"})
    check("operator may not choose SOP-COOL-02 (needs 생산관리자)", r.get("error") == 403, r.get("body", "")[:100])
    r = post(f"{PROCESS}/api/incidents/{inc['id']}/decide", {"decision": dec["id"], "option": "skill:fan-max-derate", "by": "이생산", "role": "role:prod-mgr",
                                                             "reason": "[회귀 검사] OEM 납기 오더 진행 중 — 생산을 멈추지 않고 유온을 확실히 내린다"})
    check("decision accepted → command issued", (r.get("incident") or {}).get("state") == "AWAITING_ACK", json.dumps(r.get("cmd"), ensure_ascii=False)[:160])
    cmd_id = (r.get("cmd") or {}).get("cmdId")
    st, dt = wait_for("ACK", lambda: get(f"{PROCESS}/api/incidents/{inc['id']}") if get(f"{PROCESS}/api/incidents/{inc['id']}")["state"] in ("RE_OBSERVING", "ESCALATED") else None, 40)
    check("PLC ACK DONE → RE_OBSERVING", st is not None and st["state"] == "RE_OBSERVING", f"state={st and st['state']} ack={st and st.get('ack')} after {dt:.1f}s")
    log = get(f"{GATEWAY}/api/gateway/log")
    entry = next((e for e in log if e["cmdId"] == cmd_id), None)
    check("gateway decision PASS (FAN_SET · LOAD_SET whitelisted)", entry is not None and entry["ok"], json.dumps(entry))
    u = plant_unit()
    check("PLC applied fan 100 / load 80", u["status"]["fan_pct"] == 100 and u["status"]["load_pct"] == 80, f"fan={u['status']['fan_pct']} load={u['status']['load_pct']} cmdId={u['status']['cmdId']}")

    section("5. 회복 → alerts CLEAR → 재관측 통과 → 작업지시 → 종결")
    d, dt = wait_for("CLEAR", lambda: det() if det().get("phase") == "IDLE" else None, 200)
    check("detector CLEAR (IDLE)", d is not None, f"after {dt:.0f}s TS1={d and d.get('ts1')}")
    fin, dt = wait_for("CLOSED", lambda: get(f"{PROCESS}/api/incidents/{inc['id']}") if get(f"{PROCESS}/api/incidents/{inc['id']}")["terminal"] else None, 120)
    check("incident CLOSED", fin is not None and fin["state"] == "CLOSED", f"state={fin and fin['state']} reason={fin and fin.get('reason')} after {dt:.0f}s")
    check("work order created", bool(fin and fin.get("workOrder")), json.dumps(fin and fin.get("workOrder")))
    from datetime import datetime
    from pathlib import Path
    transactions = get(f"{ENT}/api/transactions")
    actual = next((row for row in transactions if row.get('decision') == dec['id'] and row.get('skill') == 'skill:schedule-maintenance'), None)
    check('Incident work order matches the actual CMMS receipt', bool(actual and fin and fin.get('workOrder', {}).get('id') == actual['ref']), json.dumps(actual, ensure_ascii=False))
    ordered = bool(actual and fin and fin.get('closed') and datetime.fromisoformat(fin['closed'].replace('Z','+00:00')) >= datetime.fromisoformat(actual['t'].replace('Z','+00:00')))
    check('Incident closes after the actual CMMS commit', ordered, f"closed={fin and fin.get('closed')} cmms={actual and actual['t']}")
    evidence = Path('.evidence/reaudit/legacy-receipts'); evidence.mkdir(parents=True, exist_ok=True)
    (evidence/f"{inc['id']}.json").write_text(json.dumps({'incident':fin,'cmms':actual,'close_after_commit':ordered},ensure_ascii=False,indent=2),encoding='utf-8')
    hist = [h["state"] for h in (fin or {}).get("history", [])]
    check("history order", hist == ["GUIDE_RECEIVED", "AWAITING_APPROVAL", "CMD_ISSUED", "AWAITING_ACK", "ACKED", "RE_OBSERVING", "RESOLVED", "WORK_ORDER_CREATED", "CLOSED"], str(hist))
    return alert_id, cmd_id, inc["id"]


def enterprise_checks(inc_id):
    section("5b. L7 → L8 → L9: 판단 사례 기록 → 다음 판단의 선례 · DMN 규칙(온도 · 압력 · 운전 모드 · 트립) 반응")
    import subprocess
    post(f"{ENT}/api/reset")
    dec = next((d for d in get(f"{PROCESS}/api/decisions") if (d.get("origin") or {}).get("incident") == inc_id), None)
    d = get(f"{PROCESS}/api/decisions/{dec['id']}") if dec else {}
    ex = {x.get("code"): x for x in d.get("executions", [])}
    check("decision EXECUTED, PLC commands left to the HITL incident", d.get("state") == "EXECUTED" and ex.get("FAN_SET", {}).get("status") == "VIA_HITL"
          and ex.get("LOAD_SET", {}).get("status") == "VIA_HITL", json.dumps({k: v["status"] for k, v in ex.items()}))
    time.sleep(2)
    out = subprocess.run(["docker", "compose", "exec", "-T", "neo4j", "cypher-shell", "-u", "neo4j", "-p", "hydpass123", "--format", "plain",
                          f"MATCH (x:DecisionCase {{id: 'case:{dec['id']}'}})-[:CHOSE]->(s:Skill) MATCH (x)-[:FOR_INCIDENT]->(i:Incident)-[:DIAGNOSED_AS]->(c:Cause) RETURN s.sopId, i.id, c.id"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    check("decision case written to the ontology (DecisionCase -CHOSE-> Skill, -FOR_INCIDENT-> Incident -DIAGNOSED_AS-> Cause)", "SOP-COOL-02" in out and inc_id in out,
          out.strip().splitlines()[-1] if out.strip() else "")
    nd = post(f"{AGENT}/api/agent/decide", {"asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "facts": {"cause": "cause:cooler-fin-fouling"}}, timeout=60)
    rec = next((o for o in (nd.get("result") or {}).get("options", []) if o["id"] == "skill:fan-max-derate"), {})
    check("next decision reads the human precedent (same failure mode)", (rec.get("precedent") or {}).get("n", 0) >= 2, json.dumps(rec.get("precedent"), ensure_ascii=False))
    temp = next((o for o in (nd.get("result") or {}).get("options", []) if o["id"] == "skill:fan-max"), {})
    check("DMN temperature rule: forecast 55.4 ℃ ≥ 55 → WARN on SOP-COOL-01", any(w["rule"] == "rule:ts1-warn" for w in temp.get("warnings", [])), "")
    m = post(f"{AGENT}/api/agent/decide", {"asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "facts": {"cause": "cause:cooler-fin-fouling", "plc_mode": "REMOTE_MANUAL"}}, timeout=60)
    check("DMN mode rule: REMOTE_MANUAL excludes every control card", (m.get("result") or {}).get("recommended") is None
          and all(not o["feasible"] for o in (m.get("result") or {}).get("options", [])), (m.get("result") or {}).get("explanation", "")[:120])
    tr = post(f"{AGENT}/api/agent/decide", {"asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "facts": {"cause": "cause:cooler-fin-fouling", "plc_state": "TRIP"}}, timeout=60)
    check("DMN trip rule: in TRIP only SOP-TRIP-01 (reset after cooling) remains", (tr.get("result") or {}).get("recommended") == "skill:reset-after-cool", "")
    pu = post(f"{AGENT}/api/agent/decide", {"asset": "HYD-01", "pattern": "PUMP_LEAKAGE", "facts": {"cause": "cause:pump-seal-wear"}}, timeout=60)
    po = {o["id"]: o for o in (pu.get("result") or {}).get("options", [])}
    check("pump leakage: pressure raise excluded, standby pump recommended, low-pressure forecast warned",
          (pu.get("result") or {}).get("recommended") == "skill:switch-standby-pump" and not po.get("skill:raise-pressure", {}).get("feasible", True)
          and any(w["rule"] == "rule:ps1-warn" for w in po.get("skill:derate-70", {}).get("warnings", [])), (pu.get("result") or {}).get("explanation", "")[:140])


def knowledge_admin_checks():
    section("5c. 지식 관리 (L9 → L7): 스킬(SOP) 카탈로그 · 고장 유형 매칭 · 매뉴얼 인제스천")
    import base64
    from pathlib import Path
    skills = get(f"{PROCESS}/api/kg/skills", timeout=20)
    check("skill catalog lists 14+ SOP skills, each with steps and a failure mode", len(skills) >= 14 and all(k.get("sopId") and k.get("steps") and k.get("failureModes") for k in skills),
          str([k["sopId"] for k in skills][:5]))
    sk = next((k for k in skills if k["id"] == "skill:fan-max-derate"), {})
    check("skill shows approver · atomic actions · DMN rules from the ontology", (sk.get("approver") or {}).get("id") == "role:prod-mgr"
          and {a["code"] for a in sk.get("actions", [])} == {"FAN_SET", "LOAD_SET"} and any(r["effect"] == "SELECT" for r in sk.get("rules", [])), "")
    bad = post(f"{PROCESS}/api/kg/skills", {"name": "x", "sopId": "SOP-X-01", "steps": "a", "failureMode": ""})
    check("a new skill without a failure mode is refused", bad.get("error") == 400, bad.get("body", "")[:80])
    dup = post(f"{PROCESS}/api/kg/skills", {"name": "x", "sopId": "SOP-COOL-01", "steps": "a", "failureMode": "fm:cooling-loss"})
    check("an SOP number another skill owns is refused", dup.get("error") == 409, dup.get("body", "")[:80])
    sample = Path(__file__).resolve().parents[1] / "docs" / "samples" / "HM-8_cooler-fan-manual.md"
    import uuid
    suffix = uuid.uuid4().hex[:8].upper()
    raw = sample.read_text(encoding='utf-8').replace('SOP-FAN-11', 'SOP-TEST-' + suffix + '-11').replace('SOP-FAN-12', 'SOP-TEST-' + suffix + '-12').encode()
    pv = post(f"{PROCESS}/api/kg/manuals/preview", {"filename": 'scenario-' + sample.name, "data": base64.b64encode(raw).decode()}, timeout=30)
    check("manual preview: 2 sections, 2 SOPs, 8 steps", len(pv.get("sections", [])) == 2 and sum(p["stepCount"] for p in pv.get("procedures", [])) == 8,
          str([(p["id"], p.get("suggestedFailureMode")) for p in pv.get("procedures", [])]))
    links = {p["id"]: {"failureMode": "fm:bearing-degradation", "relation": "REMEDIED_BY", "kind": "work_order"} for p in pv.get("procedures", [])}
    out = post(f"{PROCESS}/api/kg/manuals/commit", dict(pv, links=links, by="[회귀 검사] 시나리오 검사기", reviewed=True), timeout=30)
    check("manual committed: 2 SOP skills matched to the fan bearing failure mode", out.get("procedures") == 2 and out.get("steps") == 8
          and all(v["failureMode"] == "fm:bearing-degradation" for v in (out.get("skills") or {}).values()), json.dumps(out.get("skills"), ensure_ascii=False))
    undone = post(f"{PROCESS}/api/kg/manuals/batches/{pv['batch']}/rollback", {'by': '[회귀 검사] 시나리오 검사기'}, timeout=30)
    check('fixture manual graph rolled back while source remains readable', undone.get('status') == 'ROLLED_BACK' and
          get(f"{PROCESS}/api/kg/manuals/sources/{pv['source_id']}").get('source_id') == pv['source_id'], pv['batch'])


def db_checks(alert_id, cmd_id, inc_id):
    section("6. L5 저장소 확인 (TimescaleDB via docker exec)")
    import subprocess
    def q(sql):
        out = subprocess.run(["docker", "compose", "exec", "-T", "timescaledb", "psql", "-U", "hyd", "-d", "hyd", "-At", "-c", sql],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=__file__.rsplit("scripts", 1)[0])
        return out.stdout.strip()
    check("alerts row RAISE→CLEAR", "CLEAR" in q(f"SELECT state FROM alerts WHERE alert_id='{alert_id}'"), q(f"SELECT state, raised_at, cleared_at FROM alerts WHERE alert_id='{alert_id}'"))
    check("actions row with ACK DONE", "DONE" in q(f"SELECT ack_result FROM actions WHERE cmd_id='{cmd_id}'"), q(f"SELECT cmd_id, ack_result, approved_by FROM actions WHERE cmd_id='{cmd_id}'"))
    n = q(f"SELECT count(*) FROM audit WHERE incident='{inc_id}'")
    check("audit rows for incident", n.isdigit() and int(n) >= 6, f"{n} rows")
    check("feat_1s has anomaly scores", (q("SELECT count(*) FROM feat_1s WHERE sensor='TS1' AND score > 0.5") or "0").isdigit() and int(q("SELECT count(*) FROM feat_1s WHERE sensor='TS1' AND score > 0.5")) > 0, "")


def negative_manual_mode():
    section("7. 부정 시나리오: 원자 명령 승인 우회를 사전에 거부")
    post(f"{PLANT}/api/reset")
    time.sleep(2)
    post(f"{PLANT}/api/mode", {"asset": "HYD-02", "mode": "REMOTE_MANUAL"})
    post(f"{PLANT}/api/fault", {"asset": "HYD-02", "type": "cooler_degradation"})
    d, dt = wait_for("RAISE HYD-02", lambda: det("HYD-02") if det("HYD-02").get("phase") == "RAISED" else None, 200)
    check("HYD-02 RAISED", d is not None, f"after {dt:.0f}s")
    alert_id = d["alert_id"] if d else None
    inc, dt = wait_for("incident HYD-02", lambda: open_incident(alert_id), 90)
    check("incident for HYD-02", inc is not None, f"{inc and inc['id']}")
    d2 = next((x for x in get(f"{PROCESS}/api/decisions") if (x.get("origin") or {}).get("incident") == (inc or {}).get("id")), None)
    d2 = get(f"{PROCESS}/api/decisions/{d2['id']}") if d2 else {}
    check("agent cards: REMOTE_MANUAL fact excludes every control card (rule:auto-mode)", d2.get("options") and all(
        any(v["rule"] == "rule:auto-mode" for v in o["violations"]) for o in d2["options"]), d2.get("explanation", "")[:120])
    r = post(f"{PROCESS}/api/incidents/{inc['id']}/approve", {"approvedBy": "[회귀 검사] 운전원", "actions": [{"code": "FAN_SET", "fan_pct": 100}]})
    check("raw command approval without SOP and role is rejected", r.get("error") == 409, json.dumps(r))
    current = get(f"{PROCESS}/api/incidents/{inc['id']}")
    check("no command created by rejected approval", current.get("cmdId") is None, str(current.get("cmdId")))
    check("incident stays open for a reviewed choice", current["state"] == "AWAITING_APPROVAL", current["state"])
    audit = get(f"{PROCESS}/api/audit")
    check("no command audit for bypass attempt", not any(a["event"] == "CMD_ISSUED" and a.get("incident") == inc["id"] for a in audit))
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
    tinc, dt = wait_for("trip incident", lambda: next((i for i in get(f"{PROCESS}/api/incidents") if i["asset"] == "HYD-03" and i["alertId"] and "TRIP" in i["alertId"]), None), 60)
    td = next((x for x in get(f"{PROCESS}/api/decisions") if (x.get("origin") or {}).get("incident") == (tinc or {}).get("id")), None)
    check("agent card for the trip: only SOP-TRIP-01 (reset after cooling) is recommended", td is not None and td.get("recommended") == "skill:reset-after-cool", json.dumps(td, ensure_ascii=False)[:160])
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
