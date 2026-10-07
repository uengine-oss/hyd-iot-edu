"""A087 (DoD 4, 회의 L253~293): a change of the business DDL reaches the ontology without a person noticing it first.

Physical InputData were bound to `ent.<table>.<column>` when a reviewed DDL was ingested. If that column later disappears
or changes its type family (number → text, timestamp → number), the binding is dangling: reading it would fail or, worse,
return a value with a different meaning. Following process-gpt-strategy `ontology_sync` (poll the source, apply the
difference idempotently, never link to a target that does not exist), the live catalog is polled and each physical input
gets `sourceState` OK | MISSING | TYPE_CHANGED (+ the live type and when the state changed). The node is not deleted —
rules may still reference it; the agent refuses to read a non-OK binding (fact unknown with the reason) and a knowledge
author re-ingests the changed DDL. New columns are not ingested automatically: ingestion stays a reviewed act.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .ingest import Column

PHYSICAL_Q = """MATCH (i:InputData) WHERE i.schema IS NOT NULL AND i.table IS NOT NULL AND i.column IS NOT NULL
RETURN i.id AS id, i.datasource AS datasource, i.schema AS schema, i.table AS table, i.column AS column, i.sqlType AS sqlType,
       i.sourceState AS state, i.sourceLiveType AS live ORDER BY i.id"""
APPLY_Q = """UNWIND $rows AS r MATCH (i:InputData {id: r.id})
SET i.sourceState = r.state, i.sourceLiveType = r.live, i.sourceCheckedAt = $now RETURN count(i) AS n"""
COLUMNS_SQL = """select table_schema, table_name, column_name, data_type from information_schema.columns
where table_schema = any(%s)"""
STATES = ('OK', 'MISSING', 'TYPE_CHANGED')


def family(sql_type: str | None) -> str:
    """The meaning class a rule relies on: a point in time, or the DMN typeRef of the column."""
    t = (sql_type or '').lower()
    if 'timestamp' in t:
        return 'point-in-time'
    return Column('x', t).type_ref


def drift(inputs: list[dict], columns: dict[tuple[str, str, str], str]) -> list[dict]:
    """Pure: the state of every physical input against the live catalog {(schema, table, column): data_type}."""
    out = []
    for i in inputs:
        live = columns.get((i['schema'], i['table'], i['column']))
        state = 'MISSING' if live is None else ('OK' if family(live) == family(i.get('sqlType')) else 'TYPE_CHANGED')
        out.append({'id': i['id'], 'state': state, 'live': live, 'declared': i.get('sqlType'),
                    'changed': state != (i.get('state') or 'OK') or (live or None) != (i.get('live') or None)})
    return out


def live_columns(connect, schemas: list[str]) -> dict[tuple[str, str, str], str]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(COLUMNS_SQL, (sorted(set(schemas)),))
        return {(s, t, c): d for s, t, c, d in cur.fetchall()}


def sync(q, connect, now: datetime | None = None) -> dict:
    """Poll once: read the bound inputs, read the live catalog, write only the inputs whose state changed."""
    inputs = [i for i in q(PHYSICAL_Q) if i.get('datasource') in (None, 'hyd-enterprise')]
    if not inputs:
        return {'checked': 0, 'changed': 0, 'states': {}}
    rows = drift(inputs, live_columns(connect, [i['schema'] for i in inputs]))
    changed = [r for r in rows if r['changed']]
    if changed:
        q(APPLY_Q, rows=[{'id': r['id'], 'state': r['state'], 'live': r['live']} for r in changed],
          now=(now or datetime.now(timezone.utc)).isoformat())
    states = {s: sorted(r['id'] for r in rows if r['state'] == s) for s in STATES}
    return {'checked': len(rows), 'changed': len(changed), 'states': {k: v for k, v in states.items() if v},
            'changes': [{k: r[k] for k in ('id', 'state', 'declared', 'live')} for r in changed]}
