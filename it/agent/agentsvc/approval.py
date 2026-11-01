"""Read current graph/source facts before authorizing an existing human choice.

No decision submission or execution occurs here. An unknown applicable rule is
not proof of compliance; material changes require a new human-reviewed decision.
"""
from datetime import datetime, timezone
from copy import deepcopy
import hashlib
import json
from hydcommon.forecast import number
from hydcommon.maintenance_policy import PM_PATTERN
from hydcommon.skill_scope import PURCHASE_PATTERN

from . import cards, decide, forecasting, guardrail


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def consented(key, value):
    """What the human consented to in a card field. A maintenance plan's elapsed-time values (assets[].applicability.target_hours
    and a reschedule plan's hours_at_window — hydcommon.maintenance_plan.ELAPSED_*) fall by 0.01 h every 36 s while the window,
    counter, package and parts stay the same. Like A086 (hours until the MES due date) they are elapsed time, not consent
    content: the current plan is rebuilt from the same rows and fails if the target passes the source limit, and execution
    re-reads it (ent.pm_scope_check · ent.pm_reschedule · memory recheck use the same without_elapsed). 2026-10-23 live: every
    B approval made more than ~36 s after the decision was refused as 'maintenancePlan changed'. Everything else stays compared."""
    if key != 'maintenancePlan' or not isinstance(value, dict):
        return value
    from hydcommon.maintenance_plan import without_elapsed
    return without_elapsed(value)


#: 승인 보류 사유에 보이는 카드 칸 이름(학생 말 — 검진 G1-10: 「카드의 rankingEvidence 내용이 변경됐습니다」)
CARD_FIELDS = {'sopId': '절차 번호', 'kind': '카드 종류', 'actions': '조치', 'approver': '승인 역할', 'steps': '절차 단계',
               'warnings': '경고', 'penalties': '감점', 'forecast': '예측', 'policy_sha256': '적용 규칙', 'reviewed_choice': '검토한 조치값',
               'rankingEvidence': '순위 근거', 'supplier_policy': '공급사 정책', 'resolvedSupplier': '정한 공급사',
               'maintenancePlan': '정비 계획', 'economicComparison': '총비용 비교'}


def unresolved(rule, facts):
    values = [(test.get('variable'), cards.test_ok(test, facts)) for test in rule.get('tests') or []]
    if any(result is False for _, result in values):
        return []
    return [key for key, result in values if result is None]


def _parameterized(skill, parameters):
    if not isinstance(parameters, dict) or set(parameters) - {'fan_pct', 'load_pct'}:
        raise ValueError('조치 변경은 팬·부하 설정만 지원합니다')
    effective = deepcopy(skill)
    normalized = {}
    for key, value in parameters.items():
        actions = [a for a in effective.get('actions', []) if a.get('kind')=='command' and a.get('param')==key]
        if len(actions) != 1 or any(actions[0].get(k) is None for k in ('min','max')):
            raise ValueError(f'{key}: 이 SOP에 변경 가능한 조치와 명시 범위가 없습니다')
        a = actions[0]
        normalized[key] = number(value, key, a['min'], a['max'])
        a['value'] = normalized[key]
    if normalized:
        labels = {'fan_pct':'팬', 'load_pct':'부하'}
        effective['name'] = (skill.get('sopId') or skill['name']) + ' 변경안: ' + ', '.join(
            f'{labels[k]} {v:g}%' for k,v in sorted(normalized.items()))
        effective['description'] = 'SOP 원문 기본값과 구분하여 검토하는 조치값입니다. 실제 적용값은 아래 원자 조치를 확인하세요.'
    return effective, normalized


