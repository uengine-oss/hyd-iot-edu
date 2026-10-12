"""Source-only procedures and exact, read-only references to existing Skills.

DOCUMENTS is provenance, never an active HAS_STEP or execution permission.
Pins cover the existing execution contract; foreign provenance is accepted only
when its active journal, owned source nodes and source anchors still agree.
"""
from __future__ import annotations

import hashlib
import json
import re

CONTRACT_Q = '''MATCH (k:Skill) WHERE $ids IS NULL OR k.id IN $ids
RETURN properties(k) AS skill,
 COLLECT { MATCH (k)-[r:APPROVED_BY|CONSISTS_OF|ADDRESSES|AFFECTS]->(n)
           RETURN {type:type(r),props:properties(r),labels:labels(n),node:properties(n),
             targets:COLLECT { MATCH (n)-[t:TARGETS]->(a) RETURN {type:type(t),props:properties(t),labels:labels(a),node:properties(a)} }} } AS outgoing,
 COLLECT { MATCH (n)-[r:MITIGATED_BY|REMEDIED_BY|PREVENTED_BY|HAS_SKILL|OUTPUTS]->(k)
           RETURN {type:type(r),props:properties(r),labels:labels(n),node:properties(n)} } AS incoming,
 COLLECT { MATCH (k)-[h:HAS_STEP]->(st:Step)
           RETURN {edge:properties(h),step:properties(st),
              manuals:COLLECT { MATCH (st)-[r:REFERS_TO]->(ms:ManualSection)
                RETURN {edge:properties(r),section:properties(ms)} }} ORDER BY st.order,st.id } AS steps
ORDER BY k.id'''


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _ordered(value):
    if isinstance(value, dict):
        return {key: _ordered(item) for key, item in value.items()}
    if isinstance(value, list):
        return sorted((_ordered(item) for item in value), key=canonical)
    return value


def contracts(tx, ids=None):
    if ids is not None and not ids:
        return {}
    out = {}
    for row in tx.run(CONTRACT_Q, ids=list(ids) if ids is not None else None).data():
        contract = _ordered(row)
        skill = row['skill']
        sections = {canonical(item['section']): item['section'] for step in row['steps'] for item in step.get('manuals') or []}
        out[skill['id']] = dict(id=skill['id'], sopId=skill.get('sopId'), owner=skill.get('_manual_document'),
            contract_sha256=digest(contract),
            steps=sorted([dict(order=item['step'].get('order'), text=item['step'].get('text')) for item in row['steps']], key=lambda s: s['order'] or 0),
            sections=[{key: section[key] for key in ('id', 'ref', 'title', 'excerpt', 'source_id', 'citation') if key in section}
                      for _, section in sorted(sections.items())],
            contract=contract)
    return out


def reference_shape(sop, link):
    if link.get('kind') != 'reference' or link.get('executable') is not False:
        raise ValueError(f'{sop}: 참고 절차는 명시 kind=reference, executable=false여야 합니다')
    forbidden = ('failureMode', 'relation', 'approver', 'actions', 'addresses', 'affects', 'parts', 'supplier_policy', 'purchase_comparison_policy')
    if any(link.get(key) not in (None, [], {}) for key in forbidden) or link.get('scope') not in (None, 'fault'):
        raise ValueError(f'{sop}: 참고 절차는 FM·승인·Action·업무 실행 연결을 갖지 않습니다. 원문 제안은 검토 기록에 보존하세요')
    return dict(kind='reference', executable=False, failureMode=None, relation=None, approver=None)


def binding_shape(procedure, link):
    target = procedure.get('existing_skill_id') or link.get('existing_skill_id')
    pin = procedure.get('reference_contract_sha256') or link.get('reference_contract_sha256')
    if not target and pin is None:
        return {}
    if link.get('kind') != 'reference':
        raise ValueError(f"{procedure['id']}: 기존 Skill은 reference로만 재참조하며 소유권/실행 계약을 인수하지 않습니다")
    if not isinstance(target, str) or not re.fullmatch(r'skill:[a-z0-9][a-z0-9:_.-]*', target):
        raise ValueError(f"{procedure['id']}: 실제 existing_skill_id가 필요합니다")
    if not isinstance(pin, str) or not re.fullmatch(r'[0-9a-f]{64}', pin):
        raise ValueError(f"{procedure['id']}: 검토한 대상의 reference_contract_sha256이 필요합니다")
    return dict(existing_skill_id=target, reference_contract_sha256=pin)


