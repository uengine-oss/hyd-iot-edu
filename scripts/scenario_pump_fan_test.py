"""Pump leakage · fan vibration · masked mitigation against the running stack (PROCESS_MODE=instance, C4).

    python scripts/scenario_pump_fan_test.py            # ~6 min at TIME_SCALE=20
    python scripts/scenario_pump_fan_test.py --only pump|fan|mask

pump  HYD-02: pump_leakage → PUMP_LEAKAGE RAISE → instance → cards (압력 상향 excluded, 예비 펌프 전환 recommended)
      → 생산관리자 selects switch-standby-pump → action.cmd PUMP_SELECT → PLC pump B → PS1 back ≥ 165 → CLEAR
      → re-observation passes on PS1 → work order → ev:closed
fan   HYD-03: fan_vibration → FAN_VIBRATION RAISE → cards → fan-slow-derate → VS1 < 1.2 → ev:closed
mask  HYD-01: pump_leakage → derate-70 selected → alert CLEAR (load < 80 ends the match) but PS1 stays < 165
      → MITIGATION_FAILED → ESCALATED → ev:escalated
Exit code 1 if anything failed.
"""
import argparse
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
import uuid

H = "http://127.0.0.1"
PLANT, DETECTOR, PROCESS, ENT = f"{H}:8000", f"{H}:8092", f"{H}:8080", f"{H}:8095"
results: list[tuple[str, bool, str]] = []
observed_instances = []
reassessment_evidence = []
REASSESS_HELD = False


def get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def post(url, data=None, timeout=20):
    req = urllib.request.Request(url, data=json.dumps(data or {}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()[:300]}


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}  {detail}", flush=True)
    return ok


def summary():
    failed = [r for r in results if not r[1]]
    print(f"\n{'ALL PASS' if not failed else str(len(failed)) + ' FAILED'} — {len(results) - len(failed)}/{len(results)} checks")
    for name, ok, detail in failed:
        print("  FAILED:", name, detail)
    sys.exit(1 if failed else 0)


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


def pattern_state(asset, pattern):
    return (get(f"{DETECTOR}/api/detector/state")["assets"].get(asset, {}).get("patterns") or {}).get(pattern) or {}


def tags(asset):
    return get(f"{PLANT}/api/state")["units"][asset]