def current_options(kg, tsdb, decision, option_id, parameters=None):
    """Common current-source evaluation for preview and final authorization."""
    origin, prior = decision.get('origin') or {}, decision.get('facts') or {}
    pattern = origin.get('pattern') or (decision.get('scenario') or {}).get('pattern') or prior.get('pattern')
    cause = origin.get('cause') or prior.get('cause')
    failure = origin.get('failureMode') or prior.get('failure_mode')
    purchase = origin.get('cause_route') == 'purchase-part'
    required = (decision.get('asset'), pattern) if purchase else (decision.get('asset'), pattern, cause, failure)
    if not all(isinstance(v, str) and v for v in required):
        raise ValueError('설비·경보·원인·고장 유형의 판단 근거가 없습니다. 다시 판단해야 합니다')
    part = None
    if purchase:
        declared = origin.get('part')
        if pattern != PURCHASE_PATTERN or not isinstance(declared, dict) or not isinstance(declared.get('partNo'), str):
            raise ValueError('명시 구매 Part 경로의 원천 근거가 올바르지 않습니다')
        part = kg.purchase_part(declared['partNo'])
        if part.get('id') != declared.get('id') or cause is not None or failure is not None:
            raise ValueError('명시 구매 Part가 현재 지식과 다르거나 고장 근거가 혼합되었습니다')
    known = dict(pattern=pattern, cause=cause, failure_mode=failure)
    if prior.get('failure_mode_name'):    # 다시 보기 문장도 처음 판단처럼 고장 유형을 이름으로(「fm:…」 id 가 아니라)
        known['failure_mode_name'] = prior['failure_mode_name']
    if part is not None:
        known.update(purchase_part=part['id'],purchase_part_no=part['partNo'],purchase_part_name=part.get('name'))
    # 처음 판단과 같은 지식 묶음 · 같은 변수 · 같은 원천(decide.judgment_context) — 원천을 못 읽으면 그 까닭으로 승인 검사가 멈춘다
    ctx = decide.judgment_context(kg, known)
    rules, inputs, skills, tradeoffs = ctx['dmn'], ctx['inputs'], dict(ctx['skills']), ctx['tradeoffs']
    reference = deepcopy(skills.get(option_id))
    reviewed = None
    if parameters is not None:
        if reference is None:
            raise ValueError('현재 지식에 선택한 SOP가 없습니다')
        skills[option_id], normalized = _parameterized(reference, parameters)
        reviewed = {'parameters': normalized, 'base_policy_sha256':cards.policy_digest(rules, reference),
                    'reference_name': reference.get('name'), 'reference_actions':reference.get('actions') or []}
    facts, provenance = decide.gather_facts(inputs, decision['asset'], known, tsdb, variables=ctx['variables'], strict=True)
    if pattern == PM_PATTERN:
        facts['pm_context'] = decide.pm_context(decision['asset'])
    compliance = [r for r in rules if r['decision'] == 'dec:compliance']
    stopping = {sid for sid, k in skills.items() if cards.stops_now(cards.option_window(compliance, sid, k, facts.get('windows_by_variable')))}
    forecasts, contexts = ({}, None) if part is not None else forecasting.candidates(kg, decision['asset'], skills, stopping)
    suppliers = kg.suppliers()
    result = cards.evaluate(rules, skills, facts, forecasts, tradeoffs, kg.precedents(failure), suppliers, contexts, evaluation_mode='execution')
    current = next((o for o in result['options'] if o['id'] == option_id), None)
    roles = {r['id']: r for r in kg.roles()}
    if current is not None and reviewed is not None:
        current['reviewed_choice'] = reviewed
    return dict(rules=rules,skills=skills,facts=facts,provenance=provenance,forecasts=forecasts,
                suppliers=suppliers,result=result,current=current,roles=roles)


