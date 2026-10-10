"""7일차 확인: 조치 비교와 추천(7-1) · 추천안 검토(7-2) · 사람에게 묻고 이어 가기(7-3)."""
from __future__ import annotations

import json

from labcheck.core import Report, need_file, read_json, run_json, run_script, work_path
from labcheck.facts import read_kit_json
from labkit.settings import KIT_ROOT

BASE_CASE = "day7/inputs/case_base.json"
HIGHLOAD_CASE = "labcheck/fixtures/day7/case_highload.json"
NO_WINDOW_CASE = "day7/inputs/case_no_window.json"
FINDING_TYPES = {"근거 누락", "조건 위반", "이유 불일치"}
WAITING = "질문 대기"
DONE = "완료"
STATE_FILE = "day7/hitl_state.json"


def expected() -> dict:
    return read_kit_json("labcheck/expected/day7.json")


def kit(relative: str) -> str:
    return str(KIT_ROOT / relative)


def order(proposal: dict) -> list[str]:
    return [item.get("action_id") for item in proposal.get("ranking", [])]


def check_proposal(report: Report, name: str, proposal: dict, wanted: dict) -> None:
    report.equal(f"{name}: 순위가 맞다", order(proposal), wanted["ranking"])
    report.equal(f"{name}: 추천 대상에서 뺀 조치가 맞다", sorted(item.get("action_id") for item in proposal.get("excluded", [])), sorted(wanted["excluded"]))
    report.equal(f"{name}: 추천(recommended)이 1위와 같다", proposal.get("recommended"), wanted["ranking"][0])
    report.check(f"{name}: 실제 제어는 하지 않았다(control_executed 가 false)", proposal.get("control_executed") is False, f"나온 값 {proposal.get('control_executed')!r}")


def lab7_1(report: Report) -> None:
    program = work_path("recommend.py")
    need_file(report, program, "추천 프로그램")
    wanted = expected()
    case = read_kit_json(BASE_CASE)
    evidence = {candidate["action_id"]: candidate["evidence"] for candidate in case["candidates"]}
    for what_if in wanted["what_if"]:
        minutes = what_if["available_minutes"]
        proposal = run_json(report, program, "--case", kit(BASE_CASE), "--available-minutes", str(minutes))
        check_proposal(report, f"작업 가능 시간 {minutes}분", proposal, what_if)
    base = run_json(report, program, "--case", kit(BASE_CASE))
    nets = {item.get("action_id"): item.get("net_benefit_manwon") for item in base.get("ranking", [])}
    report.equal("순위마다 순편익(효과 − 비용)이 비교표와 같다", nets, wanted["net_benefit_manwon"])
    report.check("순위마다 이유(reason)와 비교 자료의 근거(evidence)가 있다",
                 all(item.get("reason") and item.get("evidence") == evidence.get(item.get("action_id")) for item in base.get("ranking", [])),
                 "reason 이 비었거나 evidence 가 비교 자료와 다릅니다.")
    warned = {item.get("action_id") for item in base.get("ranking", []) if item.get("warning")}
    report.equal("결정표에서 경고인 조치에 경고 표시가 있다", warned,
                 {candidate["action_id"] for candidate in case["candidates"] if candidate["judgement"]["result"] == "경고"})
    report.check("빠진 조치마다 왜 뺐는지 적혀 있다",
                 all(item.get("detail") for item in run_json(report, program, "--case", kit(BASE_CASE), "--available-minutes", "30").get("excluded", [])),
                 "excluded 의 detail 이 비었습니다.")
    check_proposal(report, "결정표에서 제외인 조치가 있는 경우", run_json(report, program, "--case", kit(HIGHLOAD_CASE)), wanted["highload"])
    for name in ("proposal_base.json", "proposal_whatif.json"):
        need_file(report, work_path(f"day7/{name}"), "저장한 추천안")
    saved_base = read_json(report, work_path("day7/proposal_base.json"), "기본 추천안")
    saved_whatif = read_json(report, work_path("day7/proposal_whatif.json"), "조건을 바꾼 추천안")
    report.check("조건 하나를 바꾼 추천안은 작업 가능 시간만 다르고 순위가 달라졌다",
                 saved_base.get("condition") == saved_whatif.get("condition")
                 and saved_base.get("available_minutes") != saved_whatif.get("available_minutes") and order(saved_base) != order(saved_whatif),
                 f"기본 {saved_base.get('available_minutes')}분 {order(saved_base)} / 바꾼 것 {saved_whatif.get('available_minutes')}분 {order(saved_whatif)}")


