"""B7 라이브 — 작동유 열화: 사람 입력(오일 분석 기준 이탈)으로 시작하는 정비형 흐름이 실제 스택에서 끝까지 (HANDOFF A159 · A160).

    .venv/bin/python scripts/probe_b7_oil_live.py --expect legacy --out .evidence/a160/b7-legacy   # AGENT_BRIDGE=legacy, 호스트 워커 정지
    .venv/bin/python scripts/probe_b7_oil_live.py --expect worker --out .evidence/a160/b7-worker   # AGENT_BRIDGE=off, 호스트 워커 1개

순서는 `docs/handoff/verification/2026-10-08/b7-oil.md` "메인이 라이브로 확인할 순서" 그대로다.
  1. 지식: OIL_ANALYSIS 패턴 → 고장 유형 1행, rule:cand-oil -OUTPUTS-> SOP 가 있어야 한다(HM-9 인제스천 뒤 — 없으면 좌표와 함께 멈춘다).
  2. 기준 안 입력 → 경보 없음 + 사유, 처리 건 0.
  3. 학생 그림 예(`tests/fixtures/bpmn/oil_maintenance_student.bpmn`)를 B3 로 가져와 부품 · 담당을 매핑 → 사전 검사 → 판본 등록 → B4 배포.
  4. 기준 이탈 입력 → 배포된 흐름의 처리 건 · 사건.
  5. 두 바퀴: 판단(내장 결정론 또는 실제 워커) → 카드 SOP-OIL-21 → 운전원 승인 거절(403) → 정비관리자 승인 → 작업지시 →
     재분석 입력(1바퀴 "비정상" → 사건 다시 승인 대기 · 첫 작업지시 superseded, 2바퀴 "정상").
  6. 끝: 처리 건 COMPLETED(종결) · 작업지시 2건(업무 DB 행 2) · 설비 명령 0건(사건 cmdId 없음 · 감사에 명령 이벤트 없음 ·
     cmd-gateway 로그에 이 검사 동안 명령 0) · 기록 INCIDENT_REOPENED_RECHECK.
  worker 모드는 원인 진단 task 를 실제 워커(cliagents)가 집었는지와 도구 호출 이벤트를 함께 본다.
검사가 등록한 흐름은 남는다(학생 구성 — 끝나면 포털 "기준으로 되돌리기"). 정답 하드코딩 없음: 카드는 서버가 낸 것에서 SOP 로 찾는다.
"""
import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = "http://127.0.0.1"
PROCESS, AGENT = f"{H}:8080", f"{H}:8091"
FIXTURE = ROOT / "tests/fixtures/bpmn/oil_maintenance_student.bpmn"
# 학생 그림 예의 칸(tests/test_b7_oil.py 와 같은 id) — 학생이 포털 매핑 표에서 그림 이름을 보고 고르는 것
DIAG, CAND, COMP, RANK = "Activity_0diag7o", "Activity_1cand2o", "Activity_0comp3o", "Activity_1rank4o"
SELECT, WO, RECHECK, BOSS = "Activity_0slct5o", "Activity_1wo7o", "Activity_1chk8o", "Activity_0boss1o"
AGENT_TASKS = (DIAG, CAND, COMP, RANK)
SOP = "SOP-OIL-21"
ENTRY = {"pattern": "OIL_ANALYSIS", "asset": "HYD-01", "item": "water", "value": 620, "out_of_spec": True,
         "memo": "[검사] 정기 분석 — 수분 증가", "by": "user:park-maint", "by_name": "박정비", "role": "role:maint-mgr"}
COMMAND_EVENTS = {"ACTION_CMD", "COMMAND_ISSUED", "CMD_PUBLISHED", "ACK"}

results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)[:600]))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}  {str(detail)[:400]}", flush=True)
    return bool(ok)


def call(method, url, data=None, timeout=60):
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw and raw[:1] in b"{[" else raw.decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw


