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

from hydcommon.fabric import DDL_SOURCES, ENT, SOURCES

from . import ingest
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
    inputs = [i for i in q(PHYSICAL_Q) if i.get('datasource') in (None, *DDL_SOURCES)]
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


TABLES_SQL = "select table_schema, table_name from information_schema.tables where table_schema = any(%s)"


def place(text: str, requested, connect) -> tuple[list, str, list[str]]:
    """Which registered source a DDL file describes, and its tables parsed in that source's schema (an unqualified CREATE
    TABLE lands in the connection's own schema: 업무 DB → ent, 옛 설비 DB → legacy). Returns (tables, datasource, notes).

    requested = the person's pick (a DDL_SOURCES id). Not picked: the source whose live catalog holds the most of the file's
    tables (실라버스 통합 40행 — 제공 legacy-plant-db.sql 은 옛 설비 DB). None of them anywhere: the business DB, said in notes
    (the link screen then shows 「원천에 이 열이 없습니다」). A tie is the person's pick, not a guess."""
    choices = ', '.join(SOURCES[d]['label'] for d in DDL_SOURCES)     # 학생 문장 — 원천 id 가 아니라 화면의 원천 이름(마지막고침 검증 H12)
    names = sorted({t.name for t in ingest.parse_ddl(text)})
    notes: list[str] = []
    if requested not in (None, ''):
        if requested not in DDL_SOURCES:
            raise ValueError(f'등록된 원천이 아닙니다: {requested} — 고를 수 있는 원천: {choices}')
        source = requested
    else:
        schemas = {SOURCES[d]['schema']: d for d in DDL_SOURCES}
        try:
            with connect() as conn, conn.cursor() as cur:
                cur.execute(TABLES_SQL, (sorted(schemas),))
                live = cur.fetchall()
        except Exception as e:  # noqa: BLE001 — psycopg/OS errors: the pick cannot be made, say so
            raise ValueError(f'업무 DB 카탈로그를 읽지 못해 이 파일의 원천을 정하지 못했습니다({type(e).__name__}) — 원천을 고르세요: {choices}') from None
        held = {d: {t for s, t in live if schemas[s] == d and t in names} for d in DDL_SOURCES}
        best = max(len(v) for v in held.values())
        top = [d for d in DDL_SOURCES if len(held[d]) == best]
        if best == 0:
            source = ENT
            notes.append(f"등록된 원천({choices})에 이 파일의 표가 없어 {SOURCES[ENT]['label']}로 둡니다 — 적재하면 연결 화면에 「원천에 이 열이 없습니다」로 보입니다")
        elif len(top) > 1:
            raise ValueError(f"이 파일의 표가 여러 원천({', '.join(SOURCES[d]['label'] for d in top)})에 있습니다 — 원천을 고르세요: {choices}")
        else:
            source = top[0]
            missing = [n for n in names if n not in held[source]]
            notes.append(f"이 파일의 표가 있는 원천: {SOURCES[source]['label']} ({SOURCES[source]['schema']} 스키마)"
                         + (f" — 그 원천에 없는 표: {', '.join(missing)}" if missing else ''))
    return ingest.parse_ddl(text, SOURCES[source]['schema']), source, notes
