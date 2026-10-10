"""승인 단계(승인 · 거절 · 무응답)를 라이브 스택에서 한 번에 하나씩 끝까지 돌리고 확인한다(실제 워커 필요).

  .venv/bin/python scripts/approval_stage_live.py CASE OUTDIR
  CASE: {A|B|C}-approve | {A|B|C}-reject | {A|B|C}-wait   (wait = 승인하지 않고 두어 지연 알림이 나가고도 기다리는지 본 뒤 거절로 닫는다)

앞서 할 일(docs/handoff/NOW.md 2절 '버튼 완주 순서'): 잠금 → 그래프 구조판 → `scripts/c3_flows.py deploy` → 워커 1개.
포털 버튼이 부르는 것과 같은 process API 만 쓴다: 시작 POST /api/scenario/A/degrade · /api/scenario/{B|C}/start, 승인 POST /api/todolist/{id}/select
(에이전트 추천 카드), 거절 POST /api/todolist/{id}/reject-card, 정리 POST /api/scenario/A/restore · /api/scenario/{B|C}/reset.
확인은 처리 건의 끝 이벤트 · 결과 보고 · 사건 상태 · 처리 기록 · 업무 표시를 읽어서 하고, OUTDIR 에 처리 건 원문과 확인 표를 남긴다.
확인이 하나라도 틀리면 종료 1. 에이전트 task 가 실패(워커 한도 등)로 멈추면 사유를 적고 종료 2 — 끝난 척하지 않는다.
A 를 승인으로 끝낸 뒤에는 팬 지령이 100 % 로 남아 다음 열화 주입이 경보를 내지 못한다(설비 `/api/reset` 필요) — A 승인은 A 의 마지막에 돌린다."""
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
AGENT_WAIT_S, END_WAIT_S, NOTICE_WAIT_S, POLL_S = 900, 600, 120, 3
STAY_AFTER_NOTICE_S = 20      # 지연 알림 뒤에도 승인 대기인지 다시 보기까지 두는 시간
CLEAR_TS1 = 50.0              # [쿨러 복구] 뒤 유온이 이 아래(경보 해제선 52 ℃ 아래)로 올 때까지 기다린다