def get(url):
    code, body = call("GET", url)
    if code != 200:
        raise RuntimeError(f"GET {url} → {code} {str(body)[:300]}")
    return body


def wait_for(fn, timeout, every=2.0):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        last = fn()
        if last:
            return last, time.time() - t0
        time.sleep(every)
    return None, time.time() - t0


def variables(inst):
    return {v["key"]: v.get("value") for v in (inst.get("variables_data") or [])}


def cypher(q):
    r = subprocess.run(["docker", "exec", "hyd-iot-edu-neo4j-1", "cypher-shell", "-u", "neo4j", "-p", "hydpass123", "--format", "plain", q],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"cypher-shell rc={r.returncode}: {r.stderr[:300]}")
    return [ln for ln in r.stdout.strip().splitlines()[1:] if ln.strip()]


def ent(sql):
    r = subprocess.run(["docker", "exec", "supabase_db_hyd-iot-edu", "psql", "-U", "postgres", "-d", "postgres", "-At", "-F", "|", "-c", sql],
                       capture_output=True, text=True, encoding="utf-8", timeout=30)
    if r.returncode != 0:
        raise RuntimeError(f"psql: {r.stderr[:300]}")
    return r.stdout.strip()


def gateway_lines(since_iso):
    r = subprocess.run(["docker", "logs", "--since", since_iso, "hyd-iot-edu-cmd-gateway-1"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=30)
    if r.returncode != 0:
        raise RuntimeError(f"docker logs cmd-gateway: {r.stderr[:300]}")
    return [ln for ln in (r.stdout + r.stderr).splitlines() if ln.strip()]


def worker_health():
    for port in (8097, 8098):
        try:
            with urllib.request.urlopen(f"{H}:{port}/health", timeout=3) as r:
                return port, json.loads(r.read())
        except Exception:  # noqa: BLE001
            continue
    return None, None


def oil_mapping(base_mapping):
    """학생이 포털 매핑 표에서 고르는 것 — tests/test_b7_oil.py oil_mapping 과 같은 선택(시작 조건 · 부품 · 담당 · 분기 조건)."""
    m = json.loads(json.dumps(base_mapping))
    m["start"] = {"kind": "alert", "patterns": ["OIL_ANALYSIS"]}
    m["tasks"] = {DIAG: {"part": "task:diagnose"}, CAND: {"part": "task:candidates"}, COMP: {"part": "task:compliance"},
                  RANK: {"part": "task:rank"}, SELECT: {"part": "task:select", "role": "정비관리자"}, WO: {"part": "task:work-order"},
                  RECHECK: {"part": "human", "role": "정비관리자", "inputs": ["work_order"],
                            "fields": [{"key": "recheck_result", "text": "재분석 결과", "type": "select", "items": ["정상", "비정상"]},
                                       {"key": "recheck_note", "text": "메모", "type": "textarea", "required": False}]},
                  BOSS: {"part": "human", "role": "생산관리자", "inputs": ["decision"],
                         "fields": [{"key": "boss_note", "text": "확인 메모", "type": "textarea", "required": False}]}}
    m["flows"] = {"Flow_0ok9": {"var": "recheck_result", "op": "==", "value": "정상"}, "Flow_1again": {"default": True}}
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--expect", choices=["legacy", "worker"], required=True)
    ap.add_argument("--def-id", default="my_oil")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    save = lambda name, v: (out / f"{name}.json").write_text(json.dumps(v, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    agent_wait = 300 if a.expect == "legacy" else 1500
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        run(a, save, agent_wait, started)
    finally:
        (out / "checks.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    failed = [r for r in results if not r[1]]
    print(f"\n{'ALL PASS' if not failed else str(len(failed)) + ' FAILED'} — {len(results) - len(failed)}/{len(results)} checks")
    for name, _, detail in failed:
        print("  FAILED:", name, detail)
    sys.exit(1 if failed else 0)


def run(a, save, agent_wait, started):
    # 0. 모드
    mode = get(f"{PROCESS}/api/process/mode")
    bridge = "legacy" if a.expect == "legacy" else "off"
    port, wh = worker_health()
    if not check(f"process instance 모드 · AGENT_BRIDGE={bridge}", mode.get("mode") == "instance" and mode.get("agent_bridge") == bridge, json.dumps(mode)):
        return
    if a.expect == "legacy":
        if not check("호스트 워커 정지(워커가 내장 판단의 에이전트 작업을 가져가지 않게)", wh is None, f"port {port}"):
            return
    elif not check("호스트 워커 응답", wh is not None and wh.get("status") in ("ok", "starting"), json.dumps(wh)):
        return

    # 1. 지식 상태
    fm = cypher("MATCH (p:AnomalyPattern {code:'OIL_ANALYSIS'})-[:DETECTS]->(:Symptom)-[:INDICATES]->(f:FailureMode) RETURN p.id, f.id;")
    check("지식: OIL_ANALYSIS 패턴 → 증상 → 고장 유형 1행", len(fm) == 1, fm)
    sops = cypher("MATCH (:Rule {id:'rule:cand-oil'})-[:OUTPUTS]->(s) RETURN s.id;")
    if not check(f"지식: rule:cand-oil 이 조치를 내놓음(HM-9 인제스천 뒤) — {SOP}", any(SOP in s for s in sops),
                 f"{sops} — 없으면 먼저 scripts/probe_expert_answers_a098.py(워커 필요)로 HM-9 를 적재"):
        return

    # 2. 기준 안 입력 → 경보 없음
    before = len(get(f"{PROCESS}/api/instances?limit=500"))
    code, r = call("POST", f"{PROCESS}/api/human-alerts", dict(ENTRY, out_of_spec=False))
    save("2-in-spec", r)
    check("기준 안 입력 → 경보 없음 + 사유", code == 200 and r.get("raised") is False and r.get("reason"), r)
    check("기준 안 입력 → 처리 건 0", len(get(f"{PROCESS}/api/instances?limit=500")) == before, before)

    # 3. 흐름 가져오기 · 매핑 · 사전 검사 · 등록 · 배포
    code, imp = call("POST", f"{PROCESS}/api/flows/import", {"xml": FIXTURE.read_text(encoding="utf-8"), "file_name": FIXTURE.name,
                                                              "definition_id": a.def_id})
    save("3-import", imp)
    if not check("흐름 가져오기(.bpmn)", code == 200 and isinstance(imp, dict) and imp.get("mapping"), f"{code} {str(imp)[:300]}"):
        return
    mapping = oil_mapping(imp["mapping"])
    code, chk = call("POST", f"{PROCESS}/api/flows/{a.def_id}/check", {"mapping": mapping})
    save("3-check", chk)
    problems = (chk.get("check") or chk).get("problems") if isinstance(chk, dict) else chk
    if not check("사전 검사 통과", code == 200 and not problems, f"{code} {json.dumps(problems, ensure_ascii=False)[:400]}"):
        return
    code, reg = call("POST", f"{PROCESS}/api/flows/{a.def_id}/register", {"mapping": mapping})
    save("3-register", reg)
    if not check("판본 등록", code == 201 and reg.get("version"), f"{code} {str(reg)[:300]}"):
        return
    version = reg["version"]
    tools = {x["id"]: x.get("tool") for x in reg["definition"]["activities"]}
    check("등록된 흐름에 설비 명령 부품 없음 · 작업지시는 CMMS", "incident:command" not in tools.values() and tools.get(WO) == "enterprise:WO_CREATE", tools)
    code, dep = call("POST", f"{PROCESS}/api/process/definitions/{a.def_id}/deploy", {"version": version, "by": "[검사] 학생1",
                                                                                     "reason": "[검사] 작동유 흐름 배포"})
    save("3-deploy", dep)
    if not check(f"판본 {version} 배포", code == 200, f"{code} {str(dep)[:300]}"):
        return

    # 4. 기준 이탈 입력 → 배포 흐름의 처리 건 · 사건
    code, raised = call("POST", f"{PROCESS}/api/human-alerts", ENTRY)
    save("4-raised", raised)
    ok = code == 200 and raised.get("raised") is True and raised.get("route") == "response" and \
        raised.get("definition", {}).get("definition") == a.def_id and raised.get("instance") and raised.get("incident")
    if not check("기준 이탈 입력 → 배포된 흐름이 처리 건 · 사건을 엶", ok, f"{code} {json.dumps(raised, ensure_ascii=False)[:400]}"):
        return
    pid, inc_id, alert_id = raised["instance"], raised["incident"], raised["alert"]["alertId"]
    print(f"  처리 건 {pid} · 사건 {inc_id} · 경보 {alert_id}", flush=True)
    inc = get(f"{PROCESS}/api/incidents/{inc_id}")
    check("사건 화면에 출처 사람 입력 · 입력자", (inc.get("card") or {}).get("alert", {}).get("source") == "human_input" or
          json.dumps(inc, ensure_ascii=False).count("박정비") > 0, json.dumps((inc.get("card") or {}).get("alert"), ensure_ascii=False)[:300])

    view = lambda: get(f"{PROCESS}/api/instances/{pid}")
    rows = lambda v, aid: [w for w in v["workitems"] if w["activity_id"] == aid]
    seen_select = set()

    for n, verdict in ((1, "비정상"), (2, "정상")):
        print(f"\n== 바퀴 {n}", flush=True)

        def selection_open():
            v = view()
            held = [w for w in v["workitems"] if w["activity_id"] in AGENT_TASKS and w["status"] in ("PENDING", "FAILED")]
            if held:
                return {"stopped": held, "view": v}
            live = [w for w in rows(v, SELECT) if w["status"] == "IN_PROGRESS" and w["id"] not in seen_select]
            return {"select": live[0], "view": v} if live else None
        got, dt = wait_for(selection_open, agent_wait)
        if got and got.get("stopped"):
            save(f"5-{n}-stopped", got)
            check(f"바퀴 {n}: 에이전트 작업이 멈추지 않음", False, json.dumps([(w["activity_id"], w["status"], w.get("log")) for w in got["stopped"]],
                                                                      ensure_ascii=False)[:500])
            return
        if not check(f"바퀴 {n}: 에이전트 4작업 → 정비 조치 선택 열림", got is not None, f"{dt:.0f}s"):
            save(f"5-{n}-timeout", view())
            return
        v, sel = got["view"], got["select"]
        seen_select.add(sel["id"])
        done = {aid: [w["status"] for w in rows(v, aid)].count("DONE") for aid in AGENT_TASKS}
        check(f"바퀴 {n}: 에이전트 4작업 DONE {n}회씩", all(c == n for c in done.values()), f"{done} {dt:.0f}s")
        d_id = variables(v["instance"]).get("decision_id")
        dec = get(f"{PROCESS}/api/decisions/{d_id}")
        save(f"5-{n}-decision", dec)
        opt = next((o for o in dec.get("options", []) if o.get("sopId") == SOP), None)
        if not check(f"바퀴 {n}: 카드에 {SOP}(작업지시형 · 설비 명령 없음)", opt is not None and opt.get("kind") == "work_order",
                     json.dumps([(o.get("id"), o.get("sopId"), o.get("kind"), o.get("feasible")) for o in dec.get("options", [])], ensure_ascii=False)):
            return
        inc = get(f"{PROCESS}/api/incidents/{inc_id}")
        check(f"바퀴 {n}: 사건 승인 대기", inc.get("state") == "AWAITING_APPROVAL", inc.get("state"))
        code, rv = call("POST", f"{PROCESS}/api/todolist/{sel['id']}/decision-preview", {"decision": d_id, "option": opt["id"], "parameters": {}})
        if not check(f"바퀴 {n}: 승인 전 현재 원천 검토", code == 200 and rv.get("id"), f"{code} {str(rv)[:300]}"):
            return
        code, deny = call("POST", f"{PROCESS}/api/todolist/{sel['id']}/select",
                          {"decision": d_id, "option": opt["id"], "review_id": rv["id"], "by": "박운전", "role": "role:operator",
                           "reason": "[검사] 운전원은 정비 카드를 승인할 수 없어야 한다"})
        check(f"바퀴 {n}: 운전원 승인 거절(403)", code == 403, f"{code} {str(deny)[:200]}")
        code, ok_sel = call("POST", f"{PROCESS}/api/todolist/{sel['id']}/select",
                            {"decision": d_id, "option": opt["id"], "review_id": rv["id"], "by": "박정비", "role": "role:maint-mgr",
                             "reason": f"[검사] 수분 증가 — 작동유 교체 {n}회차"})
        save(f"5-{n}-select", ok_sel)
        if not check(f"바퀴 {n}: 정비관리자 승인", code == 200, f"{code} {str(ok_sel)[:300]}"):
            return

        def recheck_open():
            v = view()
            live = [w for w in rows(v, RECHECK) if w["status"] == "IN_PROGRESS"]
            wo_done = [w for w in rows(v, WO) if w["status"] == "DONE"]
            return {"recheck": live[0], "view": v, "wo": wo_done} if live and len(wo_done) == n else None
        got, dt = wait_for(recheck_open, 180)
        if not check(f"바퀴 {n}: 작업지시 DONE {n}건 → 재분석 입력 열림", got is not None, f"{dt:.0f}s"):
            save(f"5-{n}-no-recheck", view())
            return
        wo = (got["wo"][-1].get("output") or {}).get("work_order") or {}
        check(f"바퀴 {n}: CMMS 작업지시 번호", wo.get("ok") is True and str(wo.get("ref", "")).startswith("WO-"), json.dumps(wo, ensure_ascii=False)[:300])
        inc = get(f"{PROCESS}/api/incidents/{inc_id}")
        check(f"바퀴 {n}: 사건 작업지시로 닫힘 · 설비 명령 없음", inc.get("state") == "CLOSED" and not inc.get("cmdId")
              and (inc.get("workOrder") or {}).get("ref") == wo.get("ref"),
              json.dumps({"state": inc.get("state"), "cmdId": inc.get("cmdId"), "workOrder": inc.get("workOrder")}, ensure_ascii=False)[:300])
        code, sub = call("POST", f"{PROCESS}/api/todolist/{got['recheck']['id']}/submit",
                         {"output": {"recheck_result": verdict, "recheck_note": f"[검사] {n}회차 재분석 {verdict}"}, "by": "박정비"})
        save(f"5-{n}-recheck", sub)
        if not check(f"바퀴 {n}: 재분석 \"{verdict}\" 제출", code == 200, f"{code} {str(sub)[:300]}"):
            return
        if verdict == "비정상":
            def reopened():
                i = get(f"{PROCESS}/api/incidents/{inc_id}")
                return i if i.get("state") == "AWAITING_APPROVAL" else None
            i, dt = wait_for(reopened, 60)
            sup = (i or {}).get("superseded") or []
            check("비정상 → 사건 다시 승인 대기 · 첫 작업지시 superseded(recheck)", i is not None and sup and sup[-1].get("kind") == "recheck"
                  and (sup[-1].get("workOrder") or {}).get("ref") == wo.get("ref"),
                  json.dumps({"state": (i or {}).get("state"), "superseded": sup}, ensure_ascii=False)[:400])

    # 6. 끝
    def completed():
        v = view()
        return v if v["instance"]["status"] == "COMPLETED" else None
    fin, dt = wait_for(completed, 60)
    if not check("처리 건 COMPLETED(종결)", fin is not None and fin["instance"].get("end_event") == "Event_1done0o",
                 f"{dt:.0f}s end_event={(fin or {}).get('instance', {}).get('end_event')}"):
        save("6-final", view())
        return
    save("6-final", fin)
    wos = [(w.get("output") or {}).get("work_order") or {} for w in rows(fin, WO) if w["status"] == "DONE"]
    refs = sorted({w.get("ref") for w in wos if w.get("ref")})
    check("작업지시 2건(서로 다른 번호)", len(wos) == 2 and len(refs) == 2, refs)
    if refs:
        db_rows = ent("select count(*) from ent.work_orders where id in (" + ",".join(f"'{r}'" for r in refs) + ")")
        check("업무 DB ent.work_orders 에 2행", db_rows == "2", db_rows)
    inc = get(f"{PROCESS}/api/incidents/{inc_id}")
    save("6-incident", inc)
    check("사건 cmdId 없음", not inc.get("cmdId"), inc.get("cmdId"))
    audits = [x for x in get(f"{PROCESS}/api/audit") if x.get("incident") == inc_id]
    save("6-audit", audits)
    check("감사 기록에 설비 명령 이벤트 0", not any(x.get("event") in COMMAND_EVENTS for x in audits), sorted({x.get("event") for x in audits}))
    gw = gateway_lines(started)
    (Path(a.out) / "6-cmd-gateway.log").write_text("\n".join(gw), encoding="utf-8")
    # cmd-gateway 가 명령을 처리하면 "cmd CMD-… -> plant/hyd01/cmd/<mode> PASS|REJECT" 한 줄을 남긴다(경보 중계 줄은 "alert relayed")
    cmd_lines = [ln for ln in gw if re.search(r"\bcmd CMD-\S+ -> plant/hyd01/cmd/", ln)]
    check("cmd-gateway 로그에 이 검사 동안 명령 0", not cmd_lines, cmd_lines[:3])
    events = fin.get("events") or []
    check("기록에 INCIDENT_REOPENED_RECHECK", any(e.get("job_id") == "INCIDENT_REOPENED_RECHECK" or e.get("event_type") == "INCIDENT_REOPENED_RECHECK"
                                                  for e in events), sorted({e.get("job_id") for e in events if e.get("job_id")})[:20])
    diag = [w for w in rows(fin, DIAG) if w["status"] == "DONE"]
    dump = json.dumps([w.get("output") for w in diag], ensure_ascii=False)
    where = {"task 출력": f"human:{alert_id}" in dump, "기록(events)": f"human:{alert_id}" in json.dumps(events, ensure_ascii=False)}
    if a.expect == "legacy":   # 내장 결정론 판단은 agent 서비스 실행 기록에 카드(원인 · 증거)를 남긴다
        runs = [r for r in get(f"{AGENT}/api/agent/runs") if r.get("alertId") == alert_id]
        save("6-agent-runs", runs)
        where["agent 실행 기록"] = f"human:{alert_id}" in json.dumps(runs, ensure_ascii=False)
    check("원인 진단 근거 = 사람 입력 분석(human:<경보>)", any(where.values()), json.dumps(where, ensure_ascii=False) + " " + dump[:200])
    if a.expect == "worker":
        orch = sorted({(w.get("agent_orch"), w.get("consumer")) for w in diag}, key=str)
        check("원인 진단을 실제 워커(cliagents)가 수행", all(o == "cliagents" and c and "worker" in c for o, c in orch), orch)
        diag_ids = {w["id"] for w in diag}
        tool_ev = [e for e in events if e.get("todo_id") in diag_ids and str(e.get("event_type", "")).startswith("tool_usage")]
        save("6-diagnose-tool-events", tool_ev)
        names = sorted({json.dumps((e.get("data") or {}).get("tool_name") or (e.get("data") or {}).get("name") or "", ensure_ascii=False)
                        for e in tool_ev})
        check("원인 진단 도구 호출 이벤트가 남음(콘솔 · 포털에 보이는 것)", len(tool_ev) > 0, names[:12])


if __name__ == "__main__":
    main()
