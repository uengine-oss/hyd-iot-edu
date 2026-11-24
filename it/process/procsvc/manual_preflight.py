"""Read-only machine checks. Neither human review nor permission to commit."""
from hydcommon.words import josa, particle
from copy import deepcopy

from hydcommon.maintenance_policy import PM_PATTERN

from . import kgadmin, manual_knowledge, manual_references


# 검사 문장의 칸 이름(학생 화면 말) — 검토 화면의 칸 이름과 같다
FIELD_LABELS = {'link.failureMode': '고장 유형', 'link.approver': '승인 역할', 'link.parts': '구매 부품', 'link.addresses': '대상 원인',
                'link.affects': '영향 대상', 'component': '구성 요소', 'symptoms': '증상', 'leads_to': '이어지는 고장 유형',
                'failure_mode': '고장 유형', 'parts': '부품', 'disturbs': '흔드는 상태 변수', 'cause': '원인', 'outputs': '규칙 결과',
                'applies_to': '규칙 적용 대상', 'penalizes': '감점 지표', 'sensors': '관측 센서', 'tag': '태그'}

#: 없는 것을 가리켰을 때 할 일 — 문서가 새로 만들 수 있는 것(고장 유형 · 원인 · 절차), 문서가 새 항목으로 제안하고 사람이 넣기를 고르는 것(그 설비의
#: 구성 요소 · 증상 · 센서 — manual_knowledge.NEW_KINDS), 지금 지식에 있는 것에서만 고를 수 있는 것(경보 패턴 · 부품 · 공급사 · 상태 변수 · 성과 지표 —
#: 문서 적재는 이것들을 새로 만들지 않는다), 포털에서 만들 수 있는 것(승인 역할)을 갈라 말한다. 다른 분야의 문서가 여기서 막히면 「지금 지식에 없습니다」만으로는
#: 문서를 고칠지 지식을 고칠지 알 수 없다(전수검사 10-G7).
#: 검토 화면에서 고칠 수 있는 칸은 절차의 영향 · 구매 부품 · 승인 역할뿐이고, 지식 후보(고장 유형 · 원인 · 증거 · 규칙)는 [적재에서 제외]만 할 수 있다 — 「고르세요」라고 하면
#: 고를 칸이 없는 학생이 길을 잃는다(C13). 그래서 고칠 칸이 있는 곳과 없는 곳의 길을 함께 말한다.
_PICK = ('문서 적재는 {what_을} 새로 만들지 않아, 지금 지식에 없는 {what_을} 가리킨 이 항목은 이대로 적재할 수 없습니다 — 절차의 영향 · 구매 부품 칸이면 '
         '지금 지식에 있는 {what_으로} 고치고, 지식 후보(고장 유형 · 원인 · 증거 · 규칙)면 그 항목을 적재에서 제외하세요')
_pick = lambda what: _PICK.format(what=what, what_을=josa(what, '을'), what_으로=josa(what, '으로'))
#: 새 항목으로 제안할 수 있는 것인데 제안되지 않은 것 — 검토 화면은 새 항목을 만들지 않으므로(넣기 · 제외만 고른다) AI 추출이 제안해야 한다
_PROPOSE = '이 문서의 새 항목 제안에도 없습니다 — 새 {what}{p} AI 추출이 원문 인용과 함께 제안한 것만 넣을 수 있으니, 이 항목을 적재에서 제외하세요'
_propose = lambda what: _PROPOSE.format(what=what, p=particle(what, '은'))
ROLE_HELP = '역할 목록에 있는 승인 역할을 고르세요. 맞는 역할이 없으면 「AI 에이전트」 화면의 담당 배정에서 [역할 만들기]로 먼저 만든 뒤 다시 검사하세요'
REFERENCE_HELP = {
    'components': _propose('구성 요소'), 'symptoms': _propose('증상'), 'sensors': _propose('센서'),
    'patterns': _pick('경보 패턴'), 'parts': _pick('부품'), 'suppliers': _pick('공급사'),
    'state_variables': _pick('상태 변수'), 'measures': _pick('성과 지표'),
    # 승인 역할만은 포털에서 만들 수 있다(역할의 정본은 업무 DB — agent_authoring.project_roles 가 지식 그래프로 옮긴다)
    'roles': ROLE_HELP,
    'failure_modes': '이 문서의 고장 유형 목록에 넣거나 지금 지식에 있는 고장 유형을 고르세요',
    'causes': '이 문서의 원인 목록에 넣거나 지금 지식에 있는 원인을 고르세요',
    'skills': '이 문서의 절차(SOP)이거나 지금 지식에 있는 조치 방법이어야 합니다',
}


