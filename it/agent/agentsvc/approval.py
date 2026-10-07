"""Read current graph/source facts before authorizing an existing human choice.

No decision submission or execution occurs here. An unknown applicable rule is
not proof of compliance; material changes require a new human-reviewed decision.
"""
from datetime import datetime, timezone
from copy import deepcopy
import hashlib
import json
from hydcommon.forecast import number
from hydcommon import bsc

from . import cards, decide, forecasting, guardrail


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


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
    if not all(isinstance(v, str) and v for v in (decision.get('asset'), pattern, cause, failure)):
        raise ValueError('설비·경보·원인·고장 유형의 판단 근거가 없습니다. 다시 판단해야 합니다')
    rules, inputs = kg.dmn(), kg.inputs()
    ids = sorted({sid for r in rules if r['decision'] == 'dec:action-candidates' for sid in r.get('outputs') or []})
    skills = {r['skillId']: r for r in kg.skills(ids)}
    reference = deepcopy(skills.get(option_id))
    reviewed = None
    if parameters is not None:
        if reference is None:
            raise ValueError('현재 지식에 선택한 SOP가 없습니다')
        skills[option_id], normalized = _parameterized(reference, parameters)
        reviewed = {'parameters': normalized, 'base_policy_sha256':cards.policy_digest(rules, reference),
                    'reference_name': reference.get('name'), 'reference_actions':reference.get('actions') or []}
    known = dict(pattern=pattern, cause=cause, failure_mode=failure)
    facts, provenance = decide.gather_facts(inputs, decision['asset'], known, tsdb, strict=True)
    forecasts, contexts = forecasting.candidates(kg, decision['asset'], skills)
    suppliers = kg.suppliers()
    tradeoffs = kg.tradeoffs(ids)
    result = cards.evaluate(rules, skills, facts, forecasts, tradeoffs, kg.precedents(failure), suppliers, contexts)
    current = next((o for o in result['options'] if o['id'] == option_id), None)
    roles = {r['id']: r for r in kg.roles()}
    if current is not None and reviewed is not None:
        current['reviewed_choice'] = reviewed
    return dict(rules=rules,skills=skills,facts=facts,provenance=provenance,forecasts=forecasts,
                suppliers=suppliers,result=result,current=current,roles=roles,
                bsc_variables=bsc.fact_variables([r for r in tradeoffs if r['skill']==option_id]))


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


def assess(kg, tsdb, decision, option_id, role):
    """Reread policy and sources. No supplied fact overrides are trusted."""
    old = next((o for o in decision.get('options', []) if o.get('id') == option_id), None)
    if old is None:
        raise ValueError('선택할 원래 카드가 없습니다')
    review = old.get('reviewed_choice')
    if review is not None and (not isinstance(review,dict) or not isinstance(review.get('parameters'),dict)):
        raise ValueError('검토본의 조치값 계약이 올바르지 않습니다')
    data = current_options(kg,tsdb,decision,option_id, review['parameters'] if review is not None else None)
    rules, skills, facts = data['rules'], data['skills'], data['facts']
    provenance, forecasts, suppliers = data['provenance'], data['forecasts'], data['suppliers']
    current, roles = data['current'], data['roles']
    prior = decision.get('facts') or {}
    report = dict(allowed=False, decision=decision['id'], option=option_id,
                  checked_at=datetime.now(timezone.utc).isoformat(), facts=facts, provenance=provenance,
                  current_option=current, reasons=[], unknown=[],
                  policy_sha256=hashlib.sha256(canonical({'rules':rules,'skills':skills,'roles':roles}).encode()).hexdigest())
    reasons = report['reasons']
    if current is None:
        reasons.append('현재 규칙에서 선택한 SOP가 후보가 아닙니다')
    elif not current['feasible']:
        reasons.append('현재 규칙에서 선택한 SOP를 실행할 수 없습니다')
    if option_id in skills:
        candidate = cards.candidate_facts(facts, skills[option_id], forecasts, suppliers)
        for rule in rules:
            applicable = (rule['decision'] == 'dec:action-candidates' and option_id in (rule.get('outputs') or [])) or (
                rule['decision'] == 'dec:compliance' and (not rule.get('applies') or option_id in rule['applies']))
            if applicable:
                missing = unresolved(rule, candidate if rule['decision'] == 'dec:compliance' else facts)
                if missing:
                    report['unknown'].append({'rule': rule['rule'], 'effect':rule['effect'], 'variables': missing})
    if any(row['effect'] != 'WARN' for row in report['unknown']):
        reasons.append('적용 가능한 규칙의 필수 사실을 확인할 수 없습니다')
    if current:
        reasons.extend(guardrail.check_cards({'options':[current],'recommended':option_id}))
        reasons.extend(forecasting.consent_changes(old.get('forecastContext'), current.get('forecastContext')))
        # The chosen action, work content and consent context must remain what the
        # human saw. Continuous sensor changes matter through reevaluated rules.
        for key in ('sopId', 'kind', 'actions', 'approver', 'steps', 'warnings', 'penalties', 'forecast', 'policy_sha256', 'reviewed_choice', 'rankingEvidence'):
            if canonical(old.get(key)) != canonical(current.get(key)):
                reasons.append(f'카드의 {key} 내용이 변경됐습니다. 새 판단을 검토하세요')
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

    for key in ('order_due_h', 'order_penalty_per_h', 'order_customer_tier', 'hot_lot_claim', 'hot_lot_qty'):
        if key in prior or key in facts:
            if not unchanged(key):
                reasons.append(f'업무 판단 입력 {key}가 변경됐거나 확인되지 않습니다')
    # Explicit physical inputs used by current rules are also human consent
    # context. Equal values from a different column/meaning are not equivalent.
    relevant = {t.get('variable') for r in rules for t in r.get('tests') or []
                if r['decision'] == 'dec:rank-actions' or
                (r['decision'] == 'dec:action-candidates' and option_id in (r.get('outputs') or [])) or
                (r['decision'] == 'dec:compliance' and (not r.get('applies') or option_id in r['applies']))}
    before = {p['variable']: p.get('binding') for p in decision.get('provenance') or [] if p.get('binding')}
    ranking_inputs = cards.ranking_variables(rules)
    relevant.update(ranking_inputs)
    relevant.update(data['bsc_variables'])
    for key in sorted(ranking_inputs):
        if key in anchors_before or key in anchors_after:
            changed = not unchanged(key)
        else:
            changed = (key in prior) != (key in facts) or canonical(prior.get(key)) != canonical(facts.get(key))
        if changed:
            reasons.append(f'순위 판단 입력 {key}가 변경됐습니다. 새 판단을 검토하세요')
    after = {p['variable']: p.get('binding') for p in provenance if p.get('binding')}
    for key in sorted(relevant & (before.keys() | after.keys())):
        if canonical(before.get(key)) != canonical(after.get(key)):
            reasons.append(f'업무 판단 입력 {key}의 물리 출처 또는 의미가 변경됐습니다')
        if not unchanged(key):
            reasons.append(f'업무 판단 입력 {key}가 변경됐거나 확인되지 않습니다')
    report['allowed'] = not reasons
    return report
