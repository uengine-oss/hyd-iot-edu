"""Atomic, source-owned SOP graph replacement with checked, latest-first undo.

Originals and extraction coordinates live in ManualSources. Graph batches retain
the reviewed before/after snapshots. An externally edited graph is never silently
replaced; its owner must reconcile that conflict first.

Execution history (F-2, DECISIONS 35): the case projection records which SOP a person chose and which cause an incident
was diagnosed as by pointing at document-owned nodes (HISTORY_RELATIONS). That history is an audit record, not part of the
document's graph: it is split off before the drift check, a revision updates surviving nodes in place so it stays attached,
and a revision or rollback that would drop a node it points at is refused, naming the node and the history.

Ownership (C1): which nodes a document owns is the document's journal (ManualIngestionDocument.snapshot = the reviewed
after-state of its head batch). The original four labels (KnowledgeSource · ManualSection · Skill · Step) and their edges
still carry `_manual_document` because schema v2 declares it there and other readers use it (admin skill edit, AFFECTS).
The knowledge labels added by C1 (FailureMode · Cause · Evidence · Rule) and their relationships carry no extra property —
schema v2 stays unchanged — and are owned through the journal only. The snapshot of a document is every owned node and
every relationship touching one except listed execution history, so any other foreign reference is still detected as drift.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from .manual_review import canonical, document_key
from .kgadmin import skill_id
from . import kgadmin, manual_knowledge


class Conflict(ValueError):
    pass


TAGGED_LABELS = ('KnowledgeSource', 'ManualSection', 'Skill', 'Step')          # carry _manual_document (schema-declared)
KNOWLEDGE_LABELS = ('FailureMode', 'Cause', 'Evidence', 'Rule')                # C1: owned through the journal
LABELS = TAGGED_LABELS + KNOWLEDGE_LABELS
TAGGED_RELATIONS = ('PART_OF', 'HAS_STEP', 'REFERS_TO', 'REMEDIED_BY', 'MITIGATED_BY', 'PREVENTED_BY', 'APPROVED_BY', 'HAS_SKILL', 'OUTPUTS',
                    'AFFECTS')
KNOWLEDGE_RELATIONS = ('OCCURS_IN', 'INDICATES', 'LEADS_TO', 'CAUSES', 'INVOLVES_PART', 'DISTURBS', 'EVIDENCED_BY', 'ADDRESSES',
                       'CONSISTS_OF', 'HAS_RULE', 'TESTS', 'APPLIES_TO', 'PENALIZES', 'DERIVED_FROM')
RELATIONS = TAGGED_RELATIONS + KNOWLEDGE_RELATIONS
# Execution history the case projection attaches to document-owned nodes (procsvc/case_projection.py DECISION_CASE_Q ·
# INCIDENT_Q): (outside label, relation, owned label). Only these are kept across revisions; any other foreign edge is drift.
HISTORY_RELATIONS = (('DecisionCase', 'CHOSE', 'Skill'), ('Incident', 'DIAGNOSED_AS', 'Cause'))
# labels a document's edges may point at outside the document (existing structure or another source's knowledge)
TARGET_LABELS = LABELS + ('Role', 'System', 'StateVariable', 'Measure', 'Component', 'Symptom', 'Part', 'Action',
                          'DecisionTable', 'InputData')


def ensure_schema(session):
    for label in (*TAGGED_LABELS, 'ManualIngestionDocument', 'ManualIngestionBatch', 'IngestionControl'):
        session.run(f'CREATE CONSTRAINT manual_{label.lower()}_id IF NOT EXISTS '
                    f'FOR (n:{label}) REQUIRE n.id IS UNIQUE').consume()
    # Existing SOP authoring already promises one skill per SOP number. Enforce it
    # for writers which do not participate in the ingestion lock too.
    session.run('CREATE CONSTRAINT manual_skill_sop IF NOT EXISTS '
                'FOR (n:Skill) REQUIRE n.sopId IS UNIQUE').consume()


def _lock(tx):
    tx.run("MERGE (n:IngestionControl {id:'ingestion:manual'}) "
           "ON CREATE SET n.sequence=0 "
           "SET n.name=coalesce(n.name,'manual ingestion transaction lock'), n.sequence=coalesce(n.sequence,0)+1").consume()   # A092: schema requires name


def _sort(snapshot):
    return {key: sorted(value, key=canonical) for key, value in snapshot.items()}


def owned_keys(snapshot):
    """(label, id) of every node a journal snapshot owns."""
    return sorted({(n['labels'][0], n['props']['id']) for n in (snapshot or {}).get('nodes') or []})


def _is_history(edge, from_owned, to_owned):
    return not from_owned and to_owned and any(
        out in edge['from_labels'] and kind == edge['type'] and own in edge['to_labels'] for out, kind, own in HISTORY_RELATIONS)


def _snapshot(tx, document, owned=()):
    """The current graph state of what the document owns, as (graph, history).

    graph: its journal-owned nodes (plus any node still tagged with the document, so a tagged node missing from the journal
    shows up as drift) and every relationship touching one of them, except history: the HISTORY_RELATIONS edges that come
    from outside the document into an owned node."""
    by_label = {}
    for label, nid in owned:
        by_label.setdefault(label, []).append(nid)
    rows = {}
    for label, ids in by_label.items():
        if label not in LABELS:
            raise Conflict('보관된 노드 유형이 지원 계약과 다릅니다')
        for r in tx.run(f'MATCH (n:{label}) WHERE n.id IN $ids SET n.id=n.id '
                        'RETURN elementId(n) AS eid, labels(n) AS labels, properties(n) AS props', ids=ids).data():
            rows[r['eid']] = r
    for r in tx.run('MATCH (n) WHERE n._manual_document=$document SET n.id=n.id '
                    'RETURN elementId(n) AS eid, labels(n) AS labels, properties(n) AS props', document=document).data():
        rows[r['eid']] = r
    nodes = [dict(labels=sorted(r['labels']), props=r['props']) for r in rows.values()]
    found = tx.run('MATCH (a)-[r]->(b) WHERE elementId(a) IN $e OR elementId(b) IN $e '
                   'RETURN elementId(a) AS from_eid, labels(a) AS from_labels, a.id AS from_id, '
                   'elementId(b) AS to_eid, labels(b) AS to_labels, b.id AS to_id, '
                   'type(r) AS type, properties(r) AS props', e=list(rows)).data() if rows else []
    edges, history = [], []
    for edge in found:
        from_owned, to_owned = edge.pop('from_eid') in rows, edge.pop('to_eid') in rows
        edge['from_labels'].sort()
        edge['to_labels'].sort()
        (history if _is_history(edge, from_owned, to_owned) else edges).append(edge)
    return _sort({'nodes': nodes, 'edges': edges}), sorted(history, key=canonical)


def _node_text(labels, nid):
    return f"{':'.join(labels)} {nid}"


def _edge_text(edge):
    return f"({_node_text(edge['from_labels'], edge['from_id'])})-[:{edge['type']}]->({_node_text(edge['to_labels'], edge['to_id'])})"


DRIFT_SHOWN = 5          # items named per kind in a drift refusal; the rest are counted


def _drift(expected, current):
    """What differs between the journal and the graph, named, for the refusal message ('' when equal)."""
    def keyed(snapshot):
        return {(tuple(n['labels']), n['props'].get('id')): n['props'] for n in snapshot['nodes']}
    want, have = keyed(expected), keyed(current)
    want_edges = [canonical(e) for e in expected['edges']]
    have_edges = [canonical(e) for e in current['edges']]
    extra = [e for e in current['edges'] if have_edges.count(canonical(e)) > want_edges.count(canonical(e))]
    missing = [e for e in expected['edges'] if want_edges.count(canonical(e)) > have_edges.count(canonical(e))]
    parts = []
    for title, items in (('기록에 없는 노드', [_node_text(*k) for k in have if k not in want]),
                         ('사라진 노드', [_node_text(*k) for k in want if k not in have]),
                         ('속성이 바뀐 노드', [_node_text(*k) for k in want if k in have and want[k] != have[k]]),
                         ('기록에 없는 관계(사람이 고쳤거나 이력으로 허용되지 않은 바깥 관계)', sorted({_edge_text(e) for e in extra})),
                         ('사라지거나 바뀐 관계', sorted({_edge_text(e) for e in missing}))):
        if items:
            more = f' 외 {len(items) - DRIFT_SHOWN}건' if len(items) > DRIFT_SHOWN else ''
            parts.append(f"{title} {len(items)}건: {', '.join(items[:DRIFT_SHOWN])}{more}")
    return '; '.join(parts)


def _check_unchanged(expected, current, message):
    """Equality with the journal is the rule; _drift only names what differs."""
    expected = _sort(expected)
    if current != expected:
        drift = _drift(expected, current)
        raise Conflict(f'{message} — {drift}' if drift else message)


def _history_summary(history):
    """Kept history per owned node and relation type, e.g. [{node: 'Skill skill:sop-pur-13', type: 'CHOSE', count: 3}]."""
    counts = {}
    for edge in history:
        key = (_node_text(edge['to_labels'], edge['to_id']), edge['type'])
        counts[key] = counts.get(key, 0) + 1
    return [dict(node=node, type=kind, count=n) for (node, kind), n in sorted(counts.items())]


def desired(plan):
    document = plan['document']
    prefix = 'manual:' + document + ':' + plan['sha256']
    nodes, edges = [], []

    def node(label, nid, **props):
        tag = {'_manual_document': document} if label in TAGGED_LABELS else {}
        nodes.append({'labels': [label], 'props': dict(id=nid, **tag, **props)})
        return label, nid

    def edge(a, kind, b, tagged=None, **props):
        # tagged=False: a C1 knowledge edge of a type the A075/A079 paths also write tagged (OUTPUTS) — schema v2 declares no
        # _manual_document on it, so the document's own rule outputs stay untagged and are owned through the journal.
        tag = {'_manual_document': document} if (kind in TAGGED_RELATIONS if tagged is None else tagged) else {}
        edges.append(dict(from_labels=[a[0]], from_id=a[1], to_labels=[b[0]], to_id=b[1],
                          type=kind, props={**tag, **props}))

    source = node('KnowledgeSource', 'ks:' + prefix, name=plan['filename'], kind='manual',
                  source_id=plan['source_id'], document_id=plan['document_id'], sha256=plan['sha256'],
                  extractor=plan['extractor'])
    sections = {}
    for s in plan['sections']:
        key = hashlib.sha256(s['ref'].encode()).hexdigest()
        sections[s['ref']] = node('ManualSection', prefix + ':section:' + key, ref=s['ref'],
                       title=s['title'], excerpt=s['excerpt'], source_id=plan['source_id'],
                       citation=canonical(s['anchor']))
        edge(sections[s['ref']], 'PART_OF', source)
    fms, causes = manual_knowledge.desired(plan, node, edge, sections, skill_id)
    own_candidates, own_rules = manual_knowledge.own_candidate_outputs(plan, skill_id)
    for p in plan['procedures']:
        skill = node('Skill', skill_id(p['id']), name=p['name'], sopId=p['id'], kind=p['kind'],
                     description=f"매뉴얼 {plan['filename']}에서 검토한 SOP", source_id=plan['source_id'],
                     citation=canonical(p['anchor']))
        edge(fms.get(p['failureMode'], ('FailureMode', p['failureMode'])), p['relation'], skill)
        # C1: a document that states its own candidate rule is not widened; a preventive (PREVENTED_BY) SOP never joins incident rules
        if skill[1] not in own_candidates and p['relation'] in kgadmin.CORRECTIVE_RELATIONS:
            for rule in (plan.get('candidate_rules') or {}).get(p['failureMode'], []):
                if rule not in own_rules:
                    edge(('Rule', rule), 'OUTPUTS', skill)          # A075: the reviewed SOP joins the failure mode's candidate rules
        edge(skill, 'APPROVED_BY', ('Role', p['approver']))
        for a in p.get('affects') or []:            # A079: reviewed impact → the SOP reaches the BSC like seeded skills
            edge(skill, 'AFFECTS', (a['label'], a['target']), sign=a['sign'], **({'note': a['note']} if a['note'] else {}))
        for seq, a in enumerate(p.get('actions') or [], 1):          # C1: atomic actions with their values (card · execution)
            edge(skill, 'CONSISTS_OF', ('Action', a['action']), seq=seq, **({'value': a['value']} if a['value'] is not None else {}))
        for c in p.get('addresses') or []:                           # C1: the cause this SOP fixes
            edge(skill, 'ADDRESSES', causes.get(c, ('Cause', c)))
        edge(('System', 'sys:scada' if p['kind'] == 'control' else 'sys:cmms'), 'HAS_SKILL', skill)
        for step in p['steps']:
            st = node('Step', skill[1] + ':' + str(step['order']), order=step['order'], text=step['text'],
                      source_id=plan['source_id'], citation=canonical(step['anchor']))
            edge(skill, 'HAS_STEP', st)
            edge(st, 'REFERS_TO', sections[step['manual']])
    return _sort(dict(nodes=nodes, edges=edges))


def sop_conflicts(session, document, sop_ids):
    """Which proposed SOP ids are already a Skill owned by someone else (another manual document or admin knowledge)."""
    if not sop_ids:return []
    def read(tx):
        rows=tx.run('MATCH (k:Skill) WHERE k.sopId IN $ids RETURN k.sopId AS sop, k.id AS id, k._manual_document AS owner',ids=list(sop_ids)).data()
        return [dict(sop=r['sop'],skill=r['id'],owner=r['owner'] or 'admin',kind='other_document' if r['owner'] else 'admin_knowledge')
                for r in rows if r['owner']!=document]
    return session.execute_read(read)


def _validate_targets(tx, snapshot, owned):
    """Every node the snapshot creates is free or already this document's; every edge end outside it exists exactly once."""
    owned = set(owned)
    mine = {(n['labels'][0], n['props']['id']) for n in snapshot['nodes']}
    for node in snapshot['nodes']:
        label, nid = node['labels'][0], node['props']['id']
        old = tx.run(f'MATCH (n:{label} {{id:$id}}) SET n.id=n.id RETURN n.id AS id', id=nid).single()
        if old and (label, nid) not in owned:
            raise Conflict(f'{label} {nid}: 다른 원천/기존 지식이 소유합니다. 덮어쓰지 않았습니다')
        if label == 'Skill':
            sop = tx.run('MATCH (n:Skill {sopId:$sop}) SET n.id=n.id RETURN n.id AS id',
                         sop=node['props']['sopId']).single()
            if sop and (sop['id'] != nid or ('Skill', sop['id']) not in owned):
                raise Conflict(f"SOP 번호 {node['props']['sopId']}는 다른 원천의 스킬이 사용 중입니다")
    for edge in snapshot['edges']:
        for side in ('from', 'to'):
            labels, nid = edge[side + '_labels'], edge[side + '_id']
            if (labels[0], nid) in mine:
                continue
            pattern = ':'.join(labels)
            rows = tx.run(f'MATCH (n:{pattern} {{id:$id}}) SET n.id=n.id RETURN labels(n) AS labels', id=nid).data()
            if len(rows) != 1 or sorted(rows[0]['labels']) != labels:
                raise Conflict(f'{pattern} {nid}: 대상이 없거나 유형이 변경됐습니다')


