"""Atomic, source-owned SOP graph replacement with checked, latest-first undo.

Originals and extraction coordinates live in ManualSources. Graph batches retain
the reviewed before/after snapshots. A referenced or externally edited graph is
never silently replaced; its owner must reconcile that conflict first.

Ownership (C1): which nodes a document owns is the document's journal (ManualIngestionDocument.snapshot = the reviewed
after-state of its head batch). The original four labels (KnowledgeSource · ManualSection · Skill · Step) and their edges
still carry `_manual_document` because schema v2 declares it there and other readers use it (admin skill edit, AFFECTS).
The knowledge labels added by C1 (FailureMode · Cause · Evidence · Rule) and their relationships carry no extra property —
schema v2 stays unchanged — and are owned through the journal only. The snapshot of a document is every owned node and
every relationship touching one, so a foreign reference to an owned node is still detected as drift.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from .manual_review import canonical
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


def _snapshot(tx, document, owned=()):
    """The current graph state of what the document owns: its journal-owned nodes (plus any node still tagged with the
    document, so a tagged node missing from the journal shows up as drift) and every relationship touching one of them."""
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
    edges = tx.run('MATCH (a)-[r]->(b) WHERE elementId(a) IN $e OR elementId(b) IN $e '
                   'RETURN labels(a) AS from_labels, a.id AS from_id, labels(b) AS to_labels, b.id AS to_id, '
                   'type(r) AS type, properties(r) AS props', e=list(rows)).data() if rows else []
    for edge in edges:
        edge['from_labels'].sort()
        edge['to_labels'].sort()
    return _sort({'nodes': nodes, 'edges': edges})


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


def _replace(tx, current, target):
    # Caller verified the current graph equals the journal, so every relationship touching an owned node is the
    # document's own; each is removed by its identity. No DETACH DELETE is used: an unexpected foreign reference
    # makes the node delete fail and the whole transaction roll back.
    for edge in current['edges']:
        a, b = ':'.join(edge['from_labels']), ':'.join(edge['to_labels'])
        if edge['type'] not in RELATIONS:
            raise Conflict('보관된 관계 유형이 지원 계약과 다릅니다')
        row = tx.run(f"MATCH (a:{a} {{id:$a}})-[r:{edge['type']}]->(b:{b} {{id:$b}}) WHERE properties(r) = $props "
                     'WITH r LIMIT 1 DELETE r RETURN count(*) AS n', a=edge['from_id'], b=edge['to_id'], props=edge['props']).single()
        if row['n'] != 1:
            raise Conflict('지울 관계가 기록과 달라 전체 적재를 취소했습니다')
    for node in current['nodes']:
        label = node['labels'][0]
        if label not in LABELS or len(node['labels']) != 1:
            raise Conflict('보관된 노드 유형이 지원 계약과 다릅니다')
        tx.run(f'MATCH (n:{label} {{id:$id}}) DELETE n', id=node['props']['id']).consume()
    for node in target['nodes']:
        label = node['labels'][0]
        if label not in LABELS or len(node['labels']) != 1:
            raise Conflict('보관된 노드 유형이 지원 계약과 다릅니다')
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
        before = _snapshot(tx, plan['document'], owned_keys(expected))
        if before != _sort(expected):
            raise Conflict('적재 뒤 속성/규칙/실행 등의 참조가 바뀌었습니다. 변경 내용을 먼저 조정하세요')
        _validate_targets(tx, after, owned_keys(before))
        _replace(tx, before, after)
        receipt = _receipt(plan, at)
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
        current = _snapshot(tx, document, owned_keys(after))
        if current != _sort(after):
            raise Conflict('외부 속성/규칙/실행 참조가 있어 되돌릴 수 없습니다. 먼저 변경을 검토하세요')
        before = json.loads(record['before'])
        _validate_targets(tx, before, owned_keys(current))
        _replace(tx, current, before)
        tx.run('MATCH (d:ManualIngestionDocument {id:$id}) SET d.head=$head, d.snapshot=$snapshot',
               id=document, head=record.get('previous'), snapshot=record['before']).consume()
        tx.run('MATCH (b:ManualIngestionBatch {id:$id}) SET b.status="ROLLED_BACK", b.rolledBackBy=$by, b.rolledBackAt=$at',
               id=batch, by=by.strip(), at=datetime.now(timezone.utc).isoformat()).consume()
        return dict(batch=batch, status='ROLLED_BACK', replayed=False, restored_batch=record.get('previous'))
    return session.execute_write(run)


def history(session, tenant):
    rows = session.run('MATCH (b:ManualIngestionBatch {tenant:$tenant}) '
                       'OPTIONAL MATCH (d:ManualIngestionDocument {id:b.document}) '
                       'RETURN b.receipt AS receipt, b.status AS status, d.head=b.id AS current '
                       'ORDER BY b.createdAt DESC', tenant=tenant).data()
    return [dict(json.loads(r['receipt']), status=('SUPERSEDED' if r['status'] == 'ACTIVE' and not r['current'] else r['status']),
                 current=r['current']) for r in rows]


def head(session, tenant, document_id):
    key = hashlib.sha256(tenant.encode()).hexdigest() + ':' + document_id
    row = session.run('MATCH (d:ManualIngestionDocument {id:$id, tenant:$tenant}) RETURN d.head AS head',
                      id=key, tenant=tenant).single()
    return row['head'] if row else None