def check_binding(procedure, target, *, require_pin=True):
    sop, sid = procedure['id'], procedure['existing_skill_id']
    if not target or target['id'] != sid:
        raise ValueError(f'{sop}: 참조할 Skill {sid}가 없습니다')
    if target['sopId'] != sop:
        raise ValueError(f'{sop}: 기존 Skill의 SOP 번호와 다릅니다. 번호 alias나 새 ID로 우회하지 않습니다')
    source = [dict(order=step['order'], text=step['text']) for step in procedure['steps']]
    if target['steps'] != source:
        raise ValueError(f'{sop}: 기존 active 단계의 순서·내용과 원문 전체 단계가 정확히 같지 않습니다')
    if require_pin and target['contract_sha256'] != procedure.get('reference_contract_sha256'):
        raise ValueError(f'{sop}: 검토 뒤 기존 Skill의 실행 계약이 바뀌었습니다. 다시 조회·검토하세요')
    return dict(skill=sid, sopId=sop, contract_sha256=target['contract_sha256'], owner=target['owner'],
                source_steps_sha256=digest(source))


def check_plan(tx, plan):
    bound = [p for p in plan['procedures'] if p.get('existing_skill_id')]
    if not bound:
        return {}
    targets = contracts(tx, [p['existing_skill_id'] for p in bound])
    result = {}
    for p in bound:
        target = targets.get(p['existing_skill_id'])
        if target and target.get('owner'):
            if target['owner'] == plan['document']:
                raise ValueError(f"{p['id']}: 같은 문서가 소유한 Skill은 기존 소유 개정 경로로 보존하세요. 외부 재참조로 바꾸지 않습니다")
            owner = tx.run('MATCH (d:ManualIngestionDocument {id:$id}) RETURN d.tenant AS tenant', id=target['owner']).data()
            if len(owner) != 1 or owner[0]['tenant'] != plan['tenant']:
                raise ValueError(f"{p['id']}: 같은 tenant의 검증된 원문 소유 대상이 아닙니다")
        result[p['id']] = check_binding(p, target)
    return result