def _node_key(node):
    label = node['labels'][0]
    if label not in LABELS or len(node['labels']) != 1:
        raise Conflict('보관된 노드 유형이 지원 계약과 다릅니다')
    return label, node['props']['id']


def _replace(tx, current, target, history):
    """Turn the document graph `current` into `target` in place.

    Caller verified `current` equals the journal, so every relationship in it is the document's own; each is removed by its
    identity and the target's are created. A node kept by the target (same label and id) is updated in place, so the execution
    history pointing at it (`history`, never deleted) stays attached. A node the target drops is deleted — unless history
    points at it: then the whole revision is refused before any write. No DETACH DELETE is used: an unexpected foreign
    reference makes the node delete fail and the whole transaction roll back."""
    have = {_node_key(n) for n in current['nodes']}
    keep = {_node_key(n) for n in target['nodes']}
    dropped = have - keep
    blocked = _history_summary([e for e in history if (':'.join(e['to_labels']), e['to_id']) in dropped])
    if blocked:
        named = ', '.join(f"{h['node']} ← {h['type']} {h['count']}건" for h in blocked)
        raise Conflict(f'새 판에서 빠지는 노드에 판단 이력이 연결돼 있어 거절했습니다(이력은 지우지 않습니다): {named}. '
                       '그 노드를 새 판에도 남기거나, 이력을 검토한 뒤 다시 적재하세요')
    for edge in current['edges']:
        a, b = ':'.join(edge['from_labels']), ':'.join(edge['to_labels'])
        if edge['type'] not in RELATIONS:
            raise Conflict('보관된 관계 유형이 지원 계약과 다릅니다')
        row = tx.run(f"MATCH (a:{a} {{id:$a}})-[r:{edge['type']}]->(b:{b} {{id:$b}}) WHERE properties(r) = $props "
                     'WITH r LIMIT 1 DELETE r RETURN count(*) AS n', a=edge['from_id'], b=edge['to_id'], props=edge['props']).single()
        if row['n'] != 1:
            raise Conflict('지울 관계가 기록과 달라 전체 적재를 취소했습니다')
    for label, nid in sorted(dropped):
        tx.run(f'MATCH (n:{label} {{id:$id}}) DELETE n', id=nid).consume()
    for node in target['nodes']:
        label, nid = _node_key(node)
        if (label, nid) in have:
            row = tx.run(f'MATCH (n:{label} {{id:$id}}) SET n=$props RETURN count(n) AS n', id=nid, props=node['props']).single()
            if row['n'] != 1:
                raise Conflict(f'{label} {nid}: 제자리에서 바꿀 노드가 기록과 달라 전체 적재를 취소했습니다')
        else:
            tx.run(f'CREATE (n:{label}) SET n=$props', props=node['props']).consume()
    for edge in target['edges']:
        if edge['type'] not in RELATIONS:
            raise Conflict('보관된 관계 유형이 지원 계약과 다릅니다')
        a, b = ':'.join(edge['from_labels']), ':'.join(edge['to_labels'])
        if any(label not in TARGET_LABELS for label in edge['from_labels'] + edge['to_labels']):
            raise Conflict('보관된 관계의 대상 유형이 다릅니다')
        row = tx.run(f"MATCH (a:{a} {{id:$a}}), (b:{b} {{id:$b}}) CREATE (a)-[r:{edge['type']}]->(b) "
                     'SET r=$props RETURN count(r) AS n', a=edge['from_id'], b=edge['to_id'], props=edge['props']).single()
        if row['n'] != 1:
            raise Conflict('관계의 대상이 없어 전체 적재를 취소했습니다')


