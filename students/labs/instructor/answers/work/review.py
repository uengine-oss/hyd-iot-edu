"""추천안을 검토한다. 근거 누락 · 조건 위반 · 이유 불일치를 찾아 표시한다.

    python work/review.py --case day7/inputs/case_base.json --proposal day7/inputs/proposal_ok.json

검토는 추천안에 적힌 말을 믿지 않고, 비교 자료(case)를 기준으로 다시 확인한다.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

MISSING_EVIDENCE = "근거 누락"
RULE_VIOLATION = "조건 위반"
REASON_MISMATCH = "이유 불일치"
EXCLUDED = "제외"
DOCUMENT = "문서"


def finding(kind: str, action_id: str | None, detail: str) -> dict:
    return {"type": kind, "action_id": action_id, "detail": detail}


def review_item(item: dict, candidate: dict | None, available_minutes: int) -> list[dict]:
    action_id = item["action_id"]
    if candidate is None:
        return [finding(RULE_VIOLATION, action_id, "비교 자료에 없는 조치가 순위에 있다")]
    found = []
    evidence = item.get("evidence") or []
    if not any(entry.get("kind") == DOCUMENT for entry in evidence):
        found.append(finding(MISSING_EVIDENCE, action_id, "문서 근거가 하나도 없다"))
    unknown = [entry for entry in evidence if entry not in candidate["evidence"]]
    if unknown:
        found.append(finding(MISSING_EVIDENCE, action_id, f"비교 자료에 없는 근거가 적혀 있다: {unknown}"))
    judgement = candidate["judgement"]
    if judgement["result"] == EXCLUDED:
        found.append(finding(RULE_VIOLATION, action_id, f"결정표 규칙 {judgement['applied_rule']} 에서 제외인 조치가 순위에 있다"))
    required = candidate["cost"]["required_minutes"]
    if required > available_minutes:
        found.append(finding(RULE_VIOLATION, action_id, f"필요한 시간 {required}분이 작업 가능 시간 {available_minutes}분보다 길다"))
    true_net = candidate["effect"]["benefit_manwon"] - candidate["cost"]["cost_manwon"]
    if item.get("net_benefit_manwon") != true_net:
        found.append(finding(REASON_MISMATCH, action_id, f"적힌 순편익 {item.get('net_benefit_manwon')} 이 비교표의 {true_net} 과 다르다"))
    if item.get("judgement") != judgement["result"]:
        found.append(finding(REASON_MISMATCH, action_id, f"적힌 판정 '{item.get('judgement')}' 이 결정표의 '{judgement['result']}' 과 다르다"))
    return found


def review(case: dict, proposal: dict) -> dict:
    candidates = {candidate["action_id"]: candidate for candidate in case["candidates"]}
    available = proposal["available_minutes"]
    ranking = proposal["ranking"]
    findings = []
    for item in ranking:
        findings.extend(review_item(item, candidates.get(item["action_id"]), available))
    known = [item for item in ranking if item["action_id"] in candidates]
    true_nets = [candidates[i["action_id"]]["effect"]["benefit_manwon"] - candidates[i["action_id"]]["cost"]["cost_manwon"] for i in known]
    if true_nets != sorted(true_nets, reverse=True):
        findings.append(finding(REASON_MISMATCH, None, "순위가 순편익이 큰 순서와 다르다"))
    first = ranking[0]["action_id"] if ranking else None
    if proposal.get("recommended") != first:
        findings.append(finding(REASON_MISMATCH, proposal.get("recommended"), f"추천한 조치가 1위({first})와 다르다"))
    if proposal.get("control_executed") is not False:
        findings.append(finding(RULE_VIOLATION, None, "추천 단계에서 설비 제어를 실행하면 안 된다"))
    return {"case_id": case["case_id"], "verdict": "반려" if findings else "통과", "findings": findings}


def main() -> None:
    parser = argparse.ArgumentParser(description="추천안 검토")
    parser.add_argument("--case", required=True)
    parser.add_argument("--proposal", required=True)
    args = parser.parse_args()
    case = json.loads(Path(args.case).read_text(encoding="utf-8"))
    proposal = json.loads(Path(args.proposal).read_text(encoding="utf-8"))
    print(json.dumps(review(case, proposal), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
