"""실라버스 9 · 10일차의 일곱 결말을 라이브 스택에서 한 번에 하나씩 끝까지 돌리고 처리 기록 · 결과 보고를 확인한다(실제 워커 필요).

  .venv/bin/python scripts/syllabus_endings_live.py ENDING OUTDIR
  ENDING: A-normal | A-reject | A-shortfall | B-normal | B-shortfall | C-normal | C-late

앞서 할 일(docs/handoff/NOW.md 2절 '버튼 완주 순서'): 잠금 → 그래프 구조판 → `scripts/c3_flows.py deploy` → 워커 1개.
포털 버튼이 부르는 것과 같은 process API 만 쓴다(화면 조작 없음 — 새 버튼은 포털 작업자 몫이라 아직 화면에 없다):
  시작        POST /api/scenario/A/degrade · /api/scenario/A/degrade-stuck-fan(수업 입력: 조치 미달) · /api/scenario/{B|C}/start
  수업 입력   POST /api/scenario/B/poor-maintenance(시운전 미달, 시작 전에) · /api/scenario/C/delay-delivery(납기 초과, 발주 뒤에)
  사람 승인   POST /api/todolist/{id}/select (에이전트 추천 카드, 그 단계 역할의 사람으로) · /api/todolist/{id}/reject-card (A-reject)
  끝난 뒤     POST /api/scenario/A/restore · /api/scenario/{B|C}/reset (다음 결말을 위해 수업 시작 상태로)
결말은 흐름의 실제 판정(재관측 · 시운전 · 납기 타이머)이 낸다 — 이 스크립트는 결과 값을 넣지 않는다. 확인은 처리 건의 끝 이벤트 ·
결과 보고 · 사건 상태 · 처리 기록(events)을 읽어서 하고, OUTDIR 에 처리 건 원문(JSON)과 확인 표를 남긴다. 확인이 하나라도 틀리면 종료 1.
에이전트 task 가 실패(워커 한도 등)하면 그 사유를 그대로 적고 종료 2 — 끝난 척하지 않는다."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

API = os.environ.get("PROCESS_URL", "http://127.0.0.1:8080")
PLANT = os.environ.get("PLANT_SIM_HOST_URL", "http://127.0.0.1:8000")
AGENT_WAIT_S, END_WAIT_S, POLL_S = 900, 900, 3
CLEAR_TS1 = 50.0          # [쿨러 복구] 뒤 다음 주입 전에 유온이 이 아래로 내려오길 기다린다(경보 해제선 52 ℃ 아래)

#: 결말 → 시작 방법 · 승인자(포털의 '나') · 기대(끝 이벤트 · 결과 보고 · 사건 상태 · 처리 기록에 있어야/없어야 할 줄)
ENDINGS = {
    "A-normal": {"flow": "c3_cooling", "asset": "HYD-01", "start": "/api/scenario/A/degrade", "me": ("user:kim-op", "role:operator"),
                 "end": "E_ok", "outcome": "정상", "incident": "CLOSED", "jobs": ["APPROVAL_ACCEPTED", "RESULT_REPORT"], "no_jobs": ["APPROVAL_REJECTED"],
                 "done": ["T_cmd", "T_reobs", "T_wo", "R_ok"], "after": "/api/scenario/A/restore"},
    "A-reject": {"flow": "c3_cooling", "asset": "HYD-01", "start": "/api/scenario/A/degrade", "me": ("user:kim-op", "role:operator"),
                 "reject": "생산 납기가 급해 지금은 설비 조건을 바꾸지 않습니다 (수업: 승인 거절)",
                 "end": "E_rejected", "outcome": "반려", "incident": "REJECTED_BY_OPERATOR", "jobs": ["APPROVAL_REJECTED", "RESULT_REPORT"],
                 "no_jobs": ["APPROVAL_ACCEPTED"], "done": ["R_rejected"], "not_started": ["T_cmd", "T_reobs", "T_wo"], "after": "/api/scenario/A/restore"},
    "A-shortfall": {"flow": "c3_cooling", "asset": "HYD-01", "start": "/api/scenario/A/degrade-stuck-fan", "me": ("user:kim-op", "role:operator"),
                    "end": "E_fail", "outcome": "미달", "incident": "ESCALATED", "jobs": ["APPROVAL_ACCEPTED", "RESULT_REPORT"],
                    "class_input": "조치 미달", "done": ["T_cmd", "T_reobs", "R_fail"], "not_started": ["T_wo"], "after": "/api/scenario/A/restore"},
    "B-normal": {"flow": "c3_pm", "asset": "HYD-02", "start": "/api/scenario/B/start", "me": ("user:park-maint", "role:maint-mgr"),
                 "end": "E_ok", "outcome": "정상", "jobs": ["WORK_ORDER_REGISTERED", "MAINTENANCE_DONE", "TEST_RUN", "PM_COUNTER_RESET", "RESULT_REPORT"],
                 "wait_jobs": ["WAIT_STARTED", "WAIT_SKIPPED"], "done": ["T_wo", "T_wait", "T_do", "T_run", "R_ok"], "after": "/api/scenario/B/reset"},
    "B-shortfall": {"flow": "c3_pm", "asset": "HYD-02", "before": "/api/scenario/B/poor-maintenance", "start": "/api/scenario/B/start",
                    "me": ("user:park-maint", "role:maint-mgr"), "end": "E_fail", "outcome": "미달",
                    "jobs": ["WORK_ORDER_REGISTERED", "MAINTENANCE_DONE", "TEST_RUN", "PM_COUNTER_KEPT", "RESULT_REPORT"], "no_jobs": ["PM_COUNTER_RESET"],
                    "wait_jobs": ["WAIT_STARTED", "WAIT_SKIPPED"], "class_input": "시운전 미달", "done": ["T_wo", "T_wait", "T_do", "T_run", "R_fail"],
                    "after": "/api/scenario/B/reset"},
    "C-normal": {"flow": "c3_spare", "asset": "HYD-03", "start": "/api/scenario/C/start", "me": ("user:jung-buy", "role:purchasing"),
                 "end": "E_ok", "outcome": "입고 완료", "incident": "CLOSED",
                 "jobs": ["PURCHASE_ORDERED", "MCP_EFFECT_CALL", "RECEIPT_WAIT", "RECEIPT_MATCH", "GOODS_RECEIVED", "RESULT_REPORT"],
                 "done": ["T_po", "T_mail", "T_gr", "R_ok"], "after": "/api/scenario/C/reset"},
    "C-late": {"flow": "c3_spare", "asset": "HYD-03", "start": "/api/scenario/C/start", "me": ("user:jung-buy", "role:purchasing"),
               "during": "/api/scenario/C/delay-delivery", "end": "E_late", "outcome": "지연", "incident": "ESCALATED",
               "jobs": ["PURCHASE_ORDERED", "MCP_EFFECT_CALL", "RECEIPT_WAIT", "RECEIPT_DELAYED", "RESULT_REPORT"], "no_jobs": ["GOODS_RECEIVED"],
               "class_input": "납기 초과", "done": ["T_po", "T_mail", "R_late"], "after": "/api/scenario/C/reset"},
}
LOG: list[str] = []
CHECKS: list[dict] = []


def log(msg: str) -> None:
    line = f"{datetime.now().strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    LOG.append(line)


def call(method: str, url: str, body=None) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {url} → {e.code}: {e.read().decode(errors='replace')[:800]}")


def get(path: str) -> dict:
    return call("GET", API + path)


def post(path: str, body: dict) -> dict:
    return call("POST", API + path, body)


def check(name: str, ok: bool, detail="") -> None:
    CHECKS.append({"check": name, "ok": bool(ok), "detail": detail})
    log(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""))


def values(view: dict) -> dict:
    return {v["name"]: v.get("value") for v in view["instance"].get("variables_data") or []}


def rows(view: dict) -> dict:
    """활동마다 가장 최근 행."""
    out: dict = {}
    for w in sorted(view["workitems"], key=lambda w: str(w.get("start_date") or "")):
        out[w["activity_id"]] = w
    return out


def wait_instance(flow: str, known: set, timeout_s: int) -> str:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        new = [i for i in get("/api/instances?limit=100") if i["proc_inst_id"] not in known and i.get("proc_def_id") == flow]
        if new:
            return new[0]["proc_inst_id"]
        time.sleep(POLL_S)
    raise SystemExit(f"{timeout_s}초 안에 {flow} 처리 건이 열리지 않았습니다 — 흐름 배포(c3_flows.py deploy) · 감지기 · 설비 상태를 확인하세요")


def wait_approval(pid: str) -> dict:
    """에이전트 판단이 끝나 승인 task 가 열릴 때까지. 에이전트 task 가 실패로 멈추면(PENDING · 실패 기록) 사유와 함께 종료 2."""
    t0 = time.time()
    while time.time() - t0 < AGENT_WAIT_S:
        view = get(f"/api/instances/{pid}")
        r = rows(view)
        agent, approve = r.get("T_agent") or {}, r.get("T_approve") or {}
        if agent.get("status") == "DONE" and approve.get("status") == "IN_PROGRESS":
            log(f"승인 대기 — 에이전트 {time.time() - t0:.0f}초")
            return view
        failed = [e for e in view["events"] if e.get("event_type") in ("error", "task_failed") or e.get("job_id") in ("RunFailed", "TASK_ERROR")]
        if agent.get("status") == "PENDING" or view["instance"]["status"] != "RUNNING":
            reason = json.dumps([(e.get("job_id"), (e.get("data") or {}).get("friendly") or (e.get("data") or {}).get("error")) for e in failed[-3:]],
                                ensure_ascii=False)
            print(f"미완: 에이전트 task 가 {agent.get('status')} 로 멈췄습니다 — {reason}\n{agent.get('log')}", file=sys.stderr)
            raise SystemExit(2)
        time.sleep(POLL_S)
    print(f"미완: {AGENT_WAIT_S}초 안에 승인 task 가 열리지 않았습니다(워커가 도는지 확인)", file=sys.stderr)
    raise SystemExit(2)


def wait_end(pid: str, during=None) -> dict:
    t0, pressed = time.time(), during is None
    while time.time() - t0 < END_WAIT_S:
        view = get(f"/api/instances/{pid}")
        if not pressed and isinstance(values(view).get("purchase_order"), dict) and (rows(view).get("T_gr") or {}).get("status") == "SUBMITTED":
            res = post(during, {"by": "강사 (수업 입력)"})          # 발주가 나고 입고 대기가 시작된 뒤에 원인을 준다
            log(f"수업 입력 {during}: {res.get('cause')} (days {res.get('days')})")
            pressed = True
        if view["instance"]["status"] != "RUNNING":
            log(f"처리 건 종료 {view['instance']['status']} — 승인 뒤 {time.time() - t0:.0f}초")
            return view
        stuck = [w for w in view["workitems"] if w["status"] == "PENDING"]
        if stuck:
            raise SystemExit(f"task {stuck[0]['activity_id']} 가 PENDING 으로 멈췄습니다: {stuck[0].get('log')}")
        time.sleep(POLL_S)
    raise SystemExit(f"{END_WAIT_S}초 안에 처리 건이 끝나지 않았습니다: 현재 {view['instance'].get('current_activity_ids')}")


def plant_unit(asset: str) -> dict:
    return call("GET", PLANT + "/api/state")["units"][asset]


def restore_and_wait_clear(spec: dict) -> None:
    """다음 결말을 위해 수업 시작 상태로. A 는 유온이 식을 때까지 기다린다(경보가 풀려야 다음 주입이 새 경보를 낸다)."""
    res = post(spec["after"], {"by": "강사 (수업 정리)"})
    log(f"정리 {spec['after']}: {json.dumps({k: res.get(k) for k in ('button', 'instance', 'reanchored')}, ensure_ascii=False)}")
    if spec["asset"] != "HYD-01":
        return
    t0 = time.time()
    while time.time() - t0 < 600:
        unit = plant_unit("HYD-01")
        if unit["tags"]["TS1"] < CLEAR_TS1 and unit["disturbances"]["cooler_health"] == 1.0 and unit["status"].get("state", "RUN") == "RUN":
            log(f"HYD-01 유온 {unit['tags']['TS1']} ℃ — 정상으로 돌아옴 ({time.time() - t0:.0f}초)")
            return
        time.sleep(5)
    raise SystemExit("HYD-01 이 600초 안에 정상으로 돌아오지 않았습니다 — 설비 상태를 확인하세요(보호 정지면 Reset 필요)")


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in ENDINGS:
        print(__doc__, file=sys.stderr)
        return 2
    name, out = argv[1], Path(argv[2])
    spec = ENDINGS[name]
    out.mkdir(parents=True, exist_ok=True)
    me, role = spec["me"]
    known = {i["proc_inst_id"] for i in get("/api/instances?limit=100")}
    fan_before = plant_unit(spec["asset"])["tags"]["FanSpeedSP"]
    if spec.get("before"):
        res = post(spec["before"], {"by": "강사 (수업 입력)"})
        log(f"수업 입력 {spec['before']}: {res.get('cause')}")
    started = post(spec["start"], {"by": "강사", "user_id": me, "roles": [role]})
    log(f"시작 {spec['start']}: {json.dumps({k: started.get(k) for k in ('button', 'instance', 'class_input', 'reanchored')}, ensure_ascii=False)}")
    pid = started.get("instance") or wait_instance(spec["flow"], known, 600)
    log(f"처리 건 {pid}")
    view = wait_approval(pid)
    decision_id = values(view)["decision_id"]
    decision = get(f"/api/decisions/{decision_id}")
    wid = rows(view)["T_approve"]["id"]
    (out / f"{name}-at-approval.json").write_text(json.dumps({"view": view, "decision": decision}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    check("승인 전 설비 쓰기 없음 (사건에 명령 id 없음 · 효과 task 미시작)",
          not get(f"/api/incidents/{values(view)['incident']}").get("cmdId")
          and all(w["status"] == "TODO" for w in view["workitems"] if w["activity_id"] in ("T_cmd", "T_wo", "T_po", "T_mail", "T_do", "T_gr", "T_run")))
    if spec.get("reject"):
        res = post(f"/api/todolist/{wid}/reject-card", {"decision": decision_id, "by": me, "role": role, "reason": spec["reject"]})
        log(f"거절 접수: {res.get('approval')}")
    else:
        res = post(f"/api/todolist/{wid}/select", {"decision": decision_id, "option": decision["recommended"], "by": me, "role": role,
                                                   "reason": "수업: 추천안 승인"})
        log(f"승인 접수: {decision['recommended']} ({res.get('approval_status')})")
    view = wait_end(pid, spec.get("during"))
    v, r = values(view), rows(view)
    jobs = [e.get("job_id") for e in view["events"]]
    incident = get(f"/api/incidents/{v['incident']}") if v.get("incident") else {}
    report = v.get("result_report") or {}
    (out / f"{name}-final.json").write_text(json.dumps({"view": view, "incident": incident, "decision": get(f"/api/decisions/{decision_id}"),
                                                        "plant": plant_unit(spec["asset"])}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    check("처리 건이 끝났다 (COMPLETED)", view["instance"]["status"] == "COMPLETED", view["instance"]["status"])
    check(f"끝 이벤트 {spec['end']}", view["instance"].get("end_event") == spec["end"], str(view["instance"].get("end_event")))
    check(f"결과 보고 '{spec['outcome']}'", report.get("outcome") == spec["outcome"], f"{report.get('outcome')} — {report.get('title')}: {report.get('summary')}")
    if spec.get("incident"):
        check(f"사건 상태 {spec['incident']}", incident.get("state") == spec["incident"], str(incident.get("state")))
    for job in spec.get("jobs", []):
        check(f"처리 기록에 {job}", job in jobs)
    for job in spec.get("no_jobs", []):
        check(f"처리 기록에 {job} 없음", job not in jobs)
    if spec.get("wait_jobs"):
        check("처리 기록에 예약 시각 대기(시작 또는 즉시 시행)", any(j in jobs for j in spec["wait_jobs"]), str([j for j in jobs if j.startswith("WAIT")]))
    for aid in spec.get("done", []):
        check(f"task {aid} 수행됨 (DONE)", (r.get(aid) or {}).get("status") == "DONE", str((r.get(aid) or {}).get("status")))
    for aid in spec.get("not_started", []):
        check(f"task {aid} 수행 안 됨", (r.get(aid) or {}).get("status") in ("TODO", "CANCELLED", None), str((r.get(aid) or {}).get("status")))
    if spec.get("class_input"):
        marked = [e["data"] for e in view["events"] if (e.get("data") or {}).get("class_input") == spec["class_input"]]
        check(f"처리 기록에 수업 입력 '{spec['class_input']}' (원인)", bool(marked), marked[0].get("cause", "") if marked else "")
    if name == "A-reject":
        check("거절: 설비 명령 0건 (사건 명령 id 없음 · 팬 지령 그대로)", not incident.get("cmdId") and plant_unit("HYD-01")["tags"]["FanSpeedSP"] == fan_before,
              f"cmdId {incident.get('cmdId')}, FanSpeedSP {plant_unit('HYD-01')['tags']['FanSpeedSP']} (전 {fan_before})")
        check("거절: 판단 원문 REJECTED · 승인 전달 기록 없음", get(f"/api/decisions/{decision_id}").get("state") == "REJECTED" and not view["approvals"])
    if name == "A-shortfall":
        unit = plant_unit("HYD-01")
        check("미달의 원인: 명령은 접수됐고(팬 지령 100) 팬 구동부 한계 때문에 유온이 기준 밖",
              bool(incident.get("cmdId")) and unit["disturbances"]["fan_limit"] < unit["tags"]["FanSpeedSP"] and unit["tags"]["TS1"] >= 55.0,
              f"FanSpeedSP {unit['tags']['FanSpeedSP']}, 팬 한계 {unit['disturbances']['fan_limit']}, TS1 {unit['tags']['TS1']}")
    if name.startswith("B"):
        tr = v.get("test_run") or {}
        check("시운전 값이 PM-2.9 기준과 비교됨", [x["limit"] for x in tr.get("readings", [])] == [178.0, 8.8, 1.2],
              ", ".join(f"{x['tag']} {x['value']} {x['op']} {x['limit']} {'통과' if x['ok'] else '미달'}" for x in tr.get("readings", [])))
        check("다음 정비 시점: " + ("갱신" if name == "B-normal" else "갱신 안 함"), bool(tr.get("counter")) is (name == "B-normal"),
              str((tr.get("counter") or {}).get("detail")))
    if name.startswith("C"):
        po = v.get("purchase_order") or {}
        mail = next((e["data"] for e in view["events"] if e.get("job_id") == "MCP_EFFECT_CALL" and e.get("event_type") == "tool_usage_started"), {})
        check("발주 번호가 메일 인자로 넘어감", bool(po.get("ref")) and po["ref"] in json.dumps(mail.get("input") or {}, ensure_ascii=False), str(mail.get("input"))[:300])
        if name == "C-normal":
            match = (v.get("goods_receipt") or {}).get("match") or {}
            check("입고 기록이 발주와 일치", match.get("ok") is True, match.get("text", ""))
        else:
            check("지연: 입고 기록 없음 · 입고 대기 task 는 기한 타이머가 멈춤", "goods_receipt" not in v and (r.get("T_gr") or {}).get("status") == "CANCELLED",
                  str((r.get("T_gr") or {}).get("status")))
    restore_and_wait_clear(spec)
    failed = [c for c in CHECKS if not c["ok"]]
    (out / f"{name}-checks.json").write_text(json.dumps({"ending": name, "instance": pid, "result_report": report, "checks": CHECKS, "log": LOG},
                                                        ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    log(f"{name}: 확인 {len(CHECKS) - len(failed)}/{len(CHECKS)} 통과 — {pid}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
