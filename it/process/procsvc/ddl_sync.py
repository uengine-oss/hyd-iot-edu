"""A087 (DoD 4, 회의 L253~293): a change of the business DDL reaches the ontology without a person noticing it first.

Physical InputData were bound to `ent.<table>.<column>` when a reviewed DDL was ingested. If that column later disappears
or changes its type family (number → text, timestamp → number), the binding is dangling: reading it would fail or, worse,
return a value with a different meaning. Following process-gpt-strategy `ontology_sync` (poll the source, apply the
difference idempotently, never link to a target that does not exist), the live catalog is polled and each physical input
gets `sourceState` OK | MISSING | TYPE_CHANGED | COMMENT_CHANGED (+ the live type and comment, and when the state changed).
COMMENT_CHANGED (A115, r14 A10): a column comment is the business meaning; when only the comment changed, the type family
is the same and the binding stayed OK with the old meaning. The comparison is against the live comment the first sync after
an ingestion saw (`sourceBaseComment`, '' for none), not against the reviewed DDL file: a data dictionary often carries
comments the database itself never got (live 2026-10-07: comparing to the file blocked a matching column at once). A
re-ingestion clears the baseline (graph_ingest._claim), so the reviewed meaning starts a new one. The node is not deleted —
rules may still reference it; the agent refuses to read a non-OK binding (fact unknown with the reason) and a knowledge
author re-ingests the changed DDL. New columns are not ingested automatically: ingestion stays a reviewed act.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .ingest import Column

PHYSICAL_Q = """MATCH (i:InputData) WHERE i.schema IS NOT NULL AND i.table IS NOT NULL AND i.column IS NOT NULL
RETURN i.id AS id, i.datasource AS datasource, i.schema AS schema, i.table AS table, i.column AS column, i.sqlType AS sqlType,
       i.sourceState AS state, i.sourceLiveType AS live, i.sourceLiveComment AS liveComment, i.sourceBaseComment AS baseComment
ORDER BY i.id"""
APPLY_Q = """UNWIND $rows AS r MATCH (i:InputData {id: r.id})
SET i.sourceState = r.state, i.sourceLiveType = r.live, i.sourceLiveComment = r.comment, i.sourceBaseComment = r.base,
    i.sourceCheckedAt = $now
RETURN count(i) AS n"""
COLUMNS_SQL = """select c.table_schema, c.table_name, c.column_name, c.data_type,
       col_description(format('%%I.%%I', c.table_schema, c.table_name)::regclass, c.ordinal_position)
from information_schema.columns c where c.table_schema = any(%s)"""
STATES = ('OK', 'MISSING', 'TYPE_CHANGED', 'COMMENT_CHANGED')


def family(sql_type: str | None) -> str:
    """The meaning class a rule relies on: a point in time, or the DMN typeRef of the column."""
    t = (sql_type or '').lower()
    if 'timestamp' in t:
        return 'point-in-time'
    return Column('x', t).type_ref


def drift(inputs: list[dict], columns: dict[tuple[str, str, str], str | tuple[str, str | None]]) -> list[dict]:
    """Pure: the state of every physical input against the live catalog {(schema, table, column): data_type or
    (data_type, comment)}. The comment is compared only when the catalog gives it; the first such look records the
    baseline (`base`), a later different live comment is COMMENT_CHANGED."""
    out = []
    for i in inputs:
        entry = columns.get((i['schema'], i['table'], i['column']))
        with_comment = isinstance(entry, tuple)
        live, comment = entry if with_comment else (entry, None)
        base = i.get('baseComment')
        if with_comment and live is not None and base is None:
            base = comment or ''
        if live is None:
            state = 'MISSING'
        elif family(live) != family(i.get('sqlType')):
            state = 'TYPE_CHANGED'
        elif with_comment and (comment or '') != base:
            state = 'COMMENT_CHANGED'
        else:
            state = 'OK'
        changed = state != (i.get('state') or 'OK') or (live or None) != (i.get('live') or None) \
            or (with_comment and ((comment or None) != (i.get('liveComment') or None) or base != i.get('baseComment')))
        out.append({'id': i['id'], 'state': state, 'live': live, 'declared': i.get('sqlType'), 'comment': comment,
                    'base': base, 'changed': changed})
    return out


def live_columns(connect, schemas: list[str]) -> dict[tuple[str, str, str], str]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(COLUMNS_SQL, (sorted(set(schemas)),))
        return {(s, t, c): (d, note) for s, t, c, d, note in cur.fetchall()}


def sync(q, connect, now: datetime | None = None) -> dict:
    """Poll once: read the bound inputs, read the live catalog, write only the inputs whose state changed."""
    inputs = [i for i in q(PHYSICAL_Q) if i.get('datasource') in (None, 'hyd-enterprise')]
    if not inputs:
        return {'checked': 0, 'changed': 0, 'states': {}}
    rows = drift(inputs, live_columns(connect, [i['schema'] for i in inputs]))
    changed = [r for r in rows if r['changed']]
    if changed:
        q(APPLY_Q, rows=[{k: r[k] for k in ('id', 'state', 'live', 'comment', 'base')} for r in changed],
          now=(now or datetime.now(timezone.utc)).isoformat())
    states = {s: sorted(r['id'] for r in rows if r['state'] == s) for s in STATES}
    return {'checked': len(rows), 'changed': len(changed), 'states': {k: v for k, v in states.items() if v},
            'changes': [{k: r[k] for k in ('id', 'state', 'declared', 'live')} for r in changed]}
