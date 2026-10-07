"""Transactional DDL ownership journal; never detach-delete another writer's data.

The small teaching deployment serializes ingestion with one Neo4j write lock.
Other graph writers do not take that lock: owned-field drift is checked and a
conflict requires reconciliation, rather than silently overwriting their edits.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from .ingest import validate_plan

INPUT_FIELDS = ('name', 'typeRef', 'variable', 'datasource', 'catalog', 'schema',
                'table', 'column', 'sqlType', 'assetColumn', 'derive', 'source_id', 'ingested_at')
SYSTEM_FIELDS = ('name', 'zone', 'source_id')
JOURNAL_FIELDS = ('_ingest_base', '_ingest_history', '_ingest_batches', '_ingest_created')
# A087: observations the DDL source sync records on a binding — system state, not someone's edit of the input
SYNC_FIELDS = ('sourceState', 'sourceLiveType', 'sourceCheckedAt')


class Conflict(ValueError):
    pass


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _lock(tx):
    # Unique constraint is installed by ensure_schema before transactions begin.
    tx.run("MERGE (n:IngestionControl {id:'ingestion:ddl'}) "
           "ON CREATE SET n.sequence=0 "
           "SET n.name=coalesce(n.name,'DDL ingestion transaction lock'), n.sequence=coalesce(n.sequence,0)+1").consume()   # A092: schema requires name; older lock nodes had none


def ensure_schema(session):
    for label in ('IngestionControl', 'IngestionBatch', 'InputData', 'System'):
        session.run(f'CREATE CONSTRAINT ingest_{label.lower()}_id IF NOT EXISTS '
                    f'FOR (n:{label}) REQUIRE n.id IS UNIQUE').consume()


def _read(tx, label, nid):
    # Hold the node write lock through validation/restoration. A concurrent
    # property writer cannot slip between our comparison and DELETE/SET.
    row = tx.run(f'MATCH (n:{label} {{id:$id}}) SET n.id=n.id RETURN properties(n) AS p', id=nid).single()
    if row is None:
        return None
    props = dict(row['p'])
    sources = []
    if label == 'InputData':
        sources = [dict(r) for r in tx.run(
            'MATCH (:InputData {id:$id})-[r:SOURCED_FROM]->(s) '
            'RETURN s.id AS id, labels(s) AS labels, properties(r) AS props ORDER BY s.id', id=nid)]
    fields = INPUT_FIELDS if label == 'InputData' else SYSTEM_FIELDS
    return props, {'props': {k: props.get(k) for k in fields}, 'sources': sources}


def _apply(tx, label, nid, state):
    tx.run(f'MATCH (n:{label} {{id:$id}}) SET n += $props', id=nid, props=state['props']).consume()
    if label == 'InputData':
        tx.run('MATCH (:InputData {id:$id})-[r:SOURCED_FROM]->() DELETE r', id=nid).consume()
        for source in state['sources']:
            # Source identity includes its label; unrelated nodes can share an id.
            labels = source['labels']
            if not labels or any(not l.replace('_', '').isalnum() for l in labels):
                raise Conflict('출처 레이블을 복원할 수 없습니다')
            pattern = ':'.join(labels)
            row = tx.run(f'MATCH (n:InputData {{id:$id}}), (s:{pattern} {{id:$source}}) '
                         'MERGE (n)-[r:SOURCED_FROM]->(s) SET r = $props RETURN count(r) AS n',
                         id=nid, source=source['id'], props=source['props']).single()
            if row['n'] != 1:
                raise Conflict('원래 출처가 삭제되거나 중복되어 복원할 수 없습니다')


def _history(props, current):
    history = json.loads(props.get('_ingest_history', '[]'))
    if history and current != history[-1]['state']:
        raise Conflict('적재 이후 다른 작업이 원천 속성/출처를 변경했습니다. 먼저 차이를 검토하세요')
    return history


def _claim(tx, label, item, batch, at):
    nid = item['id']
    read = _read(tx, label, nid)
    created = read is None
    if created:
        tx.run(f'CREATE (n:{label} {{id:$id}})', id=nid).consume()
        read = _read(tx, label, nid)
    props, current = read
    if props.get('ingest_batch'):
        raise Conflict('이전 방식의 적재 데이터입니다. 소유권 이력 없이 덮어쓸 수 없습니다')
    history = _history(props, current)
    base = props.get('_ingest_base', _json(current))
    # Existing semantic Systems retain their properties; DDL only claims usage.
    if label == 'System' and not created:
        state = current
    else:
        fields = INPUT_FIELDS if label == 'InputData' else SYSTEM_FIELDS
        values = dict(item, ingested_at=at)
        state = {'props': {k: values.get(k) for k in fields}, 'sources': []}
        if label == 'InputData':
            state['sources'] = [{'id': item['system'], 'labels': ['System'], 'props': {}}]
    history.append({'batch': batch, 'state': state})
    _apply(tx, label, nid, state)
    tx.run(f'MATCH (n:{label} {{id:$id}}) SET n += $journal', id=nid, journal={
        '_ingest_base': base, '_ingest_created': props.get('_ingest_created', created),
        '_ingest_history': _json(history), '_ingest_batches': [h['batch'] for h in history]}).consume()


def commit(session, plan):
    validate_plan(plan)
    payload = {k: plan[k] for k in ('batch', 'filename', 'systems', 'inputs')}
    # Order in the preview is not part of the content identity.
    payload.update(systems=sorted(payload['systems'], key=lambda i: i['id']),
                   inputs=sorted(payload['inputs'], key=lambda i: i['id']))
    fingerprint = hashlib.sha256(_json(payload).encode()).hexdigest()
    at = datetime.now(timezone.utc).isoformat()
    ensure_schema(session)

    def run(tx):
        _lock(tx)
        old = tx.run('MATCH (b:IngestionBatch {id:$id}) RETURN b.fingerprint AS fingerprint, b.status AS status',
                     id=plan['batch']).single()
        out = {'batch': plan['batch'], 'filename': plan['filename'],
               'systems': len(plan['systems']), 'inputs': len(plan['inputs']), 'replayed': bool(old)}
        if old:
            if old['fingerprint'] != fingerprint or old['status'] != 'ACTIVE':
                raise Conflict('배치 ID가 이미 사용됐습니다. 변경 또는 되돌리기 후에는 새 미리보기를 만드세요')
            return out
        for label, items in (('System', payload['systems']), ('InputData', payload['inputs'])):
            for item in items:
                _claim(tx, label, item, plan['batch'], at)
        tx.run('CREATE (b:IngestionBatch {id:$id, name:$filename, filename:$filename, '
               'fingerprint:$fingerprint, status:"ACTIVE", createdAt:$at})',
               id=plan['batch'], filename=plan['filename'], fingerprint=fingerprint, at=at).consume()
        return out
    return session.execute_write(run)


def clear(session, batch):
    ensure_schema(session)

    def run(tx):
        _lock(tx)
        receipt = tx.run('MATCH (b:IngestionBatch {id:$id}) RETURN b.status AS status', id=batch).single()
        out = {'batch': batch, 'deleted': 0, 'restored': 0, 'retained': 0, 'replayed': False}
        if receipt is None:
            legacy = tx.run('MATCH (n) WHERE n.ingest_batch=$batch RETURN count(n) AS n', batch=batch).single()
            if legacy['n']:
                raise Conflict('이전 배치에는 복원 이력이 없습니다. 자동 삭제하지 않습니다')
            raise KeyError(batch)
        if receipt['status'] == 'CLEARED':
            return dict(out, replayed=True)
        for label in ('InputData', 'System'):
            ids = [r['id'] for r in tx.run(f'MATCH (n:{label}) WHERE $batch IN n._ingest_batches '
                                          'RETURN n.id AS id ORDER BY id', batch=batch)]
            for nid in ids:
                props, current = _read(tx, label, nid)
                history = _history(props, current)
                remaining = [h for h in history if h['batch'] != batch]
                if remaining:
                    _apply(tx, label, nid, remaining[-1]['state'])
                    tx.run(f'MATCH (n:{label} {{id:$id}}) SET n._ingest_history=$history, n._ingest_batches=$batches',
                           id=nid, history=_json(remaining), batches=[h['batch'] for h in remaining]).consume()
                    out['retained'] += 1
                    continue
                if props['_ingest_created']:
                    fields = INPUT_FIELDS if label == 'InputData' else SYSTEM_FIELDS
                    foreign_props = set(props) - set(fields) - set(JOURNAL_FIELDS) - set(SYNC_FIELDS) - {'id'}
                    labels = tx.run(f'MATCH (n:{label} {{id:$id}}) RETURN labels(n) AS labels', id=nid).single()['labels']
                    externally_extended = bool(foreign_props or set(labels) - {label})
                    if label == 'InputData':
                        refs = tx.run('MATCH (n:InputData {id:$id})-[r]-() '
                                      'WHERE NOT (type(r)="SOURCED_FROM" AND startNode(r)=n) '
                                      'RETURN count(r) AS n', id=nid).single()['n']
                        if refs:
                            raise Conflict('규칙/작업 등이 이 입력을 사용 중입니다. 참조를 먼저 해제하세요')
                        if externally_extended:
                            raise Conflict('다른 작업이 이 입력의 속성/유형을 추가했습니다. 해당 변경을 먼저 검토하세요')
                        tx.run('MATCH (:InputData {id:$id})-[r:SOURCED_FROM]->() DELETE r', id=nid).consume()
                    degree = tx.run(f'MATCH (n:{label} {{id:$id}}) OPTIONAL MATCH (n)-[r]-() '
                                    'RETURN count(r) AS n', id=nid).single()['n']
                    if not degree and not externally_extended:
                        tx.run(f'MATCH (n:{label} {{id:$id}}) DELETE n', id=nid).consume()
                        out['deleted'] += 1
                        continue
                    # A generated System adopted by other data is preserved.
                    out['retained'] += 1
                else:
                    _apply(tx, label, nid, json.loads(props['_ingest_base']))
                    out['restored'] += 1
                tx.run(f'MATCH (n:{label} {{id:$id}}) SET n += $props', id=nid,
                       props={k: None for k in JOURNAL_FIELDS}).consume()
        tx.run('MATCH (b:IngestionBatch {id:$id}) SET b.status="CLEARED", b.clearedAt=$at',
               id=batch, at=datetime.now(timezone.utc).isoformat()).consume()
        return out
    return session.execute_write(run)


BATCHES_Q = '''
MATCH (b:IngestionBatch {status:'ACTIVE'}), (n)
WHERE b.id IN n._ingest_batches
RETURN b.id AS batch, labels(n)[0] AS label, count(n) AS nodes, b.filename AS source, false AS legacy
UNION ALL
MATCH (n) WHERE n.ingest_batch IS NOT NULL
RETURN n.ingest_batch AS batch, labels(n)[0] AS label, count(n) AS nodes, min(n.source_id) AS source, true AS legacy
'''
