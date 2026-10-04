"""End-to-end test of PROCESS_MODE=instance against the running stack (docs/handoff/HANDOFF.md §9 B11 · D).

    PROCESS_MODE=instance AGENT_BRIDGE=legacy  docker compose up -d --build process enterprise-sim
    python scripts/scenario_instance_test.py               # cooler scenario as a process instance (~4 min at TIME_SCALE=20)
    python scripts/scenario_instance_test.py --worker      # expect the cliagents worker (AGENT_BRIDGE=off) instead of the legacy bridge

Checks (ProcessGPT semantics): alert RAISE opens one instance (every activity TODO, task:diagnose IN_PROGRESS) + one incident
→ four agent tasks go IN_PROGRESS → SUBMITTED (fetch_pending_task / save_task_result) → DONE by the engine → task:select
IN_PROGRESS with its timer event row → operator is refused (403) → production manager submits the select_card form
→ task:command SUBMITTED (service) → ACK → task:reobserve → task:work-order (CMMS row) → ev:closed; the untaken branch is
CANCELLED; the ontology holds ProcessInstance -INSTANCE_OF-> Process, WorkItem -EXECUTES-> Task, ROLE_BOUND.
Exit code 1 if anything failed. Prints PASS/FAIL per step with the observed value.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

# compose publishes IPv4 loopback; localhost may incur Windows IPv6 fallback
# on every request, consuming the accelerated human-task deadline.
H = "http://127.0.0.1"
PLANT, DETECTOR, PROCESS, ENT = f"{H}:8000", f"{H}:8092", f"{H}:8080", f"{H}:8095"
AGENT_TASKS = ("task:diagnose", "task:candidates", "task:compliance", "task:rank")
results: list[tuple[str, bool, str]] = []


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


def require(name, ok, detail=""):
    """check() for a step the rest of the run depends on: on failure print the summary and exit 1 instead of crashing."""
    if not check(name, ok, detail):
        summary()


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
    for inst in get(f"{PROCESS}/api/instances?limit=20"):
        if variables(inst).get("alert_id") == alert_id:
            return inst
    return None


def items(pid):
    return {w["activity_id"]: w for w in get(f"{PROCESS}/api/instances/{pid}")["workitems"]}


def statuses(pid):
    return {k: v["status"] for k, v in items(pid).items()}


def view(pid):
    return get(f"{PROCESS}/api/instances/{pid}")


def selection_contract_matches(inst, definition, selected_task, form):
    pinned = "forms" in definition
    expected = dict(form, id="select_card") if pinned else form
    return (inst.get("proc_def_version") == definition.get("version")
            and selected_task.get("form") == expected
            and selected_task.get("form_source") == ("definition-version" if pinned else "legacy-live"))


def cypher(q):
    out = subprocess.run(["docker", "exec", "hyd-iot-edu-neo4j-1", "cypher-shell", "-u", "neo4j", "-p", "hydpass123", "--format", "plain", q],
                         capture_output=True, text=True, timeout=60)
    return out.stdout.strip()


def restart_during_reobserve(pid, inc_id, decision_id):
    """Real PLC already ACKed. Kill the process, then verify durable review routing."""
    section("4R. 재관측 중 프로세스 강제 종료 → 재시작 확인 작업")
    evidence=Path(__file__).resolve().parents[1]/'.evidence/reaudit'/('restart-'+pid)
    evidence.mkdir(parents=True,exist_ok=True)
    def save(name,value):
        (evidence/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    before=get(f'{PROCESS}/api/incidents/{inc_id}');save('before-incident',before);save('before-instance',view(pid))
    require('fault injected while Incident RE_OBSERVING',before['state']=='RE_OBSERVING',before['state'])
    cmd_id=before['cmdId']
    subprocess.run(['docker','kill','hyd-iot-edu-process-1'],check=True,timeout=30)
    subprocess.run(['docker','start','hyd-iot-edu-process-1'],check=True,timeout=30)
    health,dt=wait_for(lambda:get(f'{PROCESS}/healthz'),60)
    require('process healthy after kill/start',health and health.get('ok'),f'after {dt:.1f}s')
    recovered,dt=wait_for(lambda:view(pid) if items(pid)['task:escalate']['status']=='IN_PROGRESS' else None,30)
    require('lost restart notification recovered into human escalation',recovered is not None,f'after {dt:.1f}s')
    inc=get(f'{PROCESS}/api/incidents/{inc_id}');save('restored-incident',inc);save('restored-instance',recovered)
    check('Incident escalated with PROCESS_RESTART_REVIEW',inc['state']=='ESCALATED' and inc.get('reason')=='PROCESS_RESTART_REVIEW',json.dumps(inc.get('reason')))
    check('command identity preserved on restart',inc.get('cmdId')==cmd_id,inc.get('cmdId',''))
    audit=get(f'{PROCESS}/api/audit')
    published=[a for a in audit if a.get('incident')==inc_id and a.get('event')=='CMD_PUBLISHED']
    save('audit',audit)
    check('only one command publication recorded',len(published)==1,str(len(published)))
    wi=items(pid)
    check('reobservation failed into review; no CMMS work order',wi['task:reobserve']['status']=='DONE'
          and wi['task:reobserve']['output'].get('recovered') is False and wi['task:work-order']['status']=='TODO',json.dumps(statuses(pid)))
    retry=post(f"{PROCESS}/api/todolist/{wi['task:select']['id']}/select",dict(decision=decision_id,option='skill:fan-max-derate',by='fixture',role='role:prod-mgr'))
    check('old approval rejected after restart',retry.get('error')==400,str(retry))
    response=post(f"{PROCESS}/api/todolist/{wi['task:escalate']['id']}/submit",dict(output={'note':'강제 종료 후 설비 상태 확인, 별도 정비 판단 필요'},by='fixture'))
    check('human confirms escalation',not response.get('error'),str(response.get('error')))
    final=view(pid);save('final-instance',final)
    check('explicit escalation end, without claiming recovery',final['instance']['status']=='COMPLETED'
          and final['instance'].get('end_event')=='ev:escalated' and variables(final['instance']).get('recovered') is False,final['instance'].get('end_event',''))
    graph=get(f'{PROCESS}/api/instances/{pid}/graph');save('graph',graph)
    save('checks',results)
    post(f'{PLANT}/api/reset')
    summary()


def main(expect_worker: bool, restart: bool = False, fresh_review: bool = False):
    section("0. 모드 · 서비스")
    mode = get(f"{PROCESS}/api/process/mode")
    clock_factor = 20.0 / max(float(mode.get("time_scale") or 20.0), 1.0)
    print(f"  physical clock factor vs baseline: {clock_factor:g}; scale={mode.get('time_scale')}", flush=True)
    require("process in instance mode", mode.get("mode") == "instance", json.dumps(mode, ensure_ascii=False))
    check("agent bridge setting matches the run", (mode.get("agent_bridge") == "legacy") != expect_worker, f"agent_bridge={mode.get('agent_bridge')} expect_worker={expect_worker}")
    h = get(f"{PROCESS}/healthz")
    check("process healthy with Supabase", h.get("ok") and h.get("supabase") is True, json.dumps({k: h.get(k) for k in ('ok', 'mode', 'supabase', 'kafka')}))
    eh = get(f"{ENT}/healthz")
    check("enterprise-sim healthy", eh.get("ok"), f"backend={eh.get('backend')}")
    users = get(f"{PROCESS}/api/users")
    check("users table seeded (people + agents)", any(u["id"] == "role:operator" and not u["is_agent"] for u in users) and any(u["id"] == "sys:agent" and u["is_agent"] for u in users), f"{len(users)} users")
    definition = get(f"{PROCESS}/api/process/definition")
    form = definition.get("forms", {}).get("select_card")
    if form is None:
        form = get(f"{PROCESS}/api/forms/select_card")
    check("default definition exposes the selection contract", [f["key"] for f in form.get("fields_json", [])] == ["chosen_skill", "chosen_skill_kind"], f"version={definition.get('version')} pinned={'forms' in definition}")

    section("1. 초기화 → 쿨러 열화 주입 (HYD-01) → 경보가 인스턴스를 연다")
    post(f"{PLANT}/api/reset")
    post(f"{ENT}/api/reset")
    time.sleep(2)
    r = post(f"{PLANT}/api/fault", {"asset": "HYD-01", "type": "cooler_degradation"})
    check("fault injected", r.get("kind") == "cooler_degradation", json.dumps(r))
    d, dt = wait_for(lambda: get(f"{DETECTOR}/api/detector/state")["assets"].get("HYD-01", {}) if get(f"{DETECTOR}/api/detector/state")["assets"].get("HYD-01", {}).get("phase") == "RAISED" else None, 200 * clock_factor)
    require("detector RAISED", d is not None, f"after {dt:.0f}s")
    alert_id = d["alert_id"] if d else None
    inst, dt = wait_for(lambda: instance_for(alert_id), 30)
    require("one instance opened for the alert", inst is not None and inst["status"] == "RUNNING", f"{inst and inst['proc_inst_id']} after {dt:.0f}s")
    pid = inst["proc_inst_id"]
    inc_id = variables(inst).get("incident")
    inc = get(f"{PROCESS}/api/incidents/{inc_id}") if inc_id else {}
    check("incident opened by the instance (AWAITING_APPROVAL)", inc.get("state") == "AWAITING_APPROVAL" and inc.get("alertId") == alert_id, f"{inc_id} {inc.get('state')}")
    check("role_bindings on the instance (the definition's roles)", any(b.get("endpoint") == "role:operator" for b in inst.get("role_bindings") or []), str([b.get("endpoint") for b in inst.get("role_bindings") or []]))
    st = statuses(pid)
    check("every activity planned (TODO) and task:diagnose live for cliagents", len(st) >= 9 and st.get("task:diagnose") in ("IN_PROGRESS", "SUBMITTED", "DONE") and st.get("task:escalate") == "TODO",
          json.dumps(st, ensure_ascii=False))
    first = items(pid)["task:diagnose"]
    check("agent task carries agent_mode=COMPLETE · agent_orch=cliagents · query with [InputData]", first.get("agent_mode") == "COMPLETE" and first.get("agent_orch") == "cliagents" and "[InputData]" in (first.get("query") or ""),
          json.dumps({k: first.get(k) for k in ('agent_mode', 'agent_orch', 'tool', 'user_id')}))

    section("2. 에이전트 작업 4개 (IN_PROGRESS → SUBMITTED → DONE) → 사람의 할일 task:select")
    tl, dt = wait_for(lambda: items(pid) if items(pid).get("task:select", {}).get("status") == "IN_PROGRESS" else None, 900 if expect_worker else 120)   # four coding-agent runs in sequence
    require("four agent tasks DONE and task:select IN_PROGRESS", tl is not None and all(tl[a]["status"] == "DONE" for a in AGENT_TASKS),
            f"after {dt:.0f}s " + json.dumps({k: v['status'] for k, v in (tl or {}).items()}, ensure_ascii=False))
    check("agent rows went through save_task_result (draft_status COMPLETED, consumer released)", all(tl[a].get("draft_status") == "COMPLETED" and tl[a].get("consumer") is None for a in AGENT_TASKS), str({a: tl[a].get("draft_status") for a in AGENT_TASKS}))
    started = [e for e in view(pid)["events"] if e["event_type"] == "task_started"]
    check("agent tasks were done by " + ("the cliagents worker" if expect_worker else "the legacy bridge"),
          bool(started) and (("legacy" in json.dumps(started, ensure_ascii=False)) != expect_worker), f"{len(started)} task_started")
    timer = tl.get("ev:select-timeout") or {}
    check("boundary timer is a work item with a due_date (sys:process)", timer.get("status") == "IN_PROGRESS" and bool(timer.get("due_date")) and timer.get("user_id") == "sys:process", json.dumps({k: timer.get(k) for k in ('status', 'due_date', 'user_id')}))
    vd = variables(view(pid)["instance"])
    check("instance variables carry cause · decision_id (product list shape)", vd.get("cause") == "cause:cooler-fin-fouling" and bool(vd.get("decision_id")), json.dumps({k: vd.get(k) for k in ('cause', 'failure_mode', 'decision_id')}))
    ev_types = [e["event_type"] for e in view(pid)["events"]]
    check("events recorded for the agent tasks", ev_types.count("task_completed") >= 4 and (not expect_worker or "tool_usage_started" in ev_types), f"{len(ev_types)} events: {sorted(set(ev_types))}")
    todo = get(f"{PROCESS}/api/todolist?status=IN_PROGRESS&user_id=role:operator")
    check("operator sees the selection task in the todolist (IN_PROGRESS)", any(t["proc_inst_id"] == pid for t in todo), str(len(todo)))
    sel = tl["task:select"]
    selected_task = get(f"{PROCESS}/api/todolist/{sel['id']}")
    check("selection uses the instance's definition and pinned form", selection_contract_matches(inst, definition, selected_task, form),
          f"version={inst.get('proc_def_version')} form_source={selected_task.get('form_source')}")
    dec = get(f"{PROCESS}/api/decisions/{vd['decision_id']}")
    check("decision holds ranked SOP cards, SOP-COOL-02 recommended", dec.get("recommended") == "skill:fan-max-derate" and len(dec.get("options", [])) >= 2, str([o['sopId'] for o in dec.get('options', [])]))

    section("3. 사람의 선택: 역할 검사 → 폼 제출(SUBMITTED) → 엔진 → gw:control → PLC 명령 (task:command)")
    r = post(f"{PROCESS}/api/todolist/{sel['id']}/select", {"decision": dec["id"], "option": "skill:fan-max-derate", "by": "OP-17", "role": "role:operator", "reason": "test"})
    check("operator refused (403) — card needs 생산관리자", r.get("error") == 403, r.get("body", "")[:100])
    check("selection task still IN_PROGRESS after refusal", get(f"{PROCESS}/api/todolist/{sel['id']}")["status"] == "IN_PROGRESS", "")
    selection = {"decision": dec["id"], "option": "skill:fan-max-derate", "by": "이생산", "role": "role:prod-mgr",
                 "reason": "OEM 납기 오더 진행 중 — 생산을 멈추지 않고 유온을 내린다"}
    if fresh_review:
        reviewed=post(f"{PROCESS}/api/todolist/{sel['id']}/decision-preview",
                      {'decision':dec['id'],'option':selection['option'],'parameters':{}},timeout=60)
        require('current source reviewed before explicit approval',reviewed.get('id')
                and reviewed.get('snapshot',{}).get('options',[{}])[0].get('feasible') is True,
                str(reviewed.get('id') or reviewed.get('body')))
        selection['review_id']=reviewed['id']
        check('review did not issue a PLC command',get(f'{PROCESS}/api/incidents/{inc_id}').get('cmdId') is None)
    r = post(f"{PROCESS}/api/todolist/{sel['id']}/select",selection,timeout=60)
    require("production manager's selection accepted", "instance" in r and not r.get("error"), json.dumps(r.get("body") or {k: str(r.get(k))[:60] for k in ('ended', 'pending')}, ensure_ascii=False)[:160])
    approvals = view(pid).get('approvals') or []
    require('approval intent durably DELIVERED once for this selection',
          len(approvals)==1 and approvals[0]['todo_id']==sel['id'] and approvals[0]['decision_id']==dec['id']
          and approvals[0]['status']=='DELIVERED' and approvals[0]['attempts']==1,
          json.dumps([{k:a.get(k) for k in ('todo_id','decision_id','status','attempts')} for a in approvals]))
    check('approval response distinguishes accepted intent and delivery result',
          r.get('accepted') is True and r.get('approval_status')=='DELIVERED',
          json.dumps({k:r.get(k) for k in ('accepted','approval_status')}))
    tl = items(pid)
    check("task:select DONE with gateway_decisions, timer CANCELLED, task:command dispatched (SUBMITTED/DONE)",
          tl["task:select"]["status"] == "DONE" and (tl["task:select"].get("gateway_decisions") or {}).get("gw:control", {}).get("selected") == ["seq:gw-command"]
          and tl.get("ev:select-timeout", {}).get("status") == "CANCELLED" and tl.get("task:command", {}).get("status") in ("SUBMITTED", "DONE"),
          json.dumps({k: v['status'] for k, v in tl.items()}, ensure_ascii=False))
    # Selection/delivery acceptance is not synchronous PLC dispatch. The service
    # now rereads current sources before it creates a command; observe that
    # separate boundary with a bounded wait, not an immediate cache snapshot.
    inc, command_wait = wait_for(lambda: (v if (v := get(f"{PROCESS}/api/incidents/{inc_id}")).get('cmdId') else None), 30)
    check("incident issued action.cmd (AWAITING_ACK or beyond)", inc is not None and inc["state"] in ("AWAITING_ACK", "ACKED", "RE_OBSERVING", "RESOLVED", "WORK_ORDER_CREATED", "CLOSED"), f"{inc and inc['state']} cmd={inc and inc.get('cmdId')} after {command_wait:.0f}s")

    section("4. ACK → 재관측 → 작업지시(CMMS) → 종결")
    tl, dt = wait_for(lambda: items(pid) if items(pid).get("task:reobserve", {}).get("status") in ("SUBMITTED", "DONE") else None, 60)
    check("PLC ACK → task:command DONE → task:reobserve waiting (SUBMITTED, held by the service)", tl is not None and tl["task:command"]["status"] == "DONE", f"after {dt:.0f}s")
    if restart:
        restart_during_reobserve(pid,inc_id,dec['id'])
    fin, dt = wait_for(lambda: view(pid) if view(pid)["instance"]["status"] == "COMPLETED" else None, 300 * clock_factor)
    require("instance COMPLETED via ev:closed", fin is not None and fin["instance"]["end_event"] == "ev:closed", f"after {dt:.0f}s end_event={fin and fin['instance'].get('end_event')}")
    wi = {w["activity_id"]: w for w in (fin or {}).get("workitems", [])}
    done = {a for a, w in wi.items() if w["status"] == "DONE"}
    check("eight tasks DONE, task:escalate CANCELLED (the branch not taken)", done >= {"task:diagnose", "task:candidates", "task:compliance", "task:rank", "task:select", "task:command", "task:reobserve", "task:work-order"}
          and wi.get("task:escalate", {}).get("status") == "CANCELLED", json.dumps({k: v['status'] for k, v in wi.items()}, ensure_ascii=False))
    wo = (wi.get("task:work-order") or {}).get("output", {}).get("work_order") or {}
    check("CMMS work order created by task:work-order", wo.get("ok") is True and str(wo.get("ref", "")).startswith("WO-"), json.dumps(wo, ensure_ascii=False)[:160])
    tx = get(f"{ENT}/api/transactions")
    check("enterprise transactions include the work order", any(t.get("skill") == "skill:schedule-maintenance" for t in tx), str(len(tx)))
    from probe_work_order_consistency import compare as compare_work_order
    receipt_checks = compare_work_order(fin, get(f"{PROCESS}/api/incidents/{inc_id}"), tx)
    for item in receipt_checks['checks'][1:3]:
        check(item['name'], item['passed'], json.dumps(item, ensure_ascii=False))
    vd = variables(fin["instance"]) if fin else {}
    participants = (fin["instance"].get("participants") or []) if fin else []
    check("recovered=true recorded · participants listed", vd.get("recovered") is True and "role:prod-mgr" in participants, str(participants))

    section("5. 온톨로지 Execution 레이어")
    out = cypher(f"MATCH (pi:ProcessInstance {{id: '{pid}'}})-[:INSTANCE_OF]->(p:Process) MATCH (w:WorkItem)-[:IN_INSTANCE]->(pi) OPTIONAL MATCH (w)-[:EXECUTES]->(t:Task) RETURN p.id, count(w), count(t), pi.status")
    check("ProcessInstance -INSTANCE_OF-> proc:anomaly-response with WorkItem -EXECUTES-> Task, COMPLETED", "proc:anomaly-response" in out and "COMPLETED" in out, out.splitlines()[-1] if out else "")
    out2 = cypher(f"MATCH (pi:ProcessInstance {{id: '{pid}'}})-[:HANDLES]->(i:Incident)-[:DIAGNOSED_AS]->(c:Cause) MATCH (pi)-[rb:ROLE_BOUND]->(r) RETURN i.id, c.id, count(rb)")
    check("instance linked to the incident, its cause and the bound roles", inc_id in out2 and "cause:cooler-fin-fouling" in out2, out2.splitlines()[-1] if out2 else "")

    section("6. 레거시 경로 보존")
    legacy = get(f"{PROCESS}/api/incidents")
    check("incident list still served (legacy API intact)", isinstance(legacy, list) and any(i["id"] == inc_id for i in legacy), str(len(legacy)))

    post(f"{PLANT}/api/reset")
    summary()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", action="store_true", help="expect the cliagents worker (AGENT_BRIDGE=off) instead of the legacy bridge")
    ap.add_argument('--restart-during-reobserve',action='store_true',help='kill/start the real process after PLC ACK; expect human restart review')
    ap.add_argument('--fresh-review',action='store_true',help='explicitly review the current source before approving unchanged SOP values')
    args=ap.parse_args()
    main(args.worker,args.restart_during_reobserve,args.fresh_review)
