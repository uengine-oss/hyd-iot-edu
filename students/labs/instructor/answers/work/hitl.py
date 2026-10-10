"""모자란 운전 조건을 사람에게 묻고, 답을 받은 뒤 멈춘 판단을 이어 간다.

    python work/hitl.py start --case day7/inputs/case_no_window.json   # 모자라면 질문을 남기고 멈춘다
    python work/hitl.py resume --answer 30                             # 사람이 답하면 이어서 끝낸다

멈춘 동안의 상태는 work/day7/hitl_state.json 에 있다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from recommend import ProposalError, build_proposal

STATE_FILE = Path(__file__).resolve().parent / "day7" / "hitl_state.json"
WAITING = "질문 대기"
DONE = "완료"
QUESTION = "작업 가능 시간이 비어 있습니다. 장치를 멈추고 작업할 수 있는 시간은 몇 분입니까?"


def save(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def public(state: dict) -> dict:
    return {key: value for key, value in state.items() if key != "case"}


def start(case: dict) -> dict:
    if case["available_minutes"] is None:
        state = {"status": WAITING, "case_id": case["case_id"], "missing": ["available_minutes"],
                 "question": QUESTION, "answers": [], "proposal": None, "case": case}
    else:
        state = {"status": DONE, "case_id": case["case_id"], "missing": [], "question": None,
                 "answers": [], "proposal": build_proposal(case), "case": case}
    save(state)
    return public(state)


def resume(answer: str) -> dict:
    if not STATE_FILE.is_file():
        raise ProposalError("이어 갈 판단이 없습니다. 먼저 start 를 실행하세요.")
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    if state["status"] != WAITING:
        raise ProposalError(f"질문을 기다리는 판단이 아닙니다(지금 상태: {state['status']}).")
    if not answer.strip().isdigit():
        raise ProposalError(f"작업 가능 시간은 0 이상의 정수(분)로 답해 주세요(받은 답 {answer!r}).")
    minutes = int(answer)
    state["proposal"] = build_proposal(state["case"], minutes)
    state["answers"].append({"field": "available_minutes", "value": minutes, "by": "사람"})
    state.update(status=DONE, missing=[], question=None)
    save(state)
    return public(state)


def main() -> None:
    parser = argparse.ArgumentParser(description="사람에게 묻고 이어 가는 판단")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("start").add_argument("--case", required=True)
    commands.add_parser("resume").add_argument("--answer", required=True)
    args = parser.parse_args()
    try:
        if args.command == "start":
            result = start(json.loads(Path(args.case).read_text(encoding="utf-8")))
        else:
            result = resume(args.answer)
    except ProposalError as error:
        print(f"진행할 수 없습니다: {error}", file=sys.stderr)
        raise SystemExit(2) from error
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