def validate(proposal, catalog):
    """Use a successfully read current catalog; never invent reviewed/by or modify proposals."""
    original = deepcopy(proposal)
    issues = []
    notices = []      # 고칠 곳이 아니라 사람이 알고 넘어갈 것(검토 필요 수에 세지 않는다)

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
        if isinstance(link, dict):
            link = manual_knowledge.blanks_as_absent(link)
        try:
            normalized = manual_knowledge.validate_link(sop, link, sops=sops, require_failure_mode=False)
            normalized['affects'] = kgadmin.validate_affects(link.get('affects'), sop)
        except ValueError as exc:
            issue('LINK_INVALID', sop, 'link', str(exc))
            continue
        entry = dict(p, **normalized)
        # Same existing kind default as commit. No default FM or fabricated review.
        entry['kind'] = entry.get('kind') or 'work_order'
        plan['procedures'].append(entry)
        if entry['kind'] == 'reference':
            try:
                entry.update(manual_references.binding_shape(p, link))
                if entry.get('existing_skill_id'):
                    target = next((s.get('reference_contract') for s in catalog['skills'] if s['id'] == entry['existing_skill_id']), None)
                    manual_references.check_binding(entry, target)
            except ValueError as exc:
                issue('REFERENCE_BINDING_INVALID', sop, 'existing_skill_id', str(exc))
            continue
        try:
            kgadmin.validate_skill(dict(name=p.get('name'), sopId=sop,
                steps=[s['text'] for s in p.get('steps') or []], failureMode=link.get('failureMode'),
                relation=link.get('relation'), kind=link.get('kind'), approver=link.get('approver'),
                **{key: link.get(key) for key in ('scope', 'executable', 'parts', 'supplier_policy', 'maintenance_policy', 'purchase_comparison_policy', 'actions', 'addresses')}),
                create=True, source_backed=True)
        except ValueError as exc:
            missing_fm = not link.get('failureMode') and link.get('scope') != 'purchase'
            issue('FAILURE_MODE_REQUIRED' if missing_fm else 'SKILL_MODEL_INVALID',
                  sop, 'link.failureMode' if missing_fm else 'link', f'{sop}: {exc}')
    try:
        plan['knowledge'] = manual_knowledge.validate(original.get('knowledge'), sections=sections,
                                                      sops=sops, anchor=lambda a: deepcopy(a))
    except ValueError as exc:
        issue('KNOWLEDGE_INVALID', None, 'knowledge', str(exc))
    plan, semantic = manual_knowledge.graph_semantics(plan, catalog)
    issues.extend(semantic)

    available = {key: {r['id'] for r in catalog[key]} for key in (
        'components', 'symptoms', 'patterns', 'parts', 'suppliers', 'state_variables',
        'measures', 'roles', 'failure_modes', 'causes', 'skills')}
    # 센서 목록이 없는 옛 카탈로그(그 칸이 생기기 전에 추출 작업에 고정한 것)는 아래 설비 구조 판정이 CATALOG_OUTDATED 로 말한다 — 그때의 제안은 센서를 가리킬 수 없었다
    available['sensors'] = {r['id'] for r in catalog['sensors']} if 'sensors' in catalog else set()
    k = plan.get('knowledge') or {}
    for key in ('failure_modes', 'causes', *manual_knowledge.NEW_KINDS):      # 이 문서가 만드는 지식 · 새 항목 제안(넣기를 고르면 적재된다)
        available[key].update(r['id'] for r in k.get(key) or [])
    available['skills'].update(kgadmin.skill_id(sop) for sop in sops)
    existing_sops = {r.get('sopId') for r in catalog['skills']} | sops

    def ref(owner, field, value, group):
        if value is not None and value not in available[group]:
            issue('REFERENCE_NOT_FOUND', owner, field, f'{owner}: {FIELD_LABELS.get(field, field)} 칸에 적은 {value}{particle(value, "이")} 지금 지식에 없습니다 — '
                  + REFERENCE_HELP[group])

    for p in plan['procedures']:
        sop = p['id']
        ref(sop, 'link.failureMode', p.get('failureMode'), 'failure_modes')
        # Missing source approval stays unknown; no maintenance-role inference.
        ref(sop, 'link.approver', p.get('approver'), 'roles')
        for part in p.get('parts') or []:
            ref(sop, 'link.parts', part, 'parts')
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
    for s in k.get('sensors') or []:
        ref(s['id'], 'component', s['component'], 'components')
    for s in k.get('symptoms') or []:
        for v in s['sensors']:
            ref(s['id'], 'sensors', v, 'sensors')
    if 'failure_modes' in k:      # 지식의 꼴 검사를 지났을 때만(지나지 못했으면 KNOWLEDGE_INVALID 가 이미 있다)
        structure, structure_notices = manual_knowledge.new_item_issues(k, catalog, plan['procedures'])
        issues.extend(structure)
        notices.extend(structure_notices)
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
        referenced = next((p for p in plan['procedures'] if p['id'] == conflict.get('sop') and p.get('kind') == 'reference'
                           and p.get('existing_skill_id') == conflict.get('skill')), None)
        if referenced and not any(i.get('sop') == referenced['id'] for i in issues):
            continue
        issue('SOP_OWNERSHIP_CONFLICT', conflict.get('sop'), 'conflicts',
              f"{conflict.get('sop')}: " + ('이미 적재된 다른 문서가 가진 SOP 번호라 새 문서로는 적재하지 않습니다(덮어쓰지 않습니다). '
                                            '그 문서를 다시 올린 것이면 문서 올리기의 「등록할 문서」 칸에서 「새 문서 등록」 대신 그 문서(… · 문서 개정)를 고르고 '
                                            '다시 올리세요 — 개정으로 올라갑니다. 다른 문서라면 원문의 SOP 번호가 겹치지 않아야 합니다'
                                            if conflict.get('kind') == 'other_document' else
                                            '기본 제공 지식 · 조치 방법 화면에서 만든 조치 방법이 가진 SOP 번호라 문서로는 적재하지 않습니다(덮어쓰지 '
                                            '않습니다). 원문의 SOP 번호가 겹치지 않아야 합니다'))
    for conflict in original.get('knowledge_conflicts') or []:
        # Extraction metadata describes the original definitions. An explicit
        # reviewed knowledge body may remove a definition and retain its ID as
        # a reference. Do not keep a stale ownership issue for an unowned node;
        # missing/invalid knowledge still retains the unresolved warning.
        if 'knowledge' in original and not any(i['code'] == 'KNOWLEDGE_INVALID' for i in issues):
            defined_ids = {item['id'] for items in k.values() for item in items}
            if conflict.get('id') not in defined_ids:
                continue
        # 무엇이 이미 있고 누가 가졌는지, 그래서 무엇을 하면 되는지를 말한다(전에는 「기존 지식의 소유권 충돌입니다. 원문과 기존 지식을 대조하세요」뿐이었다).
        # 적재가 같은 것을 거절하는 문장(manual_graph._validate_targets)과 같은 길이다: 이 항목을 빼면 남은 항목은 이미 있는 그 항목을 가리킨다
        from .manual_graph import LABEL_KO
        kind = LABEL_KO.get(conflict.get('label'), '항목')
        holder = (f"다른 문서 「{conflict['owner_name']}」가 넣은 것" if conflict.get('owner_name') else
                  '다른 문서가 넣은 것' if conflict.get('kind') == 'other_document' else '기본 제공 지식이나 「지식 › 조치 방법」 화면에서 만든 것')
        issue('KNOWLEDGE_OWNERSHIP_CONFLICT', conflict.get('id'), 'knowledge_conflicts',
              f"{conflict.get('id')}: 같은 {kind}{particle(kind, '이')} 이미 지식에 있습니다({holder}) — 이 문서로 덮어쓰지 않으니 이 항목을 적재에서 제외하세요. "
              "이 문서의 다른 항목은 이미 있는 그 항목을 가리킵니다")
    # 2026-10-23 수업 조건 리허설: 구조판에는 후보 규칙이 없고 중계 모델 추출이 세 문서 모두 후보 규칙을 내지 않아, 적재는 됐는데
    # A · B · C 판단이 「후보 지식이 없습니다」로 보류됐다. 판단이 이 절차를 후보로 낼 길(이 문서의 후보 규칙 출력, 또는 고장 조치가
    # 자동 합류할 그 고장 유형의 후보 규칙)이 없으면 검토자에게 알린다. 적재를 막지는 않는다(적재는 사람 검토 뒤 별도 검사).
    own_outputs = {ref for r in k.get('rules') or [] if r.get('effect') == 'SELECT' and r.get('table') == 'dt:action-candidates'
                   for ref in r.get('outputs') or []}
    joinable = {r['id'] for r in catalog['candidate_failure_modes']}
    # 후보 규칙이 없는 절차를 셋으로 가른다(2026-11-14 — 수업 문서 하나를 기준으로 맞고 틀림을 정하지 않는다).
    #  ① 정비 묶음(maintenance_policy.packages.sop)이 부르는 절차: 그 묶음을 가진 절차가 후보이고 이 절차는 그 안에서 실행된다 — 알리지 않는다.
    #  ② 같은 원인을 맡은 다른 절차가 후보로 나오는 절차: 그 절차의 결과에 따라 이어지는 절차(HM-8 의 점검 뒤 교체)일 수도, 빠뜨린 대안 조치일 수도
    #     있다 — 검사기가 가를 수 없으니 「검토 필요」가 아니라 참고(notices)로 알리고 사람이 원문을 보고 정한다.
    #  ③ 그 밖: 이 절차도, 같은 원인의 다른 절차도 후보로 나올 길이 없다 — 판단이 「후보 지식이 없습니다」로 보류된다(2026-10-23 리허설). 검토 필요.
    packaged = {pkg.get('sop') for q in plan['procedures'] for pkg in ((q.get('maintenance_policy') or {}).get('packages') or [])}
    is_candidate = lambda q: q['id'] in own_outputs or kgadmin.skill_id(q['id']) in own_outputs
    covering = {}
    for q in plan['procedures']:
        if is_candidate(q):
            for cause in q.get('addresses') or []:
                covering.setdefault(cause, []).append(q['id'])
    # 설비에 딸리지 않은 구성 요소(이 문서 · 다른 문서가 넣은 다른 설비)의 고장 유형을 고치는 절차는 판단 엔진의 조치 후보 규칙이 닿지 않는다 — 판단 엔진은 설비의
    # 경보에서 그 설비의 증상 · 고장 유형으로 간다. 「조치 후보 규칙을 더하세요」는 거기서 할 수 없는 일이라 검토 필요가 아니라 참고로 그 사실을 말한다
    fresh = 'sensors' in catalog and all('assets' in c for c in catalog['components'])      # 옛 카탈로그는 설비 구조 판정이 CATALOG_OUTDATED 로 말했다
    outside = manual_knowledge.outside_plant(k, catalog) if fresh and 'failure_modes' in k else set()
    for p in plan['procedures']:
        if p.get('kind') == 'reference' or p.get('executable') is False:
            continue
        if p['id'] in packaged:
            continue
        if p.get('failureMode') in outside:
            notices.append(dict(code='CANDIDATE_OUTSIDE_PLANT', sop=p['id'], field='knowledge.rules',
                                message=f"{p['id']}: 이 절차가 고치는 고장은 판단 엔진이 다루는 설비({' · '.join(sorted(a['code'] for a in catalog['assets'] if a.get('code')))})의 구성 요소가 아닌 곳에서 생겨, 판단 엔진의 "
                                        "조치 후보 규칙이 이 절차에 닿지 않습니다 — 그 설비를 맡은 에이전트가 지식 지도에서 이 절차를 읽어 씁니다"))
            continue
        siblings = sorted({s for cause in p.get('addresses') or [] for s in covering.get(cause, []) if s != p['id']})
        if not is_candidate(p) and siblings and all(cause in covering for cause in p['addresses']):
            relation = p.get('relation')
            if not (relation in kgadmin.CORRECTIVE_RELATIONS and p.get('failureMode') in joinable):
                notices.append(dict(code='CANDIDATE_NOT_DIRECT', sop=p['id'], field='knowledge.rules', siblings=siblings,
                                    message=f"{p['id']}: 판단의 조치 후보에 직접 나오지 않는 절차입니다. 같은 원인의 {' · '.join(siblings)}{particle(' · '.join(siblings), '이')} 후보로 나옵니다. "
                                            f"그 절차의 결과에 따라 이어지는 절차라면 그대로 두세요. 경보에서 바로 고를 조치라면 조치 후보 규칙을 더하세요"))
            continue
        if p['id'] in own_outputs or kgadmin.skill_id(p['id']) in own_outputs:
            continue
        relation = p.get('relation')      # 적재와 같다 — 비면 기본값을 두지 않는다(kgadmin.validate_skill)
        if relation in kgadmin.CORRECTIVE_RELATIONS and p.get('failureMode') in joinable:
            continue
        issue('CANDIDATE_RULE_MISSING', p['id'], 'knowledge.rules',
              f"{p['id']}: 이 절차를 조치 후보로 내는 규칙이 없어 판단이 이 절차를 후보로 내지 못합니다. 원문이 후보 조건을 말하면 "
              f"조치 후보 규칙(결과에 {p['id']}을 둔 선택 규칙)을 더하세요")
    execution = []
    pm_outputs = {ref for r in k.get('rules') or []
                  if r.get('effect') == 'SELECT' and r.get('table') == 'dt:action-candidates'
                  and any(t.get('variable') == 'pattern' and t.get('value') == PM_PATTERN for t in r.get('tests') or [])
                  for ref in r.get('outputs') or []}
    for p in procedures:
        raw_link = overrides[p['id']] if p['id'] in overrides else p.get('link')
        if p['id'] in pm_outputs or kgadmin.skill_id(p['id']) in pm_outputs:
            own_issues = [i for i in issues if i.get('sop') == p['id']]
            if not isinstance(raw_link, dict) or not raw_link.get('maintenance_policy'):
                own_issues.append(dict(code='PM_SCOPE_POLICY_REQUIRED',sop=p['id'],field='link.maintenance_policy',
                    message='실제 정기 정비 실행에는 원문의 정비 묶음 · 적용 설비 · 주기 · 필수 부품 정책이 필요합니다'))
            own_issues.append(dict(code='PM_ACTUAL_CONTEXT_REQUIRED',sop=p['id'],field='pm_context',
                                  message='적재 전 구조 검사는 실제 운전 시간 · 정비 요청 · 정비 시간대 · 재고 · 인력을 보지 않습니다. 실행할 때 다시 확인합니다'))
            execution.append(dict(sop=p['id'],executable=True,ready=False,issues=own_issues,
                                  execution_checked=False,evaluation_mode='structural'))
        if isinstance(raw_link, dict) and raw_link.get('scope') == 'purchase':
            explicit = raw_link.get('executable') if type(raw_link.get('executable')) is bool else None
            own_issues = [i for i in issues if i.get('sop') == p['id']]
            if explicit is True and not raw_link.get('purchase_comparison_policy'):
                # 2026-10-25 수업 한 바퀴: 정책 없는 PR-07 개정을 적재하자 C 판단이 「검토된 원문 정책이 없습니다」로 보류됐다(agentsvc cards → compare)
                own_issues.append(dict(code='PURCHASE_COMPARISON_POLICY_REQUIRED', sop=p['id'], field='link.purchase_comparison_policy',
                                       message='실제 구매 판단에는 원문의 총비용 비교 기준(불량 1건 손실 · 전수 검사 기준 · 비용) 정책이 필요합니다'))
            if issues and not own_issues:
                own_issues = [dict(code='BATCH_NOT_READY',sop=p['id'],field='validation',
                                   message='같은 제안의 지식·규칙 또는 다른 절차 검사 오류가 남아 있습니다')]
            execution.append(dict(sop=p['id'], executable=explicit,
                                  ready=explicit is True and not issues and not own_issues, issues=own_issues,
                                  evaluation_mode='structural', execution_checked=False,
                                  source_notice='구매 지식의 구조 검사 결과입니다. 실제 견적·재고·공급사 조건과 실행 시점의 업무 사실은 확인하지 않았습니다. 승인 전에 실제 조건을 다시 검사해야 합니다.'))
    result = dict(checked=True, technical_ready=not issues, needs_human_review=True, can_commit=False, issues=issues)
    result['source_value_warnings'] = manual_knowledge.source_value_warnings(original)
    result['notices'] = notices
    if execution:
        result.update(execution=execution, executable_ready=any(e['ready'] for e in execution))
    return result
