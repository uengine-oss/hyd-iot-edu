"""검토에서 채택한 후보만 연습용 그래프에 등록한다. 관계마다 출처(문서·절·줄·원문·후보 번호)를 함께 적는다.

    python work/register_candidates.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from labkit.graph import graph_session
from labkit.settings import KIT_ROOT

CANDIDATES_FILE = KIT_ROOT / "day4" / "candidates" / "prepared_candidates.json"
MAPPING_FILE = KIT_ROOT / "day4" / "data" / "id_mapping.csv"
REVIEW_FILE = Path(__file__).with_name("review.json")
ADOPTED = "채택"
RELATION_ENDS = {
    "INDICATES": ("Symptom", "FailureMode"),
    "CAUSES": ("Cause", "FailureMode"),
    "REMEDIED_BY": ("FailureMode", "Action"),
}
LINK_ASSETS = """
UNWIND $asset_ids AS asset_id
MATCH (a:Asset {id: asset_id})
MATCH (f:FailureMode {id: $failure_id})
MERGE (a)-[r:CAN_HAVE]->(f)
SET r.doc = $doc
"""


def adopted_candidates() -> list[dict]:
    review = json.loads(REVIEW_FILE.read_text(encoding="utf-8"))
    candidates = json.loads(CANDIDATES_FILE.read_text(encoding="utf-8"))["candidates"]
    unreviewed = [c["id"] for c in candidates if c["id"] not in review]
    if unreviewed:
        raise SystemExit(f"검토하지 않은 후보가 있습니다: {unreviewed}. review.json 에 채택·보류를 먼저 적어 주세요.")
    return [c for c in candidates if review[c["id"]]["decision"] == ADOPTED]


def register_statement(candidate: dict) -> str:
    from_label, to_label = RELATION_ENDS[candidate["relation"]]
    if (candidate["from"]["label"], candidate["to"]["label"]) != (from_label, to_label):
        raise SystemExit(f"후보 {candidate['id']}: {candidate['relation']} 는 {from_label} → {to_label} 여야 합니다.")
    return f"""
    MERGE (x:{from_label} {{id: $from_id}}) SET x.name = $from_name, x += $from_props
    MERGE (y:{to_label} {{id: $to_id}}) SET y.name = $to_name, y += $to_props
    MERGE (x)-[r:{candidate['relation']} {{candidate_id: $candidate_id}}]->(y)
    SET r.doc = $doc, r.section = $section, r.line = $line, r.quote = $quote
    """


def mapped_asset_ids(doc: str) -> list[str]:
    with MAPPING_FILE.open(encoding="utf-8", newline="") as handle:
        return [row["asset_id"] for row in csv.DictReader(handle) if row["doc_id"] == doc]


def main() -> None:
    adopted = adopted_candidates()
    with graph_session() as session:
        for candidate in adopted:
            source = candidate["source"]
            session.run(
                register_statement(candidate),
                from_id=candidate["from"]["id"], from_name=candidate["from"]["name"], from_props=candidate["from"].get("props", {}),
                to_id=candidate["to"]["id"], to_name=candidate["to"]["name"], to_props=candidate["to"].get("props", {}),
                candidate_id=candidate["id"], doc=source["doc"], section=source["section"], line=source["line"], quote=source["quote"],
            ).consume()
        failures = {}
        for candidate in adopted:
            for end in (candidate["from"], candidate["to"]):
                if end["label"] == "FailureMode":
                    failures[end["id"]] = candidate["source"]["doc"]
        for failure_id, doc in failures.items():
            session.run(LINK_ASSETS, asset_ids=mapped_asset_ids(doc), failure_id=failure_id, doc=doc).consume()
    print(f"채택한 후보 {len(adopted)}개를 등록했습니다: {[c['id'] for c in adopted]}")


if __name__ == "__main__":
    main()
