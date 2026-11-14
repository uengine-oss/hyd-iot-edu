"""Registered sources and validated, human-reviewed ontology plans.

Registering a document only stores the source and reports how it was read. Sections and
procedures come from the agent extraction (manual_extraction) and nowhere else: a parser that
read numbered lines was removed 2026-11-13 because it only fit documents written in one layout
and showed a result and warnings before any extraction had run. Reviewed plans are checked here.
"""
from __future__ import annotations

import hashlib
import json
from uuid import uuid4, UUID

from . import kgadmin, manual_knowledge, manual_references


def document_key(tenant, document_id):
    """The graph identity of a reviewed document: `_manual_document` on its nodes and the ManualIngestionDocument id.
    The one place this key is made — previews, conflicts, commit and head lookups all ask the graph with it."""
    return hashlib.sha256(tenant.encode()).hexdigest() + ':' + document_id


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def registered(source):
    """등록한 원문 한 판의 요약 — 화면의 「문서 등록」 응답이자 시작 파일(scripts/class_knowledge.py)이 적재 요청에 쓰는 값.
    절 · 절차는 싣지 않는다(AI 추출 결과가 싣는다). warnings 는 원문을 읽으며 생긴 것(글자 없는 쪽 등)뿐이다."""
    return {'source_id': source['source_id'], 'document_id': source['document_id'],
            'filename': source['filename'], 'batch': str(uuid4()), 'previous_batch': None,
            'status': source['status'], 'chars': sum(len(p['text']) for p in source['pages']),
            'pages': len(source['pages']), 'warnings': list(source['warnings']),
            **({'text_missing_pages': list(source['text_missing_pages'])} if source.get('text_missing_pages') else {})}