def run_to_selection(asset, fault, pattern, raise_timeout):
    """Inject → RAISE → instance → agent tasks → task:select IN_PROGRESS. Returns (pid, inc_id, decision, select item)."""
    injected_at=time.monotonic()
    r = post(f"{PLANT}/api/fault", {"asset": asset, "type": fault})
    check(f"{fault} injected on {asset}", r.get("kind") == fault, json.dumps(r))
    st, dt = wait_for(lambda: pattern_state(asset, pattern) if pattern_state(asset, pattern).get("phase") == "RAISED" else None, raise_timeout)
    t = tags(asset)["tags"]
    if not check(f"detector RAISED {pattern}", st is not None, f"after {dt:.0f}s PS1={t.get('PS1')} FS1={t.get('FS1')} VS1={t.get('VS1')} load={t.get('LoadSP')}"):
        return None
    alert_id = st["alert_id"]
    inst, dt = wait_for(lambda: instance_for(alert_id), 30)
    if not check("instance opened for the alert", inst is not None, f"{alert_id} after {dt:.0f}s"):
        return None
    pid, inc_id = inst["proc_inst_id"], variables(inst).get("incident")
    observed_instances.append(pid)
    bridge = get(f'{PROCESS}/api/process/mode').get('agent_bridge')
    stopped = {}
    def selected_or_stopped():
        current = items(pid)
        if current.get('task:select', {}).get('status') == 'IN_PROGRESS':
            return current
        blocked = [w for w in current.values() if w['status'] == 'PENDING']
        if blocked:
            stopped.update(reason='task pending', tasks=[w['activity_id'] for w in blocked])
            return current
        if bridge == 'legacy' and not REASSESS_HELD:
            matching = [r for r in get(f'{H}:8091/api/agent/runs') if r.get('alertId') == alert_id]
            latest = max(matching, key=lambda r:r.get('started') or '', default=None)
            if latest and latest['status'] in {'WITHHELD','FAILED','REJECTED_BY_GUARDRAIL'}:
                stopped.update(run=latest['id'], status=latest['status'], reason=latest.get('error'))
                return current
        return None
    tl, dt = wait_for(selected_or_stopped, 150)
    held=(tl or {}).get('task:diagnose') or {}
    if REASSESS_HELD and held.get('status')=='PENDING':
        receipt=(held.get('draft') or {}).get('_deferral') or {}
        assessment=receipt.get('assessment') or {}
        incident=get(f'{PROCESS}/api/incidents/{inc_id}')
        if not check('unsupported/unknown diagnosis is durably held without PLC command',
                     assessment.get('status') in {'UNKNOWN','UNSUPPORTED'} and assessment.get('reason')
                     and incident.get('cmdId') is None and not variables(view(pid)['instance']).get('decision_id'),
                     json.dumps(assessment,ensure_ascii=False)[:1500]):return None
        # Explicit test-user action after a complete real-time source window.
        # Production does not silently loop; SQL and TIME_SCALE are unchanged.
        remaining=max(0,125-(time.monotonic()-injected_at))
        print(f'  Waiting {remaining:.0f} wall seconds for new 2-minute source window before explicit reassessment',flush=True)
        time.sleep(remaining)
        request={'deferral_id':receipt['id'],'request_id':'scenario-'+uuid.uuid4().hex,
                 'by':'[회귀 검사] 시나리오 검사기','reason':'[회귀 검사] 고장 주입 후 실제 2분 원천 창을 새로 관측하여 재평가 요청'}
        response=post(f"{PROCESS}/api/todolist/{held['id']}/reassess",request)
        reassessment_evidence.append({'instance':pid,'held':held,'request':request,'response':response})
        if not check('explicit reassessment accepted',not response.get('error'),json.dumps(response,ensure_ascii=False)[:350]):return None
        stopped.clear();tl,dt=wait_for(selected_or_stopped,150)
    ready = (tl is not None and tl.get('task:select', {}).get('status') == 'IN_PROGRESS'
             and all(tl.get(k,{}).get('status')=='DONE' for k in ('task:diagnose','task:candidates','task:compliance','task:rank')))
    detail = {'tasks': {k:v['status'] for k,v in (tl or items(pid)).items()}, 'stopped':stopped}
    if not check("agent tasks DONE and task:select IN_PROGRESS", ready, f"after {dt:.0f}s " + json.dumps(detail, ensure_ascii=False)):
        return None
    vd = variables(view(pid)["instance"])
    dec = get(f"{PROCESS}/api/decisions/{vd['decision_id']}")
    return pid, inc_id, dec, tl["task:select"], vd


def finish(pid, inc_id, expect_end, timeout=360):
    def terminal_or_review():
        current = view(pid)
        if current['instance']['status'] == 'COMPLETED':
            return current
        if expect_end == 'ev:closed' and any(w['activity_id'] == 'task:escalate' and w['status'] == 'IN_PROGRESS'
                                            for w in current['workitems']):
            return current  # A human review is a failed close path, not six minutes of hidden waiting.
        return None
    fin, dt = wait_for(terminal_or_review, timeout)
    ok = fin is not None and fin['instance']['status'] == 'COMPLETED' and fin["instance"].get("end_event") == expect_end
    check(f"instance COMPLETED via {expect_end}", ok, f"after {dt:.0f}s end_event={fin and fin['instance'].get('end_event')} incident={get(f'{PROCESS}/api/incidents/{inc_id}').get('state')}")
    return fin if ok else None


def reobservation(inc_id):
    audits = [a for a in get(f"{PROCESS}/api/audit") if a.get("incident") == inc_id and a.get("event") == "REOBSERVATION"]   # newest first
    return (audits[0] if audits else {}).get("detail") or {}


