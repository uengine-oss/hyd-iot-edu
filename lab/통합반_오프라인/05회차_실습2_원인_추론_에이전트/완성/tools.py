"""도구. 실행할 때마다 파일을 읽어 물음에 맞는 것을 돌려주기만 하고, 판정하지 않는다."""
import json
from pathlib import Path

_폴더 = Path(__file__).resolve().parent
_그래프_경로 = _폴더 / "ontology" / "graph.json"
_입력_경로 = _폴더 / "input" / "sensor_input.json"


def _그래프():
    with open(_그래프_경로, encoding="utf-8") as f:
        그래프 = json.load(f)
    노드 = {n["props"]["id"]: n for n in 그래프["nodes"]}
    return 노드, 그래프["rels"]


def 원인_후보(패턴_코드: str):
    """경보 패턴의 코드를 받아, 그 패턴이 감지하는 증상, 증상이 가리키는 고장 유형, 그 고장 유형의 원인 후보를 돌려준다."""
    노드, 관계 = _그래프()
    패턴 = next(
        (n["props"] for n in 노드.values()
         if "AnomalyPattern" in n["labels"] and n["props"].get("code") == 패턴_코드),
        None,
    )
    if 패턴 is None:
        return {"패턴": None, "증상": [], "고장_유형": []}

    증상 = [r["b"] for r in 관계 if r["type"] == "DETECTS" and r["a"] == 패턴["id"]]
    고장_유형 = {}
    for 증상_id in 증상:
        for r in 관계:
            if r["type"] == "INDICATES" and r["a"] == 증상_id:
                고장_유형.setdefault(r["b"], []).append(증상_id)

    return {
        "패턴": {"id": 패턴["id"], "name": 패턴["name"], "code": 패턴["code"]},
        "증상": [{"id": s, "name": 노드[s]["props"]["name"]} for s in 증상],
        "고장_유형": [
            {
                "id": fm,
                "name": 노드[fm]["props"]["name"],
                "증상": 가리킨_증상,
                "원인": [
                    {
                        "id": r["a"],
                        "name": 노드[r["a"]]["props"]["name"],
                        "prior": 노드[r["a"]]["props"].get("prior"),
                        "section": 노드[r["a"]]["props"].get("section"),
                    }
                    for r in 관계 if r["type"] == "CAUSES" and r["b"] == fm
                ],
            }
            for fm, 가리킨_증상 in 고장_유형.items()
        ],
    }


def 증거_기준(원인_식별자: str):
    """원인의 식별자를 받아, 그 원인의 증거(태그 tag, 집계 방법 aggregate, 구간 windowSeconds, 비교 방향 expect, 기준값 threshold, 근거 절 section)를 돌려준다."""
    노드, 관계 = _그래프()
    칸 = ("id", "name", "tag", "aggregate", "windowSeconds", "expect", "threshold", "section")
    return {
        "원인": 원인_식별자,
        "증거": [
            {k: 노드[r["b"]]["props"].get(k) for k in 칸}
            for r in 관계 if r["type"] == "EVIDENCED_BY" and r["a"] == 원인_식별자
        ],
    }


def 센서_집계(사례: str, tag: str = None, aggregate: str = None, windowSeconds: int = None):
    """사례 번호와 태그, 집계 방법, 구간을 받아, 그 값(value)과 관측 충분성(coverage)을 돌려준다. 사례 번호만 주면 그 사례의 신선도(freshness)를 돌려준다."""
    with open(_입력_경로, encoding="utf-8") as f:
        한_건 = next((s for s in json.load(f) if s["번호"] == 사례), None) or {}
    if tag is None and aggregate is None and windowSeconds is None:
        return {"사례": 사례, "freshness": 한_건.get("freshness")}
    읽은_것 = next(
        (r for r in 한_건.get("readings", [])
         if r["tag"] == tag and r["aggregate"] == aggregate
         and r["windowSeconds"] == windowSeconds),
        {},
    )
    return {
        "사례": 사례, "tag": tag, "aggregate": aggregate, "windowSeconds": windowSeconds,
        "value": 읽은_것.get("value"), "coverage": 읽은_것.get("coverage"),
    }


def 조치_방법(고장_유형_식별자: str):
    """고장 유형의 식별자를 받아, 그 고장 유형의 조치 방법(절차 번호 sopId, 단계와 근거 절, 승인 역할, 맞는 원인)을 돌려준다."""
    노드, 관계 = _그래프()
    조치 = []
    for r in 관계:
        if r["type"] not in ("MITIGATED_BY", "REMEDIED_BY") or r["a"] != 고장_유형_식별자:
            continue
        스킬 = 노드[r["b"]]["props"]
        역할 = next(
            (노드[a["b"]]["props"] for a in 관계
             if a["type"] == "APPROVED_BY" and a["a"] == 스킬["id"]),
            None,
        )
        조치.append({
            "id": 스킬["id"],
            "sopId": 스킬.get("sopId"),
            "name": 스킬.get("name"),
            "kind": 스킬.get("kind"),
            "관계": r["type"],
            "steps": 스킬.get("steps", []),
            "승인_역할": 역할,
            "맞는_원인": [a["b"] for a in 관계
                      if a["type"] == "ADDRESSES" and a["a"] == 스킬["id"]],
        })
    return {"고장_유형": 고장_유형_식별자, "조치": 조치}