def _receipt(plan, at, replayed=False):
    k = plan.get('knowledge') or {}
    return dict(batch=plan['batch'], document_id=plan['document_id'], source_id=plan['source_id'],
                filename=plan['filename'], by=plan['by'], t=at, status='ACTIVE', replayed=replayed,
                sections=len(plan['sections']), procedures=len(plan['procedures']),
                steps=sum(len(p['steps']) for p in plan['procedures']),
                knowledge={kind: [i['id'] for i in k.get(kind) or []] for kind in manual_knowledge.KINDS},
                actions=sum(len(p.get('actions') or []) for p in plan['procedures']),
                candidate_activation=plan.get('candidate_rules') or 'NOT_CHANGED', extraction=plan.get('extraction'),
                skills={p['id']: dict(skill=skill_id(p['id']), failureMode=p['failureMode'], relation=p['relation'])
                        for p in plan['procedures']})


def commit(session, plan):
    ensure_schema(session)
    fingerprint = hashlib.sha256(canonical(plan).encode()).hexdigest()
    after = desired(plan)
    at = datetime.now(timezone.utc).isoformat()

    def run(tx):
        _lock(tx)
        old = tx.run('MATCH (b:ManualIngestionBatch {id:$id}) RETURN properties(b) AS b', id=plan['batch']).single()
        if old:
            old = old['b']
            if old['tenant'] != plan['tenant'] or old['fingerprint'] != fingerprint or old['status'] != 'ACTIVE':
                raise Conflict('배치 ID가 이미 다른 내용/상태로 사용됐습니다')
            current = tx.run('MATCH (d:ManualIngestionDocument {id:$id}) RETURN d.head AS head',
                             id=plan['document']).single()
            is_current = bool(current and current['head'] == plan['batch'])
            return dict(json.loads(old['receipt']), replayed=True, current=is_current,
                        status='ACTIVE' if is_current else 'SUPERSEDED')
        head = tx.run('MATCH (d:ManualIngestionDocument {id:$id}) RETURN d.head AS head, d.snapshot AS snapshot',
                      id=plan['document']).single()
        if (head['head'] if head else None) != plan['previous_batch']:
            raise Conflict('현재 문서 판본이 미리보기 이후 변경됐습니다. 다시 검토하세요')
        expected = json.loads(head['snapshot']) if head else {'nodes': [], 'edges': []}
        before, history = _snapshot(tx, plan['document'], owned_keys(expected))
        _check_unchanged(expected, before, '적재 뒤 문서 그래프(속성/규칙/관계)가 바뀌었습니다. 변경 내용을 먼저 조정하세요')
        _validate_targets(tx, after, owned_keys(before))
        _replace(tx, before, after, history)
        receipt = dict(_receipt(plan, at), history_kept=_history_summary(history))
        tx.run('CREATE (b:ManualIngestionBatch) SET b=$props', props=dict(id=plan['batch'], tenant=plan['tenant'],
               document=plan['document'], previous=plan['previous_batch'], fingerprint=fingerprint, status='ACTIVE',
               before=canonical(before), after=canonical(after), plan=canonical(plan), receipt=canonical(receipt), createdAt=at)).consume()
        tx.run('MERGE (d:ManualIngestionDocument {id:$id}) SET d.head=$head, d.snapshot=$snapshot, d.tenant=$tenant',
               id=plan['document'], head=plan['batch'], snapshot=canonical(after), tenant=plan['tenant']).consume()
        return receipt
    return session.execute_write(run)


