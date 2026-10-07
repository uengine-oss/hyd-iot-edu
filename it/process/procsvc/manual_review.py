"""Source-backed proposals and validated, human-reviewed ontology plans.

The structured parser is a convenience for explicitly numbered manuals, not an
LLM extractor. Both it and reviewed agent proposals use the same citation checks.
"""
from __future__ import annotations

import hashlib
import json
import re
from uuid import uuid4, UUID

from . import kgadmin

STEP_RE = re.compile(r'^\s*(\d+)[.)]\s+(.+?)\s*$')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def proposal(source, failure_modes=()):
    sections, procedures = [], []
    sec, proc = None, None
    warnings = list(source['warnings'])
    for page in source['pages']:
        offset = 0
        for raw in page['text'].splitlines(keepends=True):
            line = raw.rstrip('\r\n')
            anchor = dict(source_id=source['source_id'], page=page['page'],
                          start=offset, end=offset + len(line), quote=line)
            offset += len(raw)
            if not line.strip():
                continue
            sop = kgadmin.SOP_RE.match(line)
            heading = kgadmin.SECTION_RE.match(line)
            step = STEP_RE.match(line)
            if sop:
                if sec is None:
                    warnings.append(f'{sop[1]}: 먼저 원문 절을 지정해야 합니다')
                    proc = None
                    continue
                proc = {'id': sop[1], 'name': sop[2], 'section': sec['ref'],
                        'anchor': anchor, 'steps': []}
                procedures.append(proc)
            elif heading and not step:
                sec = {'ref': heading[1], 'title': heading[2], 'excerpt': '', 'anchor': anchor}
                sections.append(sec)
                proc = None
            elif step:
                if sec is None:
                    warnings.append('절 제목 없는 단계는 자동 적재하지 않습니다. 원문을 검토하세요')
                    continue
                if proc is None:
                    proc = {'id': 'SOP-' + sec['ref'].replace('.', '-'), 'name': sec['title'],
                            'section': sec['ref'], 'anchor': sec['anchor'], 'steps': []}
                    procedures.append(proc)
                if int(step[1]) != len(proc['steps']) + 1:
                    warnings.append(f"{proc['id']}: 원문 단계 번호 {step[1]}의 순서를 검토하세요")
                proc['steps'].append({'order': len(proc['steps']) + 1, 'text': step[2],
                                      'manual': sec['ref'], 'anchor': anchor})
            elif sec is not None:
                sec['excerpt'] += ('\n' if sec['excerpt'] else '') + line
    for p in procedures:
        p['stepCount'] = len(p['steps'])
        tokens = kgadmin._tokens(p['name'])
        scores = [(len(tokens & kgadmin._tokens(f['name'])), f['id']) for f in failure_modes]
        scores.sort(reverse=True)
        p['suggestedFailureMode'] = scores[0][1] if scores and scores[0][0] else None
    if not procedures:
        warnings.append('구조화된 SOP를 찾지 못했습니다. 일반 문서의 에이전트 추출은 별도 단계입니다')
    return {'source_id': source['source_id'], 'document_id': source['document_id'],
            'filename': source['filename'], 'batch': str(uuid4()), 'previous_batch': None,
            'method': 'structured-lines-v2', 'status': source['status'],
            'chars': sum(len(p['text']) for p in source['pages']),
            'sections': sections, 'procedures': procedures, 'warnings': warnings}


AFFECTS_MAX = 10
AFFECTS_LABELS = {'sv:': 'StateVariable', 'msr:': 'Measure'}
SIGNS = {'+': 1, '-': -1, 1: 1, -1: -1, '1': 1, '-1': -1}


def validate_affects(sop, value):
    """A079 (schema: Skill-[:AFFECTS {sign!}]->StateVariable|Measure). The reviewer says which variable or measure the
    SOP moves and in which direction; without it an ingested SOP never reaches the BSC and scores 0 on gains/losses.
    Target existence is checked at commit against the graph; only shape and sign are checked here."""
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > AFFECTS_MAX:
        raise ValueError(f'{sop}: 영향 연결은 최대 {AFFECTS_MAX}개의 목록입니다')
    out, seen = [], set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f'{sop}: 영향 연결은 객체여야 합니다')
        target = str(item.get('target') or '').strip()
        label = next((lab for prefix, lab in AFFECTS_LABELS.items() if target.startswith(prefix)), None)
        if not label or len(target) > 120 or target in seen:
            raise ValueError(f'{sop}: 영향 대상은 상태 변수(sv:…) 또는 성과 지표(msr:…) id이며 중복될 수 없습니다')
        sign = SIGNS.get(item.get('sign'))
        if sign is None:
            raise ValueError(f'{sop}: 영향 방향(sign)은 +/- 또는 1/-1 이어야 합니다')
        note = str(item.get('note') or '').strip()[:300]
        seen.add(target)
        out.append(dict(target=target, label=label, sign=sign, note=note))
    return out


def validate(archive, tenant, body):
    """Validate the entire proposal before opening any graph write transaction."""
    if body.get('reviewed') is not True or not isinstance(body.get('by'), str) or not body['by'].strip():
        raise ValueError('원문과 추출 내용을 검토한 담당자와 reviewed=true가 필요합니다')
    source = archive.get(tenant, body.get('source_id'))
    if source['status'] != 'READY':
        raise ValueError('텍스트가 없는 페이지를 먼저 검토/OCR해야 합니다. 부분 문서를 적재하지 않습니다')
    try:
        batch = str(UUID(body['batch']))
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise ValueError('미리보기의 배치 UUID가 필요합니다') from exc
    sections, procedures = body.get('sections'), body.get('procedures')
    if not isinstance(sections, list) or not sections or not isinstance(procedures, list) or not procedures:
        raise ValueError('인용이 있는 절과 SOP가 각각 하나 이상 필요합니다')
    if len(sections) > 1000 or len(procedures) > 500:
        raise ValueError('한 번에 절1000개/SOP500개까지 검토할 수 있습니다. 내용을 절단하지 않았습니다')

    def anchor(value):
        checked = archive.validate_anchor(tenant, value)
        if checked['source_id'] != source['source_id']:
            raise ValueError('다른 문서 판본의 인용을 섞을 수 없습니다')
        return checked

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
        affects = validate_affects(sop, link.get('affects'))
        # validate_skill's legacy 30-step slice must never truncate source-backed SOPs.
        fields = kgadmin.validate_skill(dict(name=p.get('name'), sopId=sop,
                    steps=[s['text'] for s in values], failureMode=link.get('failureMode'),
                    relation=link.get('relation'), kind=link.get('kind'),
                    approver=link.get('approver') or 'role:maint-mgr'), create=True)
        checked_procedures.append(dict(id=sop, name=fields['name'], section=p['section'],
                 anchor=anchor(p.get('anchor')), steps=values, failureMode=fields['failureMode'],
                 relation=fields['relation'], kind=fields['kind'], approver=fields['approver'], affects=affects))
    tenant_key = hashlib.sha256(tenant.encode()).hexdigest()
    return dict(batch=batch, tenant=tenant, document=tenant_key + ':' + source['document_id'],
                source_id=source['source_id'], document_id=source['document_id'],
                sha256=source['sha256'], filename=source['filename'], extractor=source['extractor'],
                previous_batch=body.get('previous_batch'), by=str(body['by']).strip(),
                method=str(body.get('method') or 'human-reviewed'),
                sections=list(checked_sections.values()), procedures=checked_procedures)