SCENARIOS = {
    "A": {"flow": "c3_cooling", "asset": "HYD-01", "start": "/api/scenario/A/degrade", "me": ("user:kim-op", "role:operator"),
          "outcome": "정상", "incident": "CLOSED", "effects": ["T_cmd", "T_reobs", "T_wo"], "after": "/api/scenario/A/restore"},
    "B": {"flow": "c3_pm", "asset": "HYD-02", "start": "/api/scenario/B/start", "me": ("user:park-maint", "role:maint-mgr"),
          "outcome": "정상", "incident": "CLOSED", "effects": ["T_wo"], "after": "/api/scenario/B/reset"},
    "C": {"flow": "c3_spare", "asset": "HYD-03", "start": "/api/scenario/C/start", "me": ("user:jung-buy", "role:purchasing"),
          "outcome": "입고 완료", "incident": "CLOSED", "effects": ["T_po", "T_gr"], "after": "/api/scenario/C/reset"},
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
    return {v["key"]: v.get("value") for v in view["instance"].get("variables_data") or []}


def rows(view: dict) -> dict:
    """활동마다 가장 최근 행."""
    out: dict = {}
    for w in sorted(view["workitems"], key=lambda w: str(w.get("start_date") or "")):
        out[w["activity_id"]] = w
    return out


def flag(key: str):
    """B · C 의 업무 표시(정기 점검 도래 · 재고 보충 필요). A 는 None."""
    return get("/api/scenario/status")["scenarios"][key]["alert"] if key in ("B", "C") else None


def wait_instance(flow: str, known: set) -> str:
    t0 = time.time()
    while time.time() - t0 < 600:
        new = [i for i in get("/api/instances?limit=100") if i["proc_inst_id"] not in known and i.get("proc_def_id") == flow]
        if new:
            return new[0]["proc_inst_id"]
        time.sleep(POLL_S)
    raise SystemExit(f"600초 안에 {flow} 처리 건이 열리지 않았습니다 — 흐름 배포 · 감지기 · 설비 상태(팬 지령이 100 % 로 남았는지)를 확인하세요")


def wait_approval(pid: str) -> dict:
    """에이전트 판단이 끝나 승인 task 가 열릴 때까지. 에이전트 task 가 실패로 멈추면 사유와 함께 종료 2."""
    t0 = time.time()
    while time.time() - t0 < AGENT_WAIT_S:
        view = get(f"/api/instances/{pid}")
        r = rows(view)
        agent, approve = r.get("T_agent") or {}, r.get("T_approve") or {}
        if agent.get("status") == "DONE" and approve.get("status") == "IN_PROGRESS":
            log(f"승인 대기 — 에이전트 {time.time() - t0:.0f}초")
            return view
        if agent.get("status") == "PENDING" or view["instance"]["status"] != "RUNNING":
            print(f"미완: 에이전트 task 가 {agent.get('status')} 로 멈췄습니다\n{agent.get('log')}", file=sys.stderr)
            raise SystemExit(2)
        time.sleep(POLL_S)
    print(f"미완: {AGENT_WAIT_S}초 안에 승인 task 가 열리지 않았습니다(워커가 도는지 확인)", file=sys.stderr)
    raise SystemExit(2)


def wait_notice(pid: str) -> dict:
    """승인하지 않고 둔다: 지연 알림이 나갈 때까지 기다린 뒤, 조금 더 두고 처리 건을 돌려준다."""
    t0 = time.time()
    while time.time() - t0 < NOTICE_WAIT_S:
        if (rows(get(f"/api/instances/{pid}")).get("T_notice") or {}).get("status") == "DONE":
            log(f"승인 지연 알림 나감 — 승인 대기 {time.time() - t0:.0f}초 뒤")
            time.sleep(STAY_AFTER_NOTICE_S)
            return get(f"/api/instances/{pid}")
        time.sleep(POLL_S)
    raise SystemExit(f"{NOTICE_WAIT_S}초 안에 승인 지연 알림이 나가지 않았습니다")


def wait_end(pid: str) -> dict:
    t0 = time.time()
    while time.time() - t0 < END_WAIT_S:
        view = get(f"/api/instances/{pid}")
        if view["instance"]["status"] != "RUNNING":
            log(f"처리 건 종료 {view['instance']['status']} — {time.time() - t0:.0f}초")
            return view
        stuck = [w for w in view["workitems"] if w["status"] == "PENDING"]
        if stuck:
            raise SystemExit(f"task {stuck[0]['activity_id']} 가 PENDING 으로 멈췄습니다: {stuck[0].get('log')}")
        time.sleep(POLL_S)
    raise SystemExit(f"{END_WAIT_S}초 안에 처리 건이 끝나지 않았습니다: 현재 {view['instance'].get('current_activity_ids')}")


def plant_unit(asset: str) -> dict:
    return call("GET", PLANT + "/api/state")["units"][asset]


def clean_up(key: str, spec: dict) -> None:
    res = post(spec["after"], {"by": "강사 (수업 정리)"})
    log(f"정리 {spec['after']}: {json.dumps({k: res.get(k) for k in ('button', 'instance', 'reanchored')}, ensure_ascii=False)}")
    if key != "A":
        return
    t0 = time.time()
    while time.time() - t0 < 600:
        unit = plant_unit("HYD-01")
        if unit["tags"]["TS1"] < CLEAR_TS1 and unit["disturbances"]["cooler_health"] == 1.0:
            log(f"HYD-01 유온 {unit['tags']['TS1']} ℃ — 정상으로 돌아옴 ({time.time() - t0:.0f}초)")
            return
        time.sleep(5)
    raise SystemExit("HYD-01 이 600초 안에 정상으로 돌아오지 않았습니다")


def main(argv: list[str]) -> int:
    key, _, mode = (argv[1] if len(argv) == 3 else "").partition("-")
    if key not in SCENARIOS or mode not in ("approve", "reject", "wait"):
        print(__doc__, file=sys.stderr)
        return 2
    name, out, spec = argv[1], Path(argv[2]), SCENARIOS[key]
    out.mkdir(parents=True, exist_ok=True)
    me, role = spec["me"]
    known = {i["proc_inst_id"] for i in get("/api/instances?limit=100")}
    fan_before = plant_unit(spec["asset"])["tags"]["FanSpeedSP"]
    started = post(spec["start"], {"by": "강사", "user_id": me, "roles": [role]})
    pid = started.get("instance") or wait_instance(spec["flow"], known)
    log(f"시작 {spec['start']} → 처리 건 {pid}")
    view = wait_approval(pid)
    decision_id = values(view)["decision_id"]
    decision = get(f"/api/decisions/{decision_id}")
    wid = rows(view)["T_approve"]["id"]
    (out / f"{name}-at-approval.json").write_text(json.dumps({"view": view, "decision": decision}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    check("승인 전 설비 명령 · 업무 처리 없음", not get(f"/api/incidents/{values(view)['incident']}").get("cmdId")
          and all(w["status"] == "TODO" for w in view["workitems"] if w["activity_id"] in spec["effects"]))
    if mode == "wait":
        view = wait_notice(pid)
        r, v = rows(view), values(view)
        notice = (r["T_notice"].get("output") or {}).get("result_report") or {}
        check("지연 알림만 나감 (결과 '승인 지연', 사건은 그대로)", notice.get("outcome") == "승인 지연" and notice.get("incident_closed") is False,
              f"{notice.get('title')}: {notice.get('summary')}")
        check("알림 뒤에도 승인 단계에서 기다림 (자동 취소 · 자동 거절 없음)",
              view["instance"]["status"] == "RUNNING" and r["T_approve"]["status"] == "IN_PROGRESS" and "approval" not in v
              and get(f"/api/incidents/{v['incident']}").get("state") == "AWAITING_APPROVAL",
              f"처리 건 {view['instance']['status']}, 승인 task {r['T_approve']['status']}")
        check("기다리는 동안 처리 0건", all(w["status"] == "TODO" for w in view["workitems"] if w["activity_id"] in spec["effects"]))
        (out / f"{name}-while-waiting.json").write_text(json.dumps(view, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    if mode == "approve":
        res = post(f"/api/todolist/{wid}/select", {"decision": decision_id, "option": decision["recommended"], "by": me, "role": role,
                                                   "reason": "수업: 추천안 승인"})
        log(f"승인 접수: {decision['recommended']} ({res.get('approval_status')})")
    else:
        reason = "이번에는 진행하지 않습니다 (수업: 승인 거절)"
        res = post(f"/api/todolist/{wid}/reject-card", {"decision": decision_id, "by": me, "role": role, "reason": reason})
        log(f"거절 접수: {res.get('approval')}")
    view = wait_end(pid)
    v, r = values(view), rows(view)
    jobs = [e.get("job_id") for e in view["events"]]
    incident = get(f"/api/incidents/{v['incident']}")
    report = v.get("result_report") or {}
    (out / f"{name}-final.json").write_text(json.dumps({"view": view, "incident": incident, "decision": get(f"/api/decisions/{decision_id}"),
                                                        "plant": plant_unit(spec["asset"]), "scenario_status": get("/api/scenario/status")},
                                                       ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    check("처리 건이 끝났다 (COMPLETED)", view["instance"]["status"] == "COMPLETED", view["instance"]["status"])
    if mode == "approve":
        check("끝 이벤트 E_end", view["instance"].get("end_event") == "E_end", str(view["instance"].get("end_event")))
        check(f"결과 보고 '{spec['outcome']}'", report.get("outcome") == spec["outcome"], f"{report.get('outcome')} — {report.get('title')}: {report.get('summary')}")
        check(f"사건 상태 {spec['incident']}", incident.get("state") == spec["incident"], str(incident.get("state")))
        check("처리 기록에 승인 접수, 거절 없음", "APPROVAL_ACCEPTED" in jobs and "APPROVAL_REJECTED" not in jobs)
        for aid in spec["effects"]:
            check(f"task {aid} 수행됨 (DONE)", (r.get(aid) or {}).get("status") == "DONE", str((r.get(aid) or {}).get("status")))
        if key == "A":
            check("A: 조치 뒤 유온 재확인으로 종결 (명령 id 있음 · 회복)", bool(incident.get("cmdId")) and v.get("recovered") is True,
                  f"cmdId {incident.get('cmdId')}, recovered {v.get('recovered')}")
        else:
            check("업무 표시가 꺼졌다 (처리됨)", flag(key) is False, str(flag(key)))
    else:
        check("끝 이벤트 E_rejected", view["instance"].get("end_event") == "E_rejected", str(view["instance"].get("end_event")))
        check("결과 보고 '반려'", report.get("outcome") == "반려", f"{report.get('title')}: {report.get('summary')}")
        check("사건 상태 REJECTED_BY_OPERATOR (열린 채 남지 않음)", incident.get("state") == "REJECTED_BY_OPERATOR", str(incident.get("state")))
        check("처리 기록에 거절 접수, 승인 없음", "APPROVAL_REJECTED" in jobs and "APPROVAL_ACCEPTED" not in jobs)
        for aid in spec["effects"]:
            check(f"task {aid} 수행 안 됨", (r.get(aid) or {}).get("status") in ("TODO", "CANCELLED", None), str((r.get(aid) or {}).get("status")))
        check("설비 명령 0건 (사건 명령 id 없음 · 팬 지령 그대로) · 승인 전달 기록 없음",
              not incident.get("cmdId") and plant_unit(spec["asset"])["tags"]["FanSpeedSP"] == fan_before and not view["approvals"],
              f"cmdId {incident.get('cmdId')}, FanSpeedSP {plant_unit(spec['asset'])['tags']['FanSpeedSP']} (전 {fan_before})")
        check("판단 원문 REJECTED", get(f"/api/decisions/{decision_id}").get("state") == "REJECTED")
        if key != "A":
            check("업무 표시가 켜진 채다 (처리되지 않음)", flag(key) is True, str(flag(key)))
    clean_up(key, spec)
    failed = [c for c in CHECKS if not c["ok"]]
    (out / f"{name}-checks.json").write_text(json.dumps({"case": name, "instance": pid, "result_report": report, "checks": CHECKS, "log": LOG},
                                                        ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    log(f"{name}: 확인 {len(CHECKS) - len(failed)}/{len(CHECKS)} 통과 — {pid}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