def select_with_review(sel, dec, option, by, role, reason, inc_id):
    review = post(f"{PROCESS}/api/todolist/{sel['id']}/decision-preview",
                  {'decision':dec['id'], 'option':option, 'parameters':{}}, timeout=60)
    if not check('current source reviewed before explicit approval',
                 review.get('id') and review.get('snapshot',{}).get('options',[{}])[0].get('feasible') is True,
                 str(review.get('id') or review.get('body'))):
        return {'error':409, 'body':'review unavailable/infeasible'}
    check('review did not issue PLC command',get(f'{PROCESS}/api/incidents/{inc_id}').get('cmdId') is None)
    return post(f"{PROCESS}/api/todolist/{sel['id']}/select",
                dict(decision=dec['id'],option=option,review_id=review['id'],by=by,role=role,reason=reason),timeout=60)


def scenario_pump():
    section("PUMP · HYD-02 펌프 내부 누설 → 예비 펌프 전환 → PS1 회복 → 종결")
    r = run_to_selection("HYD-02", "pump_leakage", "PUMP_LEAKAGE", 120)
    if not r:
        return
    pid, inc_id, dec, sel, vd = r
    opts = {o["id"]: o for o in dec.get("options", [])}
    check("diagnosed cause = pump seal wear (rule:dx-pump)", vd.get("cause") == "cause:pump-seal-wear", json.dumps({k: vd.get(k) for k in ('cause', 'failure_mode', 'pattern')}, ensure_ascii=False))
    check("cards: 압력 상향 excluded by rule:no-pressure-raise, 예비 펌프 전환 recommended",
          dec.get("recommended") == "skill:switch-standby-pump" and opts.get("skill:raise-pressure", {}).get("feasible") is False,
          json.dumps({k: (o.get('rank'), o.get('feasible')) for k, o in opts.items()}, ensure_ascii=False))
    r = select_with_review(sel,dec,'skill:switch-standby-pump','이생산','role:prod-mgr','[회귀 검사] 예비 펌프 정비 완료 상태',inc_id)
    if not check("production manager selected switch-standby-pump", "instance" in r and not r.get("error"), str(r.get("body") or "")[:300]):
        return
    inc, dt = wait_for(lambda: get(f"{PROCESS}/api/incidents/{inc_id}") if get(f"{PROCESS}/api/incidents/{inc_id}").get("state") in ("RE_OBSERVING", "RESOLVED", "WORK_ORDER_CREATED", "CLOSED") else None, 60)
    check("action.cmd PUMP_SELECT passed the gateway and the PLC ACKed", inc is not None and (inc.get("ack") or {}).get("result") == "DONE",
          json.dumps({"state": inc and inc.get("state"), "actions": inc and inc.get("actions"), "ack": inc and inc.get("ack")}, ensure_ascii=False)[:200])
    # ACK confirms application of the selector; the next physics/telemetry tick
    # supplies the changed pressure. Observe it instead of assuming simultaneity.
    s, pressure_dt = wait_for(lambda:(u if (u:=tags('HYD-02'))['status'].get('pump')=='B'
                                  and u['tags']['PS1']>=165 else None),15,every=.25)
    s = s or tags('HYD-02')
    check("PLC switched to pump B and PS1 recovered toward 182 bar", s["status"].get("pump") == "B" and s["tags"]["PS1"] >= 165, f"after {pressure_dt:.2f}s pump={s['status'].get('pump')} PS1={s['tags']['PS1']} FS1={s['tags']['FS1']}")
    fin = finish(pid, inc_id, "ev:closed")
    if fin:
        wi = {w["activity_id"]: w for w in fin["workitems"]}
        wo = (wi.get("task:work-order") or {}).get("output", {}).get("work_order") or {}
        check("work order (씰 교체) created in CMMS", wo.get("ok") is True, json.dumps(wo, ensure_ascii=False)[:140])
        rd = reobservation(inc_id)
        check("re-observation judged on PS1 ≥ 165 (not TS1)", rd.get("criterion") == "PS1 >= 165.0" and rd.get("passed") is True, json.dumps(rd, ensure_ascii=False)[:160])


