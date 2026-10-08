"""A120 — the pump and fan scenarios run end to end as process instances against the live stack, the way
run_scenario_evidence.py / scenario_instance_test.py prove the cooler (PROCESS_MODE=instance · AGENT_BRIDGE=legacy · TIME_SCALE=20).

    . scripts/host_libpq.sh; .venv314/Scripts/python scripts/run_scenario_pump_fan_evidence.py --out .evidence/a120/pump-fan-1 [--only pump|fan]

Every check is judged on real HTTP (process · detector · plant-sim · enterprise-sim), PG (Supabase ent.maintenance_profiles) and
PLC values read back from the plant — nothing is mocked or replayed.

pump  HYD-02 pump_leakage → detector PUMP_LEAKAGE RAISE → one instance + one Incident → the legacy bridge plays the four agent
      tasks (a first assessment whose 2-minute evidence window still averages healthy pressure is held UNSUPPORTED without any
      PLC command; a person then requests an explicit reassessment after a fresh window — A058/A059 contract) →
      cause:pump-seal-wear (rule:dx-pump) → cards: 압력 상향 excluded by rule:no-pressure-raise, 예비 펌프 전환 recommended →
      생산관리자 reviews the current source and selects → action.cmd PUMP_SELECT → cmd-gateway → PLC pump B → PS1 ≥ 165 →
      detector CLEAR → re-observation "PS1 >= 165.0" → CMMS work order → ev:closed, task:escalate CANCELLED.
fan   HYD-03 fan_vibration → FAN_VIBRATION → cause:fan-bearing-wear (rule:dx-fan, TS1 < 52) → fan SOP cards →
      fan-slow-derate selected → FAN_SET 40 · LOAD_SET 80 ACKed → VS1 < 1.2 → CLEAR → "VS1 < 1.2" → work order → ev:closed.

Setup / teardown: the asset is `restore`d (plant /api/fault type=restore) before and after each flow and /api/reset at the end puts
fan · load · pump back to the operating point. CMMS standby readiness for HYD-02 (ent.maintenance_profiles.standby_ready; NULL =
미확인 on a DB whose rows predate migration 6 although seed.sql inserts true) is set to true for the pump flow and restored to its
prior value afterwards — the agent reads it through the real CMMS endpoint, so rule:standby is judged on a known value.
Host workers (8097/8098) must be down: with AGENT_BRIDGE=legacy they would race the bridge for the same agent tasks (A085/A090).
Evidence in --out: scenario.log, checks.json, started.json/result.json, <flow>-{instance,decision,incident,audit,plant}.json.
Exit code 1 if anything failed.
"""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
import uuid

H = "http://127.0.0.1"
PLANT, DETECTOR, PROCESS, ENT, AGENT = f"{H}:8000", f"{H}:8092", f"{H}:8080", f"{H}:8095", f"{H}:8091"
AGENT_TASKS = ("task:diagnose", "task:candidates", "task:compliance", "task:rank")
DSN = os.environ.get("SUPABASE_DSN", "postgresql://postgres:postgres@127.0.0.1:54322/postgres")
EVIDENCE_WINDOW_S = 125          # evd:ps1-low / evd:fs1-drop average the last 2 wall-clock minutes of tag_1s
results: list[dict] = []
OUT: Path | None = None


class Tee:
    def __init__(self, path):
        self.f, self.o = open(path, "w", encoding="utf-8"), sys.stdout
    def write(self, s):
        self.o.write(s); self.f.write(s)
    def flush(self):
        self.o.flush(); self.f.flush()


def get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def get_status(url, timeout=10):
    """Like get() but a 503 health answer is data (consumer_dead / IPv6 — A108/A115), not an exception."""
    try:
        return get(url, timeout)
    except urllib.error.HTTPError as e:
        try:
            return dict(json.loads(e.read() or b"{}"), http=e.code)
        except Exception:  # noqa: BLE001
            return {"ok": False, "http": e.code}


