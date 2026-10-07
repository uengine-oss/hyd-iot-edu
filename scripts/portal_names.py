"""A141 — 포털 화면의 원문 id(fm:… · cause:… · rule:… · skill:… 등) → 이름 사전을 Neo4j 실제 노드에서 만든다.

    PYTHONUTF8=1 .venv314/Scripts/python.exe scripts/portal_names.py            # → it/portal/www/names.json
    PYTHONUTF8=1 .venv314/Scripts/python.exe scripts/portal_names.py --check    # 쓰지 않고 개수만

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

ROOT = Path(__file__).resolve().parents[1]
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
            names[row["id"]] = row["name"]
            kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
    if not names:
        print("names: 0 — Neo4j에 id/name 노드가 없다. 생성하지 않음", file=sys.stderr)
        return 1
    # 업무 스킬(skill:schedule-maintenance 등)은 v2 그래프에 없고 enterprise-sim 코드가 정본이다(A150)
    sys.path.insert(0, str(ROOT / "it" / "enterprise-sim"))
    from entsim.state import SKILL_NAMES  # noqa: E402
    for sid, label in SKILL_NAMES.items():
        names.setdefault(sid, label)
    kinds["BusinessSkill"] = len(SKILL_NAMES)
    print(f"names: {len(names)} · " + " · ".join(f"{k} {v}" for k, v in sorted(kinds.items(), key=lambda x: -x[1])))
    if a.check:
        return 0
    Path(a.out).write_text(json.dumps(names, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {a.out} ({Path(a.out).stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