def scenario_fan():
    section("FAN · HYD-03 팬 베어링 마모 → 팬 40 % + 부하 80 % → VS1 < 1.2 → 종결")
    r = run_to_selection("HYD-03", "fan_vibration", "FAN_VIBRATION", 150)
    if not r:
        return
    pid, inc_id, dec, sel, vd = r
    opts = {o["id"]: o for o in dec.get("options", [])}
    check("diagnosed cause = fan bearing wear (rule:dx-fan, TS1 < 52)", vd.get("cause") == "cause:fan-bearing-wear", json.dumps({k: vd.get(k) for k in ('cause', 'failure_mode')}, ensure_ascii=False))
    check("candidate cards are the fan SOPs", {"skill:fan-slow-derate", "skill:fan-slow"} <= set(opts), str(sorted(opts)))
    r = select_with_review(sel,dec,'skill:fan-slow-derate','이생산','role:prod-mgr','[회귀 검사] 유온 상승 없이 진동만 낮춘다',inc_id)
    if not check("production manager selected fan-slow-derate", "instance" in r and not r.get("error"), str(r.get("body") or "")[:300]):
        return
    inc, dt = wait_for(lambda: get(f"{PROCESS}/api/incidents/{inc_id}") if get(f"{PROCESS}/api/incidents/{inc_id}").get("state") in ("RE_OBSERVING", "RESOLVED", "WORK_ORDER_CREATED", "CLOSED") else None, 60)
    check("FAN_SET 40 · LOAD_SET 80 ACKed", inc is not None and (inc.get("ack") or {}).get("result") == "DONE", json.dumps({"actions": inc and inc.get("actions"), "ack": inc and inc.get("ack")}, ensure_ascii=False)[:200])
    s, dt = wait_for(lambda: tags("HYD-03") if tags("HYD-03")["tags"]["VS1"] < 1.2 else None, 60)
    check("VS1 fell under 1.2 mm/s (fc:fan-slow-vs1 ≈ 1.0)", s is not None, f"after {dt:.0f}s VS1={(s or tags('HYD-03'))['tags']['VS1']} fan={(s or tags('HYD-03'))['tags']['FanSpeedSP']}")
    fin = finish(pid, inc_id, "ev:closed")
    if fin:
        rd = reobservation(inc_id)
        check("re-observation judged on VS1 < 1.2", rd.get("criterion") == "VS1 < 1.2" and rd.get("passed") is True, json.dumps(rd, ensure_ascii=False)[:160])


def scenario_mask():
    section("MASK · HYD-01 펌프 누설 → 부하 70 % 선택 → 경보는 꺼지지만 PS1 < 165 → 에스컬레이션")
    r = run_to_selection("HYD-01", "pump_leakage", "PUMP_LEAKAGE", 120)
    if not r:
        return
    pid, inc_id, dec, sel, vd = r
    r = select_with_review(sel,dec,'skill:derate-70','김운전','role:operator','[회귀 검사] 일단 부하를 낮춘다',inc_id)
    if not check("operator selected derate-70 (approver role:operator)", "instance" in r and not r.get("error"), str(r.get("body") or "")[:120]):
        return
    st, dt = wait_for(lambda: pattern_state("HYD-01", "PUMP_LEAKAGE") if pattern_state("HYD-01", "PUMP_LEAKAGE").get("phase") == "IDLE" else None, 90)
    t = tags("HYD-01")["tags"]
    check("alert CLEARED because load < 80 ended the match (masked)", st is not None, f"after {dt:.0f}s load={t.get('LoadSP')} PS1={t.get('PS1')}")
    check("but PS1 still under 165 bar (fc:pump-derate70 ≈ 160)", t.get("PS1", 999) < 165, f"PS1={t.get('PS1')}")
    inc, dt = wait_for(lambda: get(f"{PROCESS}/api/incidents/{inc_id}") if get(f"{PROCESS}/api/incidents/{inc_id}").get("state") == "ESCALATED" else None, 240)
    check("incident ESCALATED with MITIGATION_FAILED", inc is not None and inc.get("reason") == "MITIGATION_FAILED", f"after {dt:.0f}s {inc and inc.get('state')} {inc and inc.get('reason')}")
    rd = reobservation(inc_id)
    check("re-observation detail says cleared=true but PS1 criterion failed", rd.get("cleared") is True and rd.get("passed") is False and rd.get("criterion") == "PS1 >= 165.0", json.dumps(rd, ensure_ascii=False)[:160])
    # gw:recovered = no → the production manager gets the escalation task (a human task, the instance waits for it)
    esc, dt = wait_for(lambda: items(pid)["task:escalate"] if items(pid).get("task:escalate", {}).get("status") == "IN_PROGRESS" else None, 30)
    check("task:escalate IN_PROGRESS for 생산관리자 (the instance waits for a person)", esc is not None and esc.get("user_id") == "role:prod-mgr", json.dumps({k: v['status'] for k, v in items(pid).items()}, ensure_ascii=False))
    if esc:
        r = post(f"{PROCESS}/api/todolist/{esc['id']}/submit", {"output": {"note": "[회귀 검사] 부하 저감으로는 압력이 회복되지 않음. 예비 펌프 전환 지시."}, "by": "이생산"})
        check("manager submitted the escalate form", "instance" in r and not r.get("error"), str(r.get("body") or "")[:120])
    fin = finish(pid, inc_id, "ev:escalated", timeout=60)
    if fin:
        wi = {w["activity_id"]: w for w in fin["workitems"]}
        check("task:work-order CANCELLED (branch not taken)", wi.get("task:work-order", {}).get("status") == "CANCELLED", json.dumps({k: v['status'] for k, v in wi.items()}, ensure_ascii=False))


