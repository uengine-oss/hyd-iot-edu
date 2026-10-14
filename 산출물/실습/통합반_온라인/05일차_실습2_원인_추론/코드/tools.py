"""도구. 부를 때마다 파일을 읽어 물음에 맞는 것을 돌려주기만 하고, 판정하지 않는다."""
import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_GRAPH = _HERE / "ontology" / "graph.json"
_CASES = _HERE / "cases" / "cases.json"


def _load_graph():
    with open(_GRAPH, encoding="utf-8") as f:
        graph = json.load(f)
    nodes = {n["props"]["id"]: n for n in graph["nodes"]}
    return nodes, graph["rels"]


def find_causes(alarm: str):
    """경보 패턴의 코드를 받아, 그 패턴이 감지하는 증상(symptoms), 증상이 가리키는 고장 유형(failures), 고장 유형마다의 원인 후보(causes)를 돌려준다."""
    nodes, rels = _load_graph()
    pattern = next(
        (n["props"] for n in nodes.values()
         if "AnomalyPattern" in n["labels"] and n["props"].get("code") == alarm),
        None,
    )
    if pattern is None:
        return {"alarm": None, "symptoms": [], "failures": []}

    symptoms = [r["b"] for r in rels if r["type"] == "DETECTS" and r["a"] == pattern["id"]]
    failures = {}
    for symptom in symptoms:
        for r in rels:
            if r["type"] == "INDICATES" and r["a"] == symptom:
                failures.setdefault(r["b"], []).append(symptom)

    return {
        "alarm": {"id": pattern["id"], "name": pattern["name"], "code": pattern["code"]},
        "symptoms": [{"id": s, "name": nodes[s]["props"]["name"]} for s in symptoms],
        "failures": [
            {
                "id": failure,
                "name": nodes[failure]["props"]["name"],
                "symptoms": seen,
                "causes": [
                    {
                        "id": r["a"],
                        "name": nodes[r["a"]]["props"]["name"],
                        "prior": nodes[r["a"]]["props"].get("prior"),
                        "section": nodes[r["a"]]["props"].get("section"),
                    }
                    for r in rels if r["type"] == "CAUSES" and r["b"] == failure
                ],
            }
            for failure, seen in failures.items()
        ],
    }


def get_evidence(cause_id: str):
    """원인의 id를 받아, 그 원인의 증거(evidence)를 돌려준다. 증거마다 태그 tag, 집계 방법 aggregate, 구간 windowSeconds, 비교 방향 expect, 기준값 threshold, 근거 절 section이 있다."""
    nodes, rels = _load_graph()
    fields = ("id", "name", "tag", "aggregate", "windowSeconds", "expect", "threshold", "section")
    return {
        "cause_id": cause_id,
        "evidence": [
            {k: nodes[r["b"]]["props"].get(k) for k in fields}
            for r in rels if r["type"] == "EVIDENCED_BY" and r["a"] == cause_id
        ],
    }


def read_sensor(case_id: str, tag: str = None, aggregate: str = None, windowSeconds: int = None):
    """사례 번호와 태그, 집계 방법, 구간을 받아, 그 값(value)과 관측 충분성(coverage)을 돌려준다. 사례 번호만 주면 그 사례의 신선도(freshness)를 돌려준다."""
    with open(_CASES, encoding="utf-8") as f:
        case = next((c for c in json.load(f) if c["id"] == case_id), None) or {}
    if tag is None and aggregate is None and windowSeconds is None:
        return {"case_id": case_id, "freshness": case.get("freshness")}
    reading = next(
        (r for r in case.get("readings", [])
         if r["tag"] == tag and r["aggregate"] == aggregate
         and r["windowSeconds"] == windowSeconds),
        {},
    )
    return {
        "case_id": case_id, "tag": tag, "aggregate": aggregate, "windowSeconds": windowSeconds,
        "value": reading.get("value"), "coverage": reading.get("coverage"),
    }


def get_actions(failure_id: str):
    """고장 유형의 id를 받아, 그 고장 유형의 조치 방법(actions)을 돌려준다. 조치마다 절차 번호 sopId, 단계 steps, 승인 역할 approver, 맞는 원인 for_causes가 있다."""
    nodes, rels = _load_graph()
    actions = []
    for r in rels:
        if r["type"] not in ("MITIGATED_BY", "REMEDIED_BY") or r["a"] != failure_id:
            continue
        skill = nodes[r["b"]]["props"]
        approver = next(
            (nodes[a["b"]]["props"] for a in rels
             if a["type"] == "APPROVED_BY" and a["a"] == skill["id"]),
            None,
        )
        actions.append({
            "id": skill["id"],
            "sopId": skill.get("sopId"),
            "name": skill.get("name"),
            "kind": skill.get("kind"),
            "relation": r["type"],
            "steps": skill.get("steps", []),
            "approver": approver,
            "for_causes": [a["b"] for a in rels
                           if a["type"] == "ADDRESSES" and a["a"] == skill["id"]],
        })
    return {"failure_id": failure_id, "actions": actions}