def preview(kg, tsdb, decision, option_id, parameters):
    if not any(o.get('id')==option_id for o in decision.get('options', [])):
        raise ValueError('원래 결정에 없는 SOP입니다')
    data = current_options(kg, tsdb, decision, option_id, parameters)
    if data['current'] is None:
        raise ValueError('현재 규칙에서 이 SOP는 후보가 아닙니다')
    if data['current']['feasible']:
        violations=guardrail.check_cards({'options':[data['current']],'recommended':option_id})
        if violations:
            raise ValueError('검토할 SOP 근거가 불완전합니다: '+'; '.join(violations))
    result = deepcopy(decision)
    result.update(options=[data['current']], facts=data['facts'], provenance=data['provenance'],
                  roles=data['roles'], recommended=data['result']['recommended'],
                  explanation=data['result']['explanation'], rankRule=data['result'].get('rankRule'))
    return result


def assess(kg, tsdb, decision, option_id, role, consented_at=None):
    """Reread policy and sources. No supplied fact overrides are trusted."""
    old = next((o for o in decision.get('options', []) if o.get('id') == option_id), None)
    if old is None:
        raise ValueError('선택할 원래 카드가 없습니다')
    from hydcommon.execution_scope import require_decision_option
    require_decision_option(decision, old)
    review = old.get('reviewed_choice')
    if review is not None and (not isinstance(review,dict) or not isinstance(review.get('parameters'),dict)):
        raise ValueError('검토본의 조치값 계약이 올바르지 않습니다')
    data = current_options(kg,tsdb,decision,option_id, review['parameters'] if review is not None else None)
    rules, skills, facts = data['rules'], data['skills'], data['facts']
    provenance, forecasts, suppliers = data['provenance'], data['forecasts'], data['suppliers']
    current, roles = data['current'], data['roles']
    prior = decision.get('facts') or {}
    names = {p['variable']: p.get('name') or p['variable'] for p in [*(decision.get('provenance') or []), *provenance] if p.get('variable')}
    label = lambda key: f"「{names.get(key, key)}」"   # noqa: E731 — 사유 문장에는 판단 변수 id 대신 지식의 이름
    report = dict(allowed=False, needs_new_preview=False, decision=decision['id'], option=option_id,
                  checked_at=datetime.now(timezone.utc).isoformat(), facts=facts, provenance=provenance,
                  current_option=current, reasons=[], unknown=[],
                  policy_sha256=hashlib.sha256(canonical({'rules':rules,'skills':skills,'roles':roles}).encode()).hexdigest())
    reasons = report['reasons']
    if current is None:
        reasons.append('현재 규칙에서 선택한 SOP가 후보가 아닙니다')
    elif not current['feasible']:
        reasons.append('현재 규칙에서 선택한 SOP를 실행할 수 없습니다')
    if option_id in skills:
        candidate_skill = skills[option_id]
        if candidate_skill.get('supplier_policy'):
            from hydcommon.skill_scope import resolve_supplier
            candidate_skill = resolve_supplier(candidate_skill, facts)
        candidate = cards.candidate_facts(facts, candidate_skill, forecasts, suppliers)
        for rule in rules:
            applicable = (rule['decision'] == 'dec:action-candidates' and option_id in (rule.get('outputs') or [])) or (
                rule['decision'] == 'dec:compliance' and cards.compliance_applies(rule,candidate_skill))
            if applicable:
                missing = unresolved(rule, candidate if rule['decision'] == 'dec:compliance' else facts)
                if missing:
                    report['unknown'].append({'rule': rule['rule'], 'effect':rule['effect'], 'variables': missing})
    if any(row['effect'] != 'WARN' for row in report['unknown']):
        reasons.append('적용 가능한 규칙의 필수 사실을 확인할 수 없습니다')
    if current:
        reasons.extend(guardrail.check_cards({'options':[current],'recommended':option_id}))
        if forecasting.requires_plant_consent(old.get('actions')) or forecasting.requires_plant_consent(current.get('actions')):
            consent = forecasting.consent_changes(old.get('forecastContext'), current.get('forecastContext'), consented_at=consented_at)
            reasons.extend(consent)
            # 예측이 오래됐거나 바뀐 것은 새 미리 보기로 다시 검토하면 풀린다 — 화면 · 점검은 문장 글자가 아니라 이 칸으로 가린다(검진 G4-16)
            report['needs_new_preview'] = bool(consent)
        # The chosen action, work content and consent context must remain what the
        # human saw. Continuous sensor changes matter through reevaluated rules.
        for key in ('sopId', 'kind', 'actions', 'approver', 'steps', 'warnings', 'penalties', 'forecast', 'policy_sha256', 'reviewed_choice', 'rankingEvidence', 'supplier_policy', 'resolvedSupplier', 'maintenancePlan', 'economicComparison'):
            if canonical(consented(key, old.get(key))) != canonical(consented(key, current.get(key))):
                reasons.append(f'카드의 {CARD_FIELDS.get(key, key)} 내용이 바뀌었습니다. 새 판단을 검토하세요')
        need = current.get('approver') or {}
        actual_role = roles.get(role)
        if not actual_role or (role != need.get('id') and int(actual_role.get('level') or 0) <= int(need.get('level') or 0)):
            reasons.append('현재 역할 정보에서 승인 권한이 없습니다')
    # A086: a fact computed from a source time (hours until the MES due date) keeps decreasing while the record is
    # unchanged. Its consent context is the source record (provenance anchor); the elapsed time reaches the decision
    # through the re-evaluated rules above (penalties/warnings/feasibility), like continuous sensor values.
    anchors_before = {p['variable']: p['anchor'] for p in decision.get('provenance') or [] if p.get('anchor') is not None}
    anchors_after = {p['variable']: p['anchor'] for p in provenance if p.get('anchor') is not None}

    def unchanged(key):
        if key in anchors_before or key in anchors_after:
            return anchors_before.get(key) is not None and anchors_before.get(key) == anchors_after.get(key) and facts.get(key) is not None
        return prior.get(key) is not None and facts.get(key) is not None and prior.get(key) == facts.get(key)

    economic = bool(current and current.get('economicComparison'))
    for key in (() if economic else ('order_due_h', 'order_penalty_per_h', 'order_customer_tier', 'hot_lot_claim', 'hot_lot_qty')):
        if key in prior or key in facts:
            if not unchanged(key):
                reasons.append(f'업무 판단 입력 {label(key)}이(가) 바뀌었거나 확인되지 않습니다')
    # Explicit physical inputs used by current rules are also human consent
    # context. Equal values from a different column/meaning are not equivalent.
    relevant = {t.get('variable') for r in rules for t in r.get('tests') or []
                if r['decision'] == 'dec:rank-actions' or
                (r['decision'] == 'dec:action-candidates' and option_id in (r.get('outputs') or [])) or
                (r['decision'] == 'dec:compliance' and (not r.get('applies') or option_id in r['applies']))}
    before = {p['variable']: p.get('binding') for p in decision.get('provenance') or [] if p.get('binding')}
    ranking_inputs = set() if economic else cards.ranking_variables(rules)
    relevant.update(ranking_inputs)
    for key in sorted(ranking_inputs):
        if key in anchors_before or key in anchors_after:
            changed = not unchanged(key)
        else:
            changed = (key in prior) != (key in facts) or canonical(prior.get(key)) != canonical(facts.get(key))
        if changed:
            reasons.append(f'순위 판단 입력 {label(key)}이(가) 바뀌었습니다. 새 판단을 검토하세요')
    after = {p['variable']: p.get('binding') for p in provenance if p.get('binding')}
    for key in sorted(relevant & (before.keys() | after.keys())):
        if canonical(before.get(key)) != canonical(after.get(key)):
            reasons.append(f'업무 판단 입력 {label(key)}의 업무 DB 출처나 뜻이 바뀌었습니다')
        if not unchanged(key):
            reasons.append(f'업무 판단 입력 {label(key)}이(가) 바뀌었거나 확인되지 않습니다')
    report['allowed'] = not reasons
    return report
