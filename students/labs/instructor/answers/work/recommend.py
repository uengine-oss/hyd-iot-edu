"""조치 후보의 효과·비용·판정을 비교해 추천안을 만든다. 설비는 건드리지 않는다.

    python work/recommend.py --case day7/inputs/case_base.json --out work/day7/proposal_base.json
    python work/recommend.py --case day7/inputs/case_base.json --available-minutes 30 --out work/day7/proposal_whatif.json

순위 규칙: 결정표 판정이 제외인 조치와 작업 가능 시간 안에 못 끝내는 조치는 빼고, 남은 것을 순편익(효과 − 비용)이 큰 순서로 세운다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXCLUDED = "제외"
WARNING = "경고"


class ProposalError(ValueError):
    pass


def net_benefit(candidate: dict) -> int:
    return candidate["effect"]["benefit_manwon"] - candidate["cost"]["cost_manwon"]


def exclusion(candidate: dict, available_minutes: int) -> dict | None:
    judgement = candidate["judgement"]
    if judgement["result"] == EXCLUDED:
        return {"reason_type": "조건 제외", "detail": f"결정표 규칙 {judgement['applied_rule']} 에서 제외"}
    required = candidate["cost"]["required_minutes"]
    if required > available_minutes:
        return {"reason_type": "시간 부족", "detail": f"필요한 시간 {required}분이 작업 가능 시간 {available_minutes}분보다 길다"}
    return None


def ranked_item(candidate: dict) -> dict:
    judgement = candidate["judgement"]
    net = net_benefit(candidate)
    reason = f"순편익 {net}만원(효과 {candidate['effect']['benefit_manwon']} − 비용 {candidate['cost']['cost_manwon']})"
    if judgement["result"] == WARNING:
        reason += f", 결정표 규칙 {judgement['applied_rule']} 경고가 있어 주의가 필요하다"
    return {
        "action_id": candidate["action_id"],
        "name": candidate["name"],
        "net_benefit_manwon": net,
        "judgement": judgement["result"],
        "warning": judgement["result"] == WARNING,
        "reason": reason,
        "evidence": candidate["evidence"],
    }


def build_proposal(case: dict, available_minutes: int | None = None) -> dict:
    available = case["available_minutes"] if available_minutes is None else available_minutes
    if available is None:
        raise ProposalError("작업 가능 시간(available_minutes)이 비어 있어 추천안을 만들 수 없습니다.")
    if isinstance(available, bool) or not isinstance(available, int) or available < 0:
        raise ProposalError(f"작업 가능 시간은 0 이상의 정수(분)여야 합니다(받은 값 {available!r}).")
    ranking, excluded = [], []
    for candidate in case["candidates"]:
        why = exclusion(candidate, available)
        if why:
            excluded.append({"action_id": candidate["action_id"], "name": candidate["name"], **why})
        else:
            ranking.append(ranked_item(candidate))
    ranking.sort(key=lambda item: item["net_benefit_manwon"], reverse=True)
    for rank, item in enumerate(ranking, start=1):
        item["rank"] = rank
    return {
        "case_id": case["case_id"],
        "asset_id": case["asset_id"],
        "condition": case["condition"],
        "available_minutes": available,
        "ranking": ranking,
        "excluded": excluded,
        "recommended": ranking[0]["action_id"] if ranking else None,
        "control_executed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="조치 추천안 만들기")
    parser.add_argument("--case", required=True)
    parser.add_argument("--available-minutes", type=int, help="작업 가능 시간을 이 값으로 가정해 본다")
    parser.add_argument("--out", help="추천안을 저장할 파일")
    args = parser.parse_args()
    case = json.loads(Path(args.case).read_text(encoding="utf-8"))
    try:
        proposal = build_proposal(case, args.available_minutes)
    except ProposalError as error:
        print(f"추천안을 만들 수 없습니다: {error}", file=sys.stderr)
        raise SystemExit(2) from error
    text = json.dumps(proposal, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