def rollback(session, tenant, batch, by):
    if not isinstance(by, str) or not by.strip():
        raise ValueError('되돌리는 담당자가 필요합니다')
    ensure_schema(session)

    def run(tx):
        _lock(tx)
        row = tx.run('MATCH (b:ManualIngestionBatch {id:$id, tenant:$tenant}) RETURN properties(b) AS b',
                     id=batch, tenant=tenant).single()
        if not row:
            raise KeyError(batch)
        record = row['b']
        if record['status'] == 'ROLLED_BACK':
            return dict(batch=batch, status='ROLLED_BACK', replayed=True)
        document = record['document']
        head = tx.run('MATCH (d:ManualIngestionDocument {id:$id}) RETURN d.head AS head', id=document).single()
        if not head or head['head'] != batch:
            raise Conflict('최신 판본부터 순서대로 되돌려야 합니다')
        after = json.loads(record['after'])
        current, history = _snapshot(tx, document, owned_keys(after))
        _check_unchanged(after, current, '적재 뒤 문서 그래프(속성/규칙/관계)가 바뀌어 되돌릴 수 없습니다. 먼저 변경을 검토하세요')
        before = json.loads(record['before'])
        _validate_targets(tx, before, owned_keys(current))
        _replace(tx, current, before, history)
        tx.run('MATCH (d:ManualIngestionDocument {id:$id}) SET d.head=$head, d.snapshot=$snapshot',
               id=document, head=record.get('previous'), snapshot=record['before']).consume()
        tx.run('MATCH (b:ManualIngestionBatch {id:$id}) SET b.status="ROLLED_BACK", b.rolledBackBy=$by, b.rolledBackAt=$at',
               id=batch, by=by.strip(), at=datetime.now(timezone.utc).isoformat()).consume()
        return dict(batch=batch, status='ROLLED_BACK', replayed=False, restored_batch=record.get('previous'),
                    history_kept=_history_summary(history))
    return session.execute_write(run)


def history(session, tenant):
    rows = session.run('MATCH (b:ManualIngestionBatch {tenant:$tenant}) '
                       'OPTIONAL MATCH (d:ManualIngestionDocument {id:b.document}) '
                       'RETURN b.receipt AS receipt, b.status AS status, d.head=b.id AS current '
                       'ORDER BY b.createdAt DESC', tenant=tenant).data()
    return [dict(json.loads(r['receipt']), status=('SUPERSEDED' if r['status'] == 'ACTIVE' and not r['current'] else r['status']),
                 current=r['current']) for r in rows]


def head(session, tenant, document_id):
    row = session.run('MATCH (d:ManualIngestionDocument {id:$id, tenant:$tenant}) RETURN d.head AS head',
                      id=document_key(tenant, document_id), tenant=tenant).single()
    return row['head'] if row else None
