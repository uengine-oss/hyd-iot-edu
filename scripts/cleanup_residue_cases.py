"""A155 — residue cleanup: precedent DecisionCases that verification runs left in the knowledge graph.

    .venv/bin/python scripts/cleanup_residue_cases.py --before 2026-10-08T12:00Z --out <dir> [--apply]            (Linux)
    . scripts/host_libpq.sh; .venv314/Scripts/python scripts/cleanup_residue_cases.py --before <ISO> --out <dir> [--apply]

Why: the precedent template (it/neo4j/templates/t3_precedents.cypher) counts every DecisionCase -CHOSE-> Skill of the same
failure mode and shows up to five reasons under 근거 보기 "과거 같은 선택". Probe scripts submit decisions through the same API a
person uses, so their reasons ("A072 probe: …", "A148-50: 포털 클릭으로 …") were projected as precedents (A151 capture ①) and their
counts entered the ranking feature precedent_share. The graph cannot tell a probe's decision from a person's, so — same rule as
cleanup_residue_instances.py (decision 99) — everything decided before --before (the moment real use starts) is residue.

Only projected cases are candidates: a DecisionCase with source_incident_id (written by procsvc/case_projection.py). Seeded
demo precedents (case:demo-*, no source_incident_id) are part of the ontology and are never touched.
Without --apply it lists and writes backup.json (properties + outgoing relationships). With --apply it DETACH DELETEs the
listed DecisionCase nodes only (Incident projections and process records stay; the precedent query no longer reaches them).
"""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from neo4j import GraphDatabase

NEO4J = (os.environ.get('NEO4J_URI', 'bolt://127.0.0.1:7687'), ('neo4j', os.environ.get('NEO4J_PASSWORD', 'hydpass123')))
LIST_Q = '''
MATCH (dc:DecisionCase) WHERE dc.source_incident_id IS NOT NULL AND dc.decidedAt < datetime($before)
OPTIONAL MATCH (dc)-[r]->(x)
RETURN dc.id AS id, properties(dc) AS props, collect({type:type(r), to:x.id}) AS rels ORDER BY dc.id
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--before', required=True, help='ISO instant; projected cases decided before this are residue')
    ap.add_argument('--out', required=True)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    datetime.fromisoformat(args.before.replace('Z', '+00:00'))   # fail loudly on a malformed boundary
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with GraphDatabase.driver(NEO4J[0], auth=NEO4J[1], connection_timeout=5) as driver, driver.session() as s:
        rows = [r.data() for r in s.run(LIST_Q, before=args.before)]
        (out / 'backup.json').write_text(json.dumps(dict(before=args.before, cases=rows), ensure_ascii=False, indent=2,
                                                    default=str), encoding='utf-8')
        deleted = 0
        if args.apply and rows:
            deleted = s.run('MATCH (dc:DecisionCase) WHERE dc.id IN $ids DETACH DELETE dc RETURN count(*) AS n',
                            ids=[r['id'] for r in rows]).single()['n']
        left = s.run('MATCH (dc:DecisionCase) RETURN count(dc) AS n, '
                     'count(CASE WHEN dc.source_incident_id IS NULL THEN 1 END) AS seeded').single().data()
    report = dict(before=args.before, residue=len(rows), applied=bool(args.apply), deleted=deleted, remaining=left,
                  reasons=[(r['props'].get('reason') or '')[:80] for r in rows])
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