def post(url, data=None, timeout=20):
    req = urllib.request.Request(url, data=json.dumps(data or {}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()[:300]}


def check(name, ok, detail=""):
    results.append({"name": name, "passed": bool(ok), "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}  {detail}", flush=True)
    return bool(ok)


def save(name, value):
    if OUT:
        (OUT / (name + ".json")).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def wait_for(fn, timeout, every=1.0):
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


def section(title):
    print(f"\n== {title}", flush=True)


def variables(inst):
    return {v["key"]: v.get("value") for v in (inst.get("variables_data") or [])}


def instance_for(alert_id):
    for inst in get(f"{PROCESS}/api/instances?limit=30"):
        if variables(inst).get("alert_id") == alert_id:
            return inst
    return None


def view(pid):
    return get(f"{PROCESS}/api/instances/{pid}")


def items(pid):
    return {w["activity_id"]: w for w in view(pid)["workitems"]}


def statuses(pid):
    return {k: v["status"] for k, v in items(pid).items()}


def pattern_state(asset, pattern):
    return (get(f"{DETECTOR}/api/detector/state")["assets"].get(asset, {}).get("patterns") or {}).get(pattern) or {}


def unit(asset):
    return get(f"{PLANT}/api/state")["units"][asset]


def incident(inc_id):
    return get(f"{PROCESS}/api/incidents/{inc_id}")


def audits(inc_id, event=None):
    rows = [a for a in get(f"{PROCESS}/api/audit") if a.get("incident") == inc_id]        # newest first
    return [a for a in rows if event is None or a.get("event") == event]


def health(port):
    try:
        return get(f"{H}:{port}/health", timeout=3)
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- setup / teardown
def restore(asset, label):
    r = post(f"{PLANT}/api/fault", {"asset": asset, "type": "restore", "ramp_sim_s": 10})
    ok = r.get("kind") == "restore"
    if ok:
        s, dt = wait_for(lambda: unit(asset) if not unit(asset).get("faults") and (u := unit(asset))["status"].get("leak", 0) == 0
                         and u["status"].get("bearing_wear", 0) == 0 and u["status"].get("cooler_health", 1) == 1 else None, 30)
        ok = s is not None
    check(f"{asset} restored {label}", ok, json.dumps(r.get("targets") if ok else r, ensure_ascii=False)[:160])
    return ok


class StandbyFixture:
    """CMMS source of record: ent.maintenance_profiles.standby_ready for HYD-02 = true during the pump flow, prior value restored."""
    def __init__(self, asset):
        self.asset, self.conn, self.prior = asset, None, None

    def __enter__(self):
        import psycopg
        self.conn = psycopg.connect(DSN, autocommit=True)
        row = self.conn.execute("select standby_ready from ent.maintenance_profiles where asset=%s", (self.asset,)).fetchone()
        if row is None:
            raise RuntimeError(f"no ent.maintenance_profiles row for {self.asset}")
        self.prior = row[0]
        self.conn.execute("update ent.maintenance_profiles set standby_ready=true where asset=%s", (self.asset,))
        live = (get(f"{ENT}/cmms/history?asset={self.asset}").get("facts") or {}).get("standby_ready")
        check(f"CMMS standby_ready set true for {self.asset} (prior {self.prior!r}) and visible through the CMMS endpoint", live is True, f"live={live!r}")
        save("standby-before", {self.asset: self.prior})
        return self

    def __exit__(self, *exc):
        self.conn.execute("update ent.maintenance_profiles set standby_ready=%s where asset=%s", (self.prior, self.asset))
        actual = self.conn.execute("select standby_ready from ent.maintenance_profiles where asset=%s", (self.asset,)).fetchone()[0]
        check(f"CMMS standby_ready restored to prior value for {self.asset}", actual is self.prior, f"actual={actual!r} expected={self.prior!r}")
        save("standby-restored", {"actual": actual, "expected": self.prior})
        self.conn.close()


# ---------------------------------------------------------------- shared path: inject → RAISE → instance → agent tasks → task:select
def run_to_selection(flow, asset, fault, pattern, raise_timeout):
    injected_at = time.monotonic()
    r = post(f"{PLANT}/api/fault", {"asset": asset, "type": fault})
    check(f"{fault} injected on {asset} (ramp {r.get('ramp_sim_s')} sim-s)", r.get("kind") == fault, json.dumps(r, ensure_ascii=False)[:160])
    st, dt = wait_for(lambda: pattern_state(asset, pattern) if pattern_state(asset, pattern).get("phase") == "RAISED" else None, raise_timeout)
    t = unit(asset)["tags"]
    if not check(f"detector RAISED {pattern}", st is not None, f"after {dt:.0f}s PS1={t.get('PS1')} FS1={t.get('FS1')} VS1={t.get('VS1')} TS1={t.get('TS1')} load={t.get('LoadSP')}"):
        return None
    alert_id = st["alert_id"]
    inst, dt = wait_for(lambda: instance_for(alert_id), 30)
    if not check("one instance opened for the alert (RUNNING)", inst is not None and inst["status"] == "RUNNING", f"{alert_id} after {dt:.0f}s"):
        return None
    pid, inc_id = inst["proc_inst_id"], variables(inst).get("incident")
    inc = incident(inc_id) if inc_id else {}
    check("incident opened by the instance (AWAITING_APPROVAL) with the pattern's recovery criterion", inc.get("state") == "AWAITING_APPROVAL" and inc.get("alertId") == alert_id,
          f"{inc_id} {inc.get('state')} pattern={inc.get('pattern')}")
    st0 = statuses(pid)
    check("every activity planned and task:diagnose live", len(st0) >= 9 and st0.get("task:diagnose") in ("IN_PROGRESS", "SUBMITTED", "DONE", "PENDING") and st0.get("task:escalate") == "TODO",
          json.dumps(st0, ensure_ascii=False))

    stopped, seen_runs = {}, set()
    def selected_or_stopped():
        current = items(pid)
        if current.get("task:select", {}).get("status") == "IN_PROGRESS":
            return current
        if any(w["status"] == "PENDING" for w in current.values()):
            stopped.update(reason="task pending", tasks=[w["activity_id"] for w in current.values() if w["status"] == "PENDING"])
            return current
        # only an agent run that ended after the last (re)assessment request counts as "stopped" — the held first run stays listed
        matching = [x for x in get(f"{AGENT}/api/agent/runs") if x.get("alertId") == alert_id and x.get("id") not in seen_runs]
        latest = max(matching, key=lambda x: x.get("started") or "", default=None)
        # WITHHELD is not a stop: the process turns it into a held task (PENDING + _deferral) a moment later — wait for that
        if latest and latest["status"] in {"FAILED", "REJECTED_BY_GUARDRAIL"}:
            stopped.update(run=latest["id"], status=latest["status"], reason=latest.get("error"))
            return current
        return None
    tl, dt = wait_for(selected_or_stopped, 150)
    held = (tl or {}).get("task:diagnose") or {}
    if held.get("status") == "PENDING":
        # The evidence SQL averages the last 2 minutes; right after RAISE the window is mostly healthy, so the agent holds the
        # diagnosis instead of guessing. A person asks for a reassessment once a full window of the faulted plant exists.
        receipt = (held.get("draft") or {}).get("_deferral") or {}
        assessment = receipt.get("assessment") or {}
        if not check("first assessment held (UNSUPPORTED/UNKNOWN) without any PLC command or decision",
                     assessment.get("status") in {"UNKNOWN", "UNSUPPORTED"} and assessment.get("reason") and incident(inc_id).get("cmdId") is None
                     and not variables(view(pid)["instance"]).get("decision_id"), json.dumps(assessment, ensure_ascii=False)[:300]):
            return None
        remaining = max(0.0, EVIDENCE_WINDOW_S - (time.monotonic() - injected_at))
        print(f"  waiting {remaining:.0f}s for a fresh 2-minute source window before the explicit reassessment", flush=True)
        time.sleep(remaining)
        seen_runs.update(x.get("id") for x in get(f"{AGENT}/api/agent/runs") if x.get("alertId") == alert_id)
        request = {"deferral_id": receipt["id"], "request_id": "a120-" + uuid.uuid4().hex, "by": "이생산",
                   "reason": "[회귀 검사] 고장 주입 뒤 2분 원천 창을 새로 관측했으므로 재평가를 요청한다"}
        response = post(f"{PROCESS}/api/todolist/{held['id']}/reassess", request)
        save(f"{flow}-reassessment", {"held": held, "request": request, "response": response})
        if not check("explicit reassessment accepted (person's request, not an approval)", not response.get("error") and response.get("status") == "QUEUED",
                     json.dumps(response, ensure_ascii=False)[:200]):
            return None
        stopped.clear()
        tl, dt2 = wait_for(selected_or_stopped, 150); dt += dt2
    ready = tl is not None and tl.get("task:select", {}).get("status") == "IN_PROGRESS" and all(tl.get(a, {}).get("status") == "DONE" for a in AGENT_TASKS)
    if not check("four agent tasks DONE and task:select IN_PROGRESS", ready, f"after {dt:.0f}s " + json.dumps({"tasks": {k: v['status'] for k, v in (tl or {}).items()}, "stopped": stopped}, ensure_ascii=False)[:400]):
        return None
    started = [e for e in view(pid)["events"] if e["event_type"] == "task_started"]
    check("agent tasks were done by the legacy bridge (no host worker took them)", bool(started) and all("legacy" in json.dumps(e, ensure_ascii=False) for e in started), f"{len(started)} task_started")
    timer = tl.get("ev:select-timeout") or {}
    check("boundary timer is a work item with a due_date (sys:process)", timer.get("status") == "IN_PROGRESS" and bool(timer.get("due_date")), json.dumps({k: timer.get(k) for k in ('status', 'due_date')}))
    vd = variables(view(pid)["instance"])
    dec = get(f"{PROCESS}/api/decisions/{vd['decision_id']}") if vd.get("decision_id") else {}
    return pid, inc_id, dec, tl["task:select"], vd


def select_with_review(sel, dec, option, by, role, reason, inc_id):
    review = post(f"{PROCESS}/api/todolist/{sel['id']}/decision-preview", {"decision": dec["id"], "option": option, "parameters": {}}, timeout=60)
    first = (review.get("snapshot", {}).get("options") or [{}])[0]
    if not check("current source reviewed before explicit approval (option feasible now)", review.get("id") and first.get("feasible") is True,
                 json.dumps({"review": review.get("id"), "feasible": first.get("feasible"), "violations": first.get("violations"), "body": review.get("body")}, ensure_ascii=False)[:300]):
        return {"error": 409, "body": "review unavailable/infeasible"}
    check("review did not issue a PLC command", incident(inc_id).get("cmdId") is None)
    r = post(f"{PROCESS}/api/todolist/{sel['id']}/select", dict(decision=dec["id"], option=option, review_id=review["id"], by=by, role=role, reason=reason), timeout=60)
    return r


def after_ack(flow, pid, inc_id):
    inc, dt = wait_for(lambda: (v if (v := incident(inc_id)).get("state") in ("RE_OBSERVING", "RESOLVED", "WORK_ORDER_CREATED", "CLOSED", "ESCALATED") else None), 60)
    check("action.cmd passed the gateway and the PLC ACKed DONE (Incident path only)", inc is not None and (inc.get("ack") or {}).get("result") == "DONE" and inc.get("state") != "ESCALATED",
          json.dumps({"state": inc and inc.get("state"), "actions": inc and inc.get("actions"), "ack": inc and inc.get("ack")}, ensure_ascii=False)[:240])
    published = audits(inc_id, "CMD_PUBLISHED")
    check("exactly one command published for the incident", len(published) == 1, str(len(published)))
    return inc


def finish(flow, pid, inc_id, timeout=400):
    def terminal_or_review():
        current = view(pid)
        if current["instance"]["status"] == "COMPLETED":
            return current
        if any(w["activity_id"] == "task:escalate" and w["status"] == "IN_PROGRESS" for w in current["workitems"]):
            return current      # the failed-close path: a person is being asked, do not wait the whole window in silence
        return None
    fin, dt = wait_for(terminal_or_review, timeout)
    inc = incident(inc_id)
    ok = fin is not None and fin["instance"]["status"] == "COMPLETED" and fin["instance"].get("end_event") == "ev:closed"
    check("instance COMPLETED via ev:closed", ok, f"after {dt:.0f}s end_event={fin and fin['instance'].get('end_event')} incident={inc.get('state')} reason={inc.get('reason')}")
    wi = {w["activity_id"]: w for w in (fin or {}).get("workitems", [])}
    save(f"{flow}-instance", fin or view(pid)); save(f"{flow}-incident", inc); save(f"{flow}-audit", audits(inc_id))
    if not ok:
        return None
    done = {a for a, w in wi.items() if w["status"] == "DONE"}
    check("eight tasks DONE, task:escalate CANCELLED (branch not taken)",
          done >= {*AGENT_TASKS, "task:select", "task:command", "task:reobserve", "task:work-order"} and wi.get("task:escalate", {}).get("status") == "CANCELLED",
          json.dumps({k: v['status'] for k, v in wi.items()}, ensure_ascii=False))
    wo = (wi.get("task:work-order") or {}).get("output", {}).get("work_order") or {}
    check("CMMS work order created by task:work-order and recorded on the incident", wo.get("ok") is True and str(wo.get("ref", "")).startswith("WO-")
          and (inc.get("workOrder") or {}).get("id") == wo.get("ref"), json.dumps(wo, ensure_ascii=False)[:200])
    check("incident CLOSED", inc.get("state") == "CLOSED", inc.get("state"))
    vd = variables(fin["instance"])
    check("recovered=true recorded · 생산관리자 among participants", vd.get("recovered") is True and "role:prod-mgr" in (fin["instance"].get("participants") or []), str(fin["instance"].get("participants")))
    return fin


def reobservation(inc_id):
    rows = audits(inc_id, "REOBSERVATION")
    return (rows[0] if rows else {}).get("detail") or {}


# ---------------------------------------------------------------- flows
def scenario_pump():
    section("PUMP · HYD-02 펌프 내부 누설 → 예비 펌프 전환 → PS1 회복 → 작업지시 → 종결")
    asset = "HYD-02"
    if not restore(asset, "before the flow"):
        return
    with StandbyFixture(asset):
        r = run_to_selection("pump", asset, "pump_leakage", "PUMP_LEAKAGE", 120)
        if not r:
            return
        pid, inc_id, dec, sel, vd = r
        save("pump-decision", dec)
        opts = {o["id"]: o for o in dec.get("options", [])}
        check("diagnosed cause = pump seal wear (rule:dx-pump, PS1 < 165)", vd.get("cause") == "cause:pump-seal-wear" and vd.get("failure_mode") == "fm:volumetric-loss",
              json.dumps({k: vd.get(k) for k in ('cause', 'failure_mode', 'pattern')}, ensure_ascii=False))
        check("cards: 압력 상향(SOP-PMP-03) excluded by rule:no-pressure-raise, 예비 펌프 전환(SOP-PMP-01) recommended",
              dec.get("recommended") == "skill:switch-standby-pump" and opts.get("skill:raise-pressure", {}).get("feasible") is False
              and any(v.get("rule") == "rule:no-pressure-raise" for v in opts.get("skill:raise-pressure", {}).get("violations") or []),
              json.dumps({k: (o.get('rank'), o.get('feasible')) for k, o in opts.items()}, ensure_ascii=False))
        r = post(f"{PROCESS}/api/todolist/{sel['id']}/select", {"decision": dec["id"], "option": "skill:switch-standby-pump", "by": "[회귀 검사] 운전원", "role": "role:operator", "reason": "[회귀 검사] 권한 밖 승인 시도"})
        check("operator refused (403) — 예비 펌프 전환 needs 생산관리자", r.get("error") == 403, str(r.get("body", ""))[:120])
        r = select_with_review(sel, dec, "skill:switch-standby-pump", "이생산", "role:prod-mgr", "[회귀 검사] 예비 펌프 정비 완료 상태 — 생산을 멈추지 않고 압력을 회복한다", inc_id)
        if not check("production manager selected 예비 펌프 전환 (accepted · approval DELIVERED)", "instance" in r and not r.get("error") and r.get("approval_status") == "DELIVERED",
                     json.dumps(r.get("body") or {k: r.get(k) for k in ('accepted', 'approval_status')}, ensure_ascii=False)[:200]):
            return
        inc = after_ack("pump", pid, inc_id)
        check("command was PUMP_SELECT B", bool(inc) and inc.get("actions") == [{"code": "PUMP_SELECT", "pump": "B"}], json.dumps(inc and inc.get("actions")))
        s, dt = wait_for(lambda: (u if (u := unit(asset))["status"].get("pump") == "B" and u["tags"]["PS1"] >= 165 else None), 20, every=0.25)
        s = s or unit(asset)
        check("PLC switched to pump B and PS1 recovered ≥ 165 bar (fc:pump-switch 182)", s["status"].get("pump") == "B" and s["tags"]["PS1"] >= 165,
              f"after {dt:.1f}s pump={s['status'].get('pump')} PS1={s['tags']['PS1']} FS1={s['tags']['FS1']}")
        st, dt = wait_for(lambda: pattern_state(asset, "PUMP_LEAKAGE") if pattern_state(asset, "PUMP_LEAKAGE").get("phase") == "IDLE" else None, 120)
        check("detector CLEARED PUMP_LEAKAGE (PS1 ≥ 168 ∧ FS1 ≥ 8.0 held)", st is not None, f"after {dt:.0f}s")
        fin = finish("pump", pid, inc_id)
        save("pump-plant", get(f"{PLANT}/api/state"))
        if fin:
            rd = reobservation(inc_id)
            check("re-observation judged on PS1 ≥ 165 with cleared=true (not TS1)", rd.get("criterion") == "PS1 >= 165.0" and rd.get("passed") is True and rd.get("cleared") is True,
                  json.dumps(rd, ensure_ascii=False)[:200])
            wo = ({w["activity_id"]: w for w in fin["workitems"]}.get("task:work-order") or {}).get("output", {}).get("work_order") or {}
            check("work order is the pump SOP follow-up in CMMS", "SOP-PMP" in str(wo.get("detail", "")) and wo.get("system") == "sys:cmms", str(wo.get("detail", ""))[:160])
    restore(asset, "after the flow")


def scenario_fan():
    section("FAN · HYD-03 팬 베어링 마모 → 팬 40 % + 부하 80 % → VS1 < 1.2 → 작업지시 → 종결")
    asset = "HYD-03"
    if not restore(asset, "before the flow"):
        return
    r = run_to_selection("fan", asset, "fan_vibration", "FAN_VIBRATION", 150)
    if not r:
        return
    pid, inc_id, dec, sel, vd = r
    save("fan-decision", dec)
    opts = {o["id"]: o for o in dec.get("options", [])}
    check("diagnosed cause = fan bearing wear (rule:dx-fan, TS1 < 52)", vd.get("cause") == "cause:fan-bearing-wear" and vd.get("failure_mode") == "fm:bearing-degradation",
          json.dumps({k: vd.get(k) for k in ('cause', 'failure_mode', 'pattern')}, ensure_ascii=False))
    check("candidate cards are the fan SOPs (fan-slow-derate · fan-slow) and fan-slow-derate is feasible",
          {"skill:fan-slow-derate", "skill:fan-slow"} <= set(opts) and opts["skill:fan-slow-derate"].get("feasible") is True,
          json.dumps({k: (o.get('rank'), o.get('feasible')) for k, o in opts.items()}, ensure_ascii=False))
    r = select_with_review(sel, dec, "skill:fan-slow-derate", "이생산", "role:prod-mgr", "[회귀 검사] 유온 상승 없이 진동만 낮춘다", inc_id)
    if not check("production manager selected fan-slow-derate (accepted · approval DELIVERED)", "instance" in r and not r.get("error") and r.get("approval_status") == "DELIVERED",
                 json.dumps(r.get("body") or {k: r.get(k) for k in ('accepted', 'approval_status')}, ensure_ascii=False)[:200]):
        return
    inc = after_ack("fan", pid, inc_id)
    codes = [a.get("code") for a in (inc or {}).get("actions") or []]
    check("command was FAN_SET 40 · LOAD_SET 80", codes == ["FAN_SET", "LOAD_SET"] and (inc["actions"][0].get("fan_pct"), inc["actions"][1].get("load_pct")) == (40, 80), json.dumps(inc and inc.get("actions")))
    s, dt = wait_for(lambda: (u if (u := unit(asset))["tags"]["VS1"] < 1.2 and u["tags"]["FanSpeedSP"] == 40 else None), 60)
    s = s or unit(asset)
    check("PLC fan 40 % · VS1 fell under 1.2 mm/s (fc:fan-slow-vs1 ≈ 1.0)", s["tags"]["VS1"] < 1.2 and s["tags"]["FanSpeedSP"] == 40, f"after {dt:.0f}s VS1={s['tags']['VS1']} fan={s['tags']['FanSpeedSP']} load={s['tags']['LoadSP']}")
    st, dt = wait_for(lambda: pattern_state(asset, "FAN_VIBRATION") if pattern_state(asset, "FAN_VIBRATION").get("phase") == "IDLE" else None, 120)
    check("detector CLEARED FAN_VIBRATION (VS1 < 1.1 ∧ not rising, held)", st is not None, f"after {dt:.0f}s")
    fin = finish("fan", pid, inc_id)
    save("fan-plant", get(f"{PLANT}/api/state"))
    if fin:
        rd = reobservation(inc_id)
        check("re-observation judged on VS1 < 1.2 with cleared=true", rd.get("criterion") == "VS1 < 1.2" and rd.get("passed") is True and rd.get("cleared") is True, json.dumps(rd, ensure_ascii=False)[:200])
    restore(asset, "after the flow")


# ---------------------------------------------------------------- main
def main():
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", choices=["pump", "fan"])
    ap.add_argument("--allow-workers", action="store_true", help="do not fail the precondition when a host worker is up (not for evidence runs)")
    ap.add_argument("--no-reset", action="store_true", help="skip the final plant /api/reset (restore per asset still runs)")
    a = ap.parse_args()
    OUT = Path(a.out).resolve(); OUT.mkdir(parents=True, exist_ok=False)
    sys.stdout = Tee(OUT / "scenario.log")
    root = Path(__file__).resolve().parents[1]
    record = {"started": datetime.now(timezone.utc).isoformat(), "pid": os.getpid(), "argv": sys.argv,
              "script_sha256": hashlib.sha256((root / "scripts/run_scenario_pump_fan_evidence.py").read_bytes()).hexdigest()}
    save("started", record)
    try:
        section("0. 모드 · 서비스 · 선행 조건")
        mode = get(f"{PROCESS}/api/process/mode")
        save("mode", mode)
        check("process in instance mode with the legacy agent bridge", mode.get("mode") == "instance" and mode.get("agent_bridge") == "legacy", json.dumps(mode, ensure_ascii=False))
        check("TIME_SCALE 20", float(mode.get("time_scale") or 0) == 20.0, str(mode.get("time_scale")))
        h = get_status(f"{PROCESS}/healthz")
        if not check("process healthy with Supabase and Kafka (503 with consumer_dead → docker restart hyd-iot-edu-process-1 first)",
                     h.get("ok") and h.get("supabase") is True and h.get("kafka") is True, json.dumps(h, ensure_ascii=False)[:300]):
            return
        for name, url in (("detector", f"{DETECTOR}/healthz"), ("plant-sim", f"{PLANT}/healthz"), ("enterprise-sim", f"{ENT}/healthz"), ("agent", f"{AGENT}/healthz")):
            try:
                eh = get_status(url); ok = eh.get("ok", True) and not eh.get("http")
            except Exception as e:  # noqa: BLE001
                eh, ok = {"error": str(e)[:100]}, False
            check(f"{name} healthy", ok, json.dumps(eh, ensure_ascii=False)[:120])
        workers = [p for p in (8097, 8098) if health(p)]
        ok_workers = not workers or a.allow_workers
        check("no host worker up on 8097/8098 (they would race the legacy bridge for the agent tasks)", ok_workers, f"up on {workers}" if workers else "none")
        if not ok_workers:
            return
        for name, fn in (("pump", scenario_pump), ("fan", scenario_fan)):
            if a.only in (None, name):
                fn()
    finally:
        if not a.no_reset:
            post(f"{PLANT}/api/reset")
        save("plant-final", get(f"{PLANT}/api/state"))
        failed = [r for r in results if not r["passed"]]
        record.update(finished=datetime.now(timezone.utc).isoformat(), passed=len(results) - len(failed), total=len(results), failed=[r["name"] for r in failed])
        save("checks", results); save("result", record)
        print(f"\n{'ALL PASS' if not failed else str(len(failed)) + ' FAILED'} — {len(results) - len(failed)}/{len(results)} checks")
        for r in failed:
            print("  FAILED:", r["name"], r["detail"])
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