def lab7_2(report: Report) -> None:
    program = work_path("review.py")
    need_file(report, program, "검토 프로그램")
    for review in expected()["reviews"]:
        result = run_json(report, program, "--case", kit(review["case"]), "--proposal", kit(review["proposal"]))
        found = [finding.get("type") for finding in result.get("findings", [])]
        report.equal(f"{review['name']}: 판정이 '{review['verdict']}' 이다", result.get("verdict"), review["verdict"])
        report.equal(f"{review['name']}: 지적한 종류가 맞다", sorted(set(found)), sorted(review["types"]))
        report.check(f"{review['name']}: 지적마다 종류와 설명이 있다",
                     all(finding.get("type") in FINDING_TYPES and finding.get("detail") for finding in result.get("findings", [])), f"나온 지적 {result.get('findings')}")
    for name in ("review_ok.json", "review_missing_evidence.json"):
        need_file(report, work_path(f"day7/{name}"), "저장한 검토 결과")


def state() -> dict:
    """멈춘 판단이 저장된 파일. 아직 없으면 빈 사전."""
    path = work_path(STATE_FILE)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def lab7_3(report: Report) -> None:
    program = work_path("hitl.py")
    need_file(report, program, "묻고 이어 가는 프로그램")
    wanted = expected()
    for resume in wanted["resume"]:
        waiting = run_json(report, program, "start", "--case", kit(NO_WINDOW_CASE))
        report.check("작업 가능 시간이 비면 추천하지 않고 멈춘다(질문 대기)",
                     waiting.get("status") == WAITING and not waiting.get("proposal"), f"status={waiting.get('status')!r}, proposal={waiting.get('proposal')!r}")
        report.check("무엇이 없는지와 사람에게 할 질문이 있다",
                     waiting.get("missing") == ["available_minutes"] and "시간" in str(waiting.get("question", "")), f"missing={waiting.get('missing')!r}, question={waiting.get('question')!r}")
        report.check("멈춘 상태가 파일에 남는다", state().get("status") == WAITING, f"work/{STATE_FILE} 의 status: {state().get('status')!r}")
        bad = run_script(program, "resume", "--answer", "모름")
        report.check("숫자가 아닌 답은 받지 않고 계속 기다린다", bad.returncode != 0 and state().get("status") == WAITING,
                     f"종료 코드 {bad.returncode}, 상태 {state().get('status')!r}")
        finished = run_json(report, program, "resume", "--answer", resume["answer"])
        proposal = finished.get("proposal") or {}
        report.check(f"사람이 {resume['answer']}분이라고 답하면 멈춘 판단을 이어서 끝낸다",
                     finished.get("status") == DONE and proposal.get("recommended") == resume["recommended"]
                     and proposal.get("available_minutes") == int(resume["answer"]),
                     f"status={finished.get('status')!r}, 추천={proposal.get('recommended')!r}")
        answers = finished.get("answers") or []
        report.check("사람이 준 답이 기록에 남는다", bool(answers) and answers[-1].get("value") == int(resume["answer"]), f"answers={answers}")
    again = run_script(program, "resume", "--answer", "30")
    report.check("기다리는 질문이 없을 때 이어 가라고 하면 오류로 알린다", again.returncode != 0, "끝난 판단을 다시 이어 갔습니다.")
    complete = run_json(report, program, "start", "--case", kit(BASE_CASE))
    report.check("모자란 정보가 없으면 묻지 않고 바로 끝낸다",
                 complete.get("status") == DONE and (complete.get("proposal") or {}).get("recommended") == wanted["what_if"][0]["ranking"][0],
                 f"status={complete.get('status')!r}")


LABS = {
    "7-1": ("조치별 예상 효과와 근거를 정리해 추천하기", lab7_1),
    "7-2": ("검토 에이전트가 근거와 조건을 확인하게 만들기", lab7_2),
    "7-3": ("필요한 운전 조건을 사람에게 묻고 판단 이어 가기", lab7_3),
}
