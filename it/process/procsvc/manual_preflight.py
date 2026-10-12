"""Read-only machine checks. Neither human review nor permission to commit."""
from copy import deepcopy

from . import kgadmin, manual_knowledge, manual_review


def validate(proposal, catalog):
    """Use a successfully read current catalog; never invent reviewed/by or modify proposals."""
    original = deepcopy(proposal)
    issues = []

    def issue(code, owner, field, message):
        issues.append(dict(code=code, sop=owner, field=field, message=message))

    procedures = original.get('procedures') or []
    if not procedures:
        issue('NO_PROCEDURES', None, 'procedures', '아직 적재할 절차가 없습니다. 원문과 추출 제안을 검토하세요')
    sops = {p['id'] for p in procedures}
    sections = {s['ref'] for s in original.get('sections') or []}
    plan = dict(procedures=[], knowledge={})
    overrides = original.get('links')
    if overrides is None:
        overrides = {}
    elif not isinstance(overrides, dict):
        issue('LINKS_INVALID', None, 'links', '검토 연결은 SOP별 객체여야 합니다')
        overrides = {}
    for p in procedures:
        sop = p['id']
        # Extraction previews keep suggested links on each procedure. A review
        # can explicitly override a SOP, including {} to clear the suggestion.
        # Only an absent override key falls back to the original procedure link.
        link = overrides[sop] if sop in overrides else p.get('link')
        if link is None:
            link = {}
        try:
            normalized = manual_knowledge.validate_link(sop, link, sops=sops, require_failure_mode=False)
            normalized['affects'] = manual_review.validate_affects(sop, link.get('affects'))
        except ValueError as exc:
            issue('LINK_INVALID', sop, 'link', str(exc))
            continue
        entry = dict(p, **normalized)
        # Same existing kind default as commit. No default FM or fabricated review.
        entry['kind'] = entry.get('kind') or 'work_order'
        plan['procedures'].append(entry)
        try:
            kgadmin.validate_skill(dict(name=p.get('name'), sopId=sop,
                steps=[s['text'] for s in p.get('steps') or []], failureMode=link.get('failureMode'),
                relation=link.get('relation'), kind=link.get('kind'), approver=link.get('approver')), create=True)
        except ValueError as exc:
            issue('FAILURE_MODE_REQUIRED' if not link.get('failureMode') else 'SKILL_MODEL_INVALID',
                  sop, 'link.failureMode' if not link.get('failureMode') else 'link', f'{sop}: {exc}')
    try:
        plan['knowledge'] = manual_knowledge.validate(original.get('knowledge'), sections=sections,
                                                      sops=sops, anchor=lambda a: deepcopy(a))
    except ValueError as exc:
        issue('KNOWLEDGE_INVALID', None, 'knowledge', str(exc))
    _, semantic = manual_knowledge.graph_semantics(plan, catalog)
    issues.extend(semantic)

    available = {key: {r['id'] for r in catalog[key]} for key in (
        'components', 'symptoms', 'patterns', 'parts', 'suppliers', 'state_variables',
        'measures', 'roles', 'failure_modes', 'causes', 'skills')}
    k = plan.get('knowledge') or {}
    for key in ('failure_modes', 'causes'):
        available[key].update(r['id'] for r in k.get(key) or [])
    available['skills'].update(kgadmin.skill_id(sop) for sop in sops)
    existing_sops = {r.get('sopId') for r in catalog['skills']} | sops

    def ref(owner, field, value, group):
        if value is not None and value not in available[group]:
            issue('REFERENCE_NOT_FOUND', owner, field, f'{owner}: {field}의 {value} 참조가 현재 지식에 없습니다')

    for p in plan['procedures']:
        sop = p['id']
        ref(sop, 'link.failureMode', p.get('failureMode'), 'failure_modes')
        # Commit retains its historic fallback. Check that target without claiming
        # the original proposed it or inserting a reviewer/approver into the response.
        ref(sop, 'link.approver', p.get('approver') or 'role:maint-mgr', 'roles')
        for cause in p.get('addresses') or []:
            ref(sop, 'link.addresses', cause, 'causes')
        for a in p.get('affects') or []:
            target = a.get('target')
            ref(sop, 'link.affects', target, 'measures' if str(target).startswith('msr:') else 'state_variables')
    for f in k.get('failure_modes') or []:
        ref(f['id'], 'component', f['component'], 'components')
        for v in f['symptoms']:
            ref(f['id'], 'symptoms', v, 'symptoms')
        for v in f['leads_to']:
            ref(f['id'], 'leads_to', v, 'failure_modes')
    for c in k.get('causes') or []:
        ref(c['id'], 'failure_mode', c['failure_mode'], 'failure_modes')
        for v in c['parts']:
            ref(c['id'], 'parts', v, 'parts')
        for d in c['disturbs']:
            ref(c['id'], 'disturbs', d['target'], 'state_variables')
    for e in k.get('evidence') or []:
        ref(e['id'], 'cause', e['cause'], 'causes')
    for r in k.get('rules') or []:
        for field in ('outputs', 'applies_to'):
            for v in r[field]:
                if v.startswith('SOP-'):
                    if v not in existing_sops:
                        issue('SOP_NOT_FOUND', r['id'], field, f"{r['id']}: {v} SOP 참조가 현재 지식에 없습니다")
                else:
                    ref(r['id'], field, v, 'causes' if v.startswith('cause:') else 'skills')
        ref(r['id'], 'penalizes', r['penalizes'], 'measures')
    for conflict in original.get('conflicts') or []:
        issue('SOP_OWNERSHIP_CONFLICT', conflict.get('sop'), 'conflicts',
              f"{conflict.get('sop')}: 기존 원천이 소유한 SOP입니다. 덮어쓰지 않고 개정 여부를 검토하세요")
    for conflict in original.get('knowledge_conflicts') or []:
        issue('KNOWLEDGE_OWNERSHIP_CONFLICT', conflict.get('id'), 'knowledge_conflicts',
              f"{conflict.get('id')}: 기존 지식의 소유권 충돌입니다. 원문과 기존 지식을 대조하세요")
    return dict(checked=True, technical_ready=not issues, needs_human_review=True, can_commit=False, issues=issues)