def provenance(tx, edge):
    """Return a verified dependency, or None (ordinary foreign drift).

    The journal is the already source-validated commit record. Revalidate exact
    graph Step/Section/edge against it and its canonical plan fingerprint; never
    trust a relationship's _manual_document tag on its own.
    """
    if edge.get('type') != 'DOCUMENTS' or edge.get('from_labels') != ['Step'] or edge.get('to_labels') != ['Skill']:
        return None
    document = edge.get('props', {}).get('_manual_document')
    if not document:
        return None
    rows = tx.run('MATCH (d:ManualIngestionDocument {id:$id}) MATCH (b:ManualIngestionBatch {id:d.head}) '
                  'RETURN properties(d) AS d,properties(b) AS b', id=document).data()
    if len(rows) != 1:
        return None
    try:
        d, batch = rows[0]['d'], rows[0]['b']
        plan, after = json.loads(batch['plan']), json.loads(batch['after'])
        if (batch['status'] != 'ACTIVE' or batch['document'] != document or d['snapshot'] != batch['after']
                or plan['document'] != document or plan['tenant'] != d['tenant'] or batch['tenant'] != d['tenant']
                or batch['fingerprint'] != digest(plan) or edge not in after['edges']):
            return None
        nodes = {(n['labels'][0], n['props']['id']): n['props'] for n in after['nodes']}
        step = nodes.get(('Step', edge['from_id']))
        if not step or step.get('_manual_document') != document or step.get('source_id') != plan['source_id']:
            return None
        actual = tx.run('MATCH (st:Step {id:$id}) RETURN properties(st) AS p', id=edge['from_id']).data()
        if len(actual) != 1 or actual[0]['p'] != step:
            return None
        actual_documents = tx.run('MATCH (:Step {id:$id})-[r:DOCUMENTS]->(k:Skill) RETURN k.id AS id,properties(r) AS p',
                                   id=edge['from_id']).data()
        if len(actual_documents) != 1 or actual_documents[0]['id'] != edge['to_id'] or actual_documents[0]['p'] != edge['props']:
            return None
        refs = [e for e in after['edges'] if e['from_id'] == edge['from_id'] and e['type'] == 'REFERS_TO']
        if len(refs) != 1:
            return None
        ref = refs[0]
        section = nodes.get(('ManualSection', ref['to_id']))
        source_edges = [e for e in after['edges'] if e['from_id'] == ref['to_id'] and e['type'] == 'PART_OF']
        if len(source_edges) != 1:
            return None
        source = nodes.get(('KnowledgeSource', source_edges[0]['to_id']))
        if (not section or section.get('source_id') != plan['source_id'] or not source
                or source.get('sha256') != plan['sha256'] or source.get('source_id') != plan['source_id']):
            return None
        actual_source = tx.run('MATCH (s:KnowledgeSource {id:$id}) RETURN properties(s) AS p', id=source['id']).data()
        actual_part = tx.run('MATCH (:ManualSection {id:$a})-[r:PART_OF]->(:KnowledgeSource {id:$b}) RETURN properties(r) AS p',
                            a=section['id'], b=source['id']).data()
        if (len(actual_source) != 1 or actual_source[0]['p'] != source or len(actual_part) != 1
                or actual_part[0]['p'] != source_edges[0]['props']):
            return None
        actual_section = tx.run('MATCH (s:ManualSection {id:$id}) RETURN properties(s) AS p', id=ref['to_id']).data()
        if len(actual_section) != 1 or actual_section[0]['p'] != section:
            return None
        actual_ref = tx.run('MATCH (:Step {id:$id})-[r:REFERS_TO]->(s:ManualSection) RETURN s.id AS id,properties(r) AS p',
                            id=edge['from_id']).data()
        if len(actual_ref) != 1 or actual_ref[0]['id'] != ref['to_id'] or actual_ref[0]['p'] != ref['props']:
            return None
        active = tx.run('MATCH (:Skill)-[:HAS_STEP]->(:Step {id:$id}) RETURN count(*) AS n', id=edge['from_id']).single()
        if active['n']:
            return None
        candidates = [p for p in plan['procedures'] if p.get('existing_skill_id') == edge['to_id']
                      and any(canonical(s['anchor']) == step['citation'] and s['text'] == step['text'] and s['order'] == step['order'] for s in p['steps'])]
        if len(candidates) != 1:
            return None
        procedure = candidates[0]
        if json.loads(step['citation'])['source_id'] != plan['source_id']:
            return None
        target = contracts(tx, [edge['to_id']]).get(edge['to_id'])
        if target and target.get('owner'):
            owner = tx.run('MATCH (d:ManualIngestionDocument {id:$id}) RETURN d.tenant AS tenant', id=target['owner']).data()
            if len(owner) != 1 or owner[0]['tenant'] != plan['tenant']:
                return None
        checked = check_binding(procedure, target)
        return dict(document=document, tenant=plan['tenant'], step=edge['from_id'], **checked)
    except (KeyError, TypeError, ValueError):
        return None


def incoming_dependencies(tx, skill_ids):
    if not skill_ids:
        return []
    rows = tx.run('MATCH (a:Step)-[r:DOCUMENTS]->(b:Skill) WHERE b.id IN $ids '
                  'RETURN labels(a) AS from_labels,a.id AS from_id,labels(b) AS to_labels,b.id AS to_id, '
                  'type(r) AS type,properties(r) AS props', ids=list(skill_ids)).data()
    return [dict(edge=row, verified=provenance(tx, row)) for row in rows]
