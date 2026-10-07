"""A115 — residue cleanup: RUNNING process instances that interrupted test runs left behind (decision 99, same method as A101).

    . scripts/host_libpq.sh; .venv314/Scripts/python scripts/cleanup_residue_instances.py --before 2026-10-07T12:20Z --out <dir> [--apply]

Without --apply it only lists and backs up. With --apply, in this order:
  1. backup.json — the bpm_proc_inst rows, their todolist rows, and the graph projection (ProcessInstance + its WorkItems).
  2. PG: bpm_proc_inst.is_deleted = true (rows kept); open todolist rows of those instances → CANCELLED with a log note, so
     they leave "내 할일" (the engine's claim already skips deleted parents — migration 21).
  3. Neo4j: DETACH DELETE the ProcessInstance nodes and their WorkItem nodes (projection only; definitions untouched).
Anything started at/after --before is kept (a regression running right now).
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from neo4j import GraphDatabase

DSN = os.environ.get('SUPABASE_DSN', 'postgresql://postgres:postgres@127.0.0.1:54322/postgres')
NEO4J = ('bolt://127.0.0.1:7687', ('neo4j', os.environ.get('NEO4J_PASSWORD', 'hydpass123')))
OPEN = ('TODO', 'IN_PROGRESS', 'SUBMITTED', 'PENDING')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--before', required=True, help='ISO instant; instances started before this are residue')
    ap.add_argument('--out', required=True)
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    cutoff = datetime.fromisoformat(a.before.replace('Z', '+00:00'))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(DSN, autocommit=False) as db:
        inst = db.execute("select * from bpm_proc_inst where status='RUNNING' and not is_deleted and start_date < %s order by start_date",
                          (cutoff,)).fetchall()
        cols = [d.name for d in db.execute('select * from bpm_proc_inst limit 0').description]
        instances = [dict(zip(cols, r)) for r in inst]
        ids = [i['proc_inst_id'] for i in instances]
        tcols = [d.name for d in db.execute('select * from todolist limit 0').description]
        todos = [dict(zip(tcols, r)) for r in db.execute('select * from todolist where proc_inst_id = any(%s)', (ids,)).fetchall()] if ids else []
        driver = GraphDatabase.driver(NEO4J[0], auth=NEO4J[1])
        with driver.session() as s:
            graph = s.run('MATCH (p:ProcessInstance) WHERE p.id IN $ids OPTIONAL MATCH (p)<-[:IN_INSTANCE]-(w:WorkItem) '
                          'RETURN p.id AS id, properties(p) AS props, collect(properties(w)) AS workitems', ids=ids).data()
        backup = {'cutoff': cutoff.isoformat(), 'instances': instances, 'todolist': todos, 'graph': graph}
        (out / 'backup.json').write_text(json.dumps(backup, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
        by_def = {}
        for i in instances:
            by_def[i['proc_def_id']] = by_def.get(i['proc_def_id'], 0) + 1
        open_todos = [t for t in todos if t['status'] in OPEN]
        print(f"residue instances: {len(ids)} {by_def}; todolist rows {len(todos)} (open {len(open_todos)}); graph nodes "
              f"{len(graph)} + workitems {sum(len(g['workitems']) for g in graph)}")
        if not a.apply:
            print('dry run — nothing changed; backup written to', out / 'backup.json'); return
        n1 = db.execute('update bpm_proc_inst set is_deleted = true where proc_inst_id = any(%s) and not is_deleted', (ids,)).rowcount
        n2 = db.execute("update todolist set status='CANCELLED', end_date=coalesce(end_date, now()), "
                        "log=coalesce(log,'')||'[A115 residue cleanup: instance soft-deleted] ' "
                        "where proc_inst_id = any(%s) and status = any(%s)", (ids, list(OPEN))).rowcount
        db.commit()
        with driver.session() as s:
            n3 = s.run('MATCH (p:ProcessInstance) WHERE p.id IN $ids OPTIONAL MATCH (p)<-[:IN_INSTANCE]-(w:WorkItem) '
                       'WITH p, collect(w) AS ws FOREACH (w IN ws | DETACH DELETE w) DETACH DELETE p RETURN count(p) AS n', ids=ids).single()['n']
        driver.close()
        print(f'applied: instances soft-deleted {n1}, open todolist rows cancelled {n2}, graph instances deleted {n3}')
        (out / 'applied.json').write_text(json.dumps({'instances': n1, 'todolist_cancelled': n2, 'graph_instances': n3, 'ids': ids},
                                                     ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
