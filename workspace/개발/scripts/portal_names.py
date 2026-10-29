"""A141 — 포털 화면의 원문 id(fm:… · cause:… · rule:… · skill:… 등) → 이름 사전을 Neo4j 실제 노드에서 만든다.

    PYTHONUTF8=1 .venv314/Scripts/python.exe workspace/개발/scripts/portal_names.py            # → it/portal/www/names.json
    PYTHONUTF8=1 .venv314/Scripts/python.exe workspace/개발/scripts/portal_names.py --check    # 쓰지 않고 개수만

규칙: `id`와 `name`이 모두 있는 노드만 담는다. Rule 노드는 `name`이 없고 `annotation`(규칙 설명)만 있으므로 그것을 쓴다.
그 밖의 이름 없는 노드(WorkItem · Incident · Step …)는 넣지 않는다 — 화면이 지어낸 번역을 보이면 안 되기 때문이다.
포털(ui.js UI.loadNames)은 names.json을 읽어 응답에 이름이 없을 때만 이 사전으로 바꾼다. 접속: bolt://127.0.0.1:7687 (compose neo4j).
"""
import argparse
import json
import os
import sys
from pathlib import Path

from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "it" / "portal" / "www" / "names.json"
# 프로세스 실행 기록(FlowNode · ProcessInstance · ProcessVersion · IngestionBatch · IngestionControl)은 화면에 id 로 나오지 않으므로 뺀다
SKIP_LABELS = ["FlowNode", "ProcessInstance", "ProcessVersion", "IngestionBatch", "IngestionControl"]
QUERY = """
MATCH (n) WHERE n.id IS NOT NULL AND none(l IN labels(n) WHERE l IN $skip)
WITH n, CASE WHEN n.name IS NOT NULL AND n.name <> '' THEN n.name
             WHEN 'Rule' IN labels(n) AND n.annotation IS NOT NULL THEN n.annotation END AS label
WHERE label IS NOT NULL AND n.id <> label
RETURN n.id AS id, label AS name, labels(n)[0] AS kind
ORDER BY id
"""


def display_name(label):
    """UIUX의 화면 명칭 정책만 투영한다. DB·업무 원문은 수정하지 않는다.

    이름 없는 값과 알 수 없는 이름은 그대로 둔다. 이 함수는 생성 사전의
    name/Rule annotation 및 공식 스킬 이름에만 적용하며 자유문에는 쓰지 않는다.
    """
    if not isinstance(label, str):
        return label
    label = label.replace("정비 작업지시", "정비 오더").replace("작업지시", "정비 오더")
    known = {
        "CMMS": "정비 관리", "ERP": "구매 · 재고 관리", "MES": "생산 관리",
        "SCM 구매 포털": "공급망 구매 창구", "Historian (TimescaleDB)": "센서 기록",
        "SCADA · PLC (cmd-gateway 경유)": "설비 제어",
        "PLC 운전 모드": "설비 운전 모드", "PLC 상태": "설비 상태",
        "경남유압 BSC 전략맵": "경남유압 성과 목표",
        "HITL 프로세스 서비스": "업무 처리", "QMS 품질 시스템": "품질 관리",
        "CEP 탐지기 (Flink 대체)": "센서 경보 감지기",
    }
    if label in known:
        return known[label]
    # Rule annotations are generated display labels, never stored original evidence.
    return label.replace("PLC가", "설비 제어기가").replace("BSC 득실", "성과 득실").replace("강도 high 1 · medium 0.6 · low 0.3", "강도 높음 1 · 중간 0.6 · 낮음 0.3")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uri", default=os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687"))
    ap.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"))
    ap.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD", "hydpass123"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--check", action="store_true", help="파일을 쓰지 않고 개수만 보고")
    a = ap.parse_args()
    names, kinds = {}, {}
    with GraphDatabase.driver(a.uri, auth=(a.user, a.password)) as driver, driver.session() as s:
        for row in s.run(QUERY, skip=SKIP_LABELS):
            names[row["id"]] = display_name(row["name"])
            kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
    if not names:
        print("names: 0 — Neo4j에 id/name 노드가 없다. 생성하지 않음", file=sys.stderr)
        return 1
    # 업무 스킬(skill:schedule-maintenance 등)은 v2 그래프에 없고 enterprise-sim 코드가 정본이다(A150)
    sys.path.insert(0, str(ROOT / "it" / "enterprise-sim"))
    from entsim.state import SKILL_NAMES  # noqa: E402
    for sid, label in SKILL_NAMES.items():
        names.setdefault(sid, display_name(label))
    kinds["BusinessSkill"] = len(SKILL_NAMES)
    print(f"names: {len(names)} · " + " · ".join(f"{k} {v}" for k, v in sorted(kinds.items(), key=lambda x: -x[1])))
    if a.check:
        return 0
    Path(a.out).write_text(json.dumps(names, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {a.out} ({Path(a.out).stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