def validate(archive, tenant, body):
    """Validate the entire proposal before opening any graph write transaction."""
    if body.get('reviewed') is not True or not isinstance(body.get('by'), str) or not body['by'].strip():
        raise ValueError('원문과 추출 내용을 검토한 담당자와 reviewed=true가 필요합니다')
    if body.get('review_method') is not None and body['review_method'] not in ('human-reviewed', 'user-delegated-ai-review'):
        raise ValueError('검토 수행 방식(review_method)이 지원 계약과 다릅니다')
    # 기본 제공 판의 판 표시: 시작할 때 서명 묶음의 검토본을 넣는 적재(scripts/class_knowledge.py)만 싣는다 — 그 적재가 「지금 묶음 판이 이미
    # 들어 있는가」를 담당자 칸의 자유 글이 아니라 이 칸으로 가린다(담당자 칸에 같은 글을 적은 판이 기본 제공 판으로 읽히던 것).
    revision = body.get('provided_revision')
    if revision is not None and (not isinstance(revision, str) or not 0 < len(revision) <= 80 or not body.get('review_method')):
        raise ValueError('기본 제공 판 표시(provided_revision)는 검토 수행 방식(review_method)과 함께 80자 이내 글로만 받습니다')
    source = archive.get(tenant, body.get('source_id'))
    if source['status'] != 'READY':      # P13: only a document with no text at all (manual_sources.status_of)
        raise ValueError('이 PDF는 모든 페이지에 텍스트가 없어 적재할 글이 없습니다 — 글자 인식(OCR)한 PDF로 다시 올리세요')
    try:
        batch = str(UUID(body['batch']))
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise ValueError('문서 등록 응답의 배치 UUID가 필요합니다') from exc
    sections, procedures = body.get('sections'), body.get('procedures')
    if not isinstance(sections, list) or not sections or not isinstance(procedures, list) or not procedures:
        raise ValueError('인용이 있는 절과 SOP가 각각 하나 이상 필요합니다')
    if len(sections) > 1000 or len(procedures) > 500:
        raise ValueError('한 번에 절1000개/SOP500개까지 검토할 수 있습니다. 내용을 절단하지 않았습니다')

    def anchor(value):
        return archive.anchor_in_source(source, value)

    checked_sections = {}
    for section in sections:
        if not isinstance(section, dict):
            raise ValueError('절은 필드가 있는 객체여야 합니다')
        ref = section.get('ref')
        if not isinstance(ref, str) or not ref.strip() or ref in checked_sections:
            raise ValueError('문서 안에서 절 식별자는 비어 있지 않고 유일해야 합니다')
        title = section.get('title')
        if not isinstance(title, str) or not title.strip():
            raise ValueError('절 제목이 필요합니다')
        if not isinstance(section.get('excerpt', ''), str):
            raise ValueError('절 본문은 문자열이어야 합니다')
        checked_sections[ref] = dict(ref=ref, title=title, excerpt=section.get('excerpt') or '',
                                     anchor=anchor(section.get('anchor')))
    checked_procedures, seen = [], set()
    sop_ids = {p.get('id') for p in procedures if isinstance(p, dict) and isinstance(p.get('id'), str)}
    links = body.get('links') or {}
    if not isinstance(links, dict):
        raise ValueError('고장 유형 연결은 SOP별 객체여야 합니다')
    for p in procedures:
        if not isinstance(p, dict):
            raise ValueError('SOP는 필드가 있는 객체여야 합니다')
        sop = p.get('id')
        if not isinstance(sop, str) or not kgadmin.SOP_ID_RE.fullmatch(sop) or sop in seen:
            raise ValueError('SOP ID 형식 또는 중복을 확인하세요')
        seen.add(sop)
        if p.get('section') not in checked_sections:
            raise ValueError(f'{sop}: 실제 문서 절을 지정하세요')
        steps = p.get('steps')
        if not isinstance(steps, list) or not 1 <= len(steps) <= 1000:
            raise ValueError(f'{sop}: 단계는1~1000개입니다. 내용을 절단하지 않았습니다')
        values = []
        for order, step in enumerate(steps, 1):
            if not isinstance(step, dict):
                raise ValueError('단계는 필드가 있는 객체여야 합니다')
            if type(step.get('order')) is not int or step['order'] != order:
                raise ValueError(f'{sop}: 단계 순서는1부터 연속이어야 합니다')
            if not isinstance(step.get('text'), str) or not step['text'].strip():
                raise ValueError(f'{sop}: 빈 단계를 저장할 수 없습니다')
            if step.get('manual') not in checked_sections:
                raise ValueError(f'{sop}: 단계의 원문 절이 없습니다')
            values.append(dict(order=order, text=step['text'], manual=step['manual'], anchor=anchor(step.get('anchor'))))
        link = links.get(sop) or {}
        if not isinstance(link, dict):
            raise ValueError('SOP 연결은 객체여야 합니다')
        link = manual_knowledge.blanks_as_absent(link)
        if link.get('kind') == 'reference':
            fields = manual_references.reference_shape(sop, link)
            binding = manual_references.binding_shape(p, link)
            if any(step['text'] not in step['anchor']['quote'] for step in values):
                raise ValueError(f'{sop}: 참고 단계 내용은 검증한 원문 인용에 그대로 있어야 합니다')
            checked_procedures.append(dict(id=sop, name=kgadmin.validate_skill(dict(name=p.get('name')))['name'],
                section=p['section'], anchor=anchor(p.get('anchor')), steps=values, affects=[],
                **fields, **binding))
            continue
        if p.get('existing_skill_id') or link.get('existing_skill_id') or p.get('reference_contract_sha256') or link.get('reference_contract_sha256'):
            raise ValueError(f'{sop}: 기존 Skill 재참조는 명시 reference 분기에서만 가능합니다')
        affects = kgadmin.validate_affects(link.get('affects'), sop)
        extra = manual_knowledge.validate_link(sop, {k: link.get(k) for k in ('actions', 'addresses')},
                                               sops=sop_ids, require_failure_mode=False)   # C1: CONSISTS_OF · ADDRESSES
        # validate_skill's legacy 30-step slice must never truncate source-backed SOPs.
        fields = kgadmin.validate_skill(dict(name=p.get('name'), sopId=sop,
                    steps=[s['text'] for s in values], failureMode=link.get('failureMode'),
                    relation=link.get('relation'), kind=link.get('kind'),
                    approver=link.get('approver'),
                    **{k: link.get(k) for k in ('scope', 'executable', 'parts', 'supplier_policy', 'maintenance_policy', 'purchase_comparison_policy', 'actions', 'addresses')}), create=True, source_backed=True)
        if fields.get('purchase_comparison_policy'):
            fields['purchase_comparison_policy']['anchor']=anchor(fields['purchase_comparison_policy']['anchor'])
        if fields.get('maintenance_policy'):
            policy=fields['maintenance_policy']
            policy['anchor']=anchor(policy['anchor'])
            policy['model_anchor']=anchor(policy['model_anchor'])
            if any(package['sop'] not in sop_ids for package in policy['packages']):
                raise ValueError('원문 정비 패키지의 실제 SOP가 같은 제안에 없습니다')
        checked_procedures.append(dict(id=sop, name=fields['name'], section=p['section'],
                 anchor=anchor(p.get('anchor')), steps=values, failureMode=fields['failureMode'],
                 relation=fields['relation'], kind=fields['kind'], approver=fields.get('approver'), affects=affects,
                 **{k: fields[k] for k in ('scope', 'executable', 'parts', 'supplier_policy', 'maintenance_policy', 'purchase_comparison_policy') if k in fields},
                 **{k: extra[k] for k in ('actions', 'addresses') if extra.get(k)}))
    from hydcommon.maintenance_policy import consistent_packages
    consistent_packages(checked_procedures)
    # C1: the reviewed knowledge part (고장 유형 · 원인 · 증거 · 규칙). Existence in the graph is checked at commit.
    knowledge = manual_knowledge.validate(body.get('knowledge'), sections=set(checked_sections), sops=sop_ids, anchor=anchor)
    return dict(batch=batch, tenant=tenant, document=document_key(tenant, source['document_id']),
                source_id=source['source_id'], document_id=source['document_id'],
                sha256=source['sha256'], filename=source['filename'], extractor=source['extractor'],
                previous_batch=body.get('previous_batch'), by=str(body['by']).strip(),
                method=str(body.get('method') or 'human-reviewed'),
                **({'review_method': body['review_method']} if body.get('review_method') else {}),
                **({'provided_revision': revision} if revision else {}),
                sections=list(checked_sections.values()), procedures=checked_procedures,
                **({'knowledge': knowledge} if knowledge and any(knowledge.values()) else {}))