def main():
    global REASSESS_HELD
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', choices=['pump','fan','mask'])
    ap.add_argument('--out', help='preserve this run decisions, instances and plant observations')
    ap.add_argument('--standby-ready', action='store_true', help='explicit test fixture: CMMS HYD-02 ready=true; restore prior value')
    ap.add_argument('--reassess-held', action='store_true', help='explicit test-user reassessment after a fresh 2-minute source window; no automatic production retry')
    args = ap.parse_args()
    REASSESS_HELD=args.reassess_held
    out=Path(args.out) if args.out else None
    if out: out.mkdir(parents=True,exist_ok=False)
    conn=None; prior=None
    def save(name,value):
        if out: (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    try:
        mode = get(f'{PROCESS}/api/process/mode')
        check('process in instance mode', mode.get('mode')=='instance', json.dumps(mode,ensure_ascii=False))
        if args.standby_ready:
            import psycopg
            conn=psycopg.connect('postgresql://postgres:postgres@127.0.0.1:54322/postgres',autocommit=True)
            row=conn.execute("select standby_ready from ent.maintenance_profiles where asset='HYD-02'").fetchone()
            assert row is not None, 'missing maintenance source row'
            prior=row[0];save('readiness-before',{'HYD-02':prior})
            conn.execute("update ent.maintenance_profiles set standby_ready=true where asset='HYD-02'")
            print('Explicit test fixture: CMMS HYD-02 standby_ready=true',flush=True)
        post(f'{PLANT}/api/reset');time.sleep(3)
        for name,fn in (('pump',scenario_pump),('fan',scenario_fan),('mask',scenario_mask)):
            if args.only in (None,name): fn()
    finally:
        for index,pid in enumerate(observed_instances):
            current=view(pid);save(f'instance-{index}',current)
            values=variables(current['instance'])
            if values.get('decision_id'):save(f'decision-{index}',get(f"{PROCESS}/api/decisions/{values['decision_id']}"))
            if values.get('incident'):save(f'incident-{index}',get(f"{PROCESS}/api/incidents/{values['incident']}"))
        save('plant-before-reset',get(f'{PLANT}/api/state'))
        save('checks',[{'name':name,'passed':ok,'detail':detail} for name,ok,detail in results])
        save('reassessments',reassessment_evidence)
        post(f'{PLANT}/api/reset')
        if conn:
            conn.execute("update ent.maintenance_profiles set standby_ready=%s where asset='HYD-02'",(prior,))
            actual=conn.execute("select standby_ready from ent.maintenance_profiles where asset='HYD-02'").fetchone()[0]
            save('readiness-restored',{'actual':actual,'expected':prior});assert actual is prior
            conn.close()
    summary()


if __name__=='__main__':
    main()
