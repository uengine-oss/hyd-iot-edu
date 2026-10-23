"""Explicit source-backed purchasing domain; legacy Skills remain fault actions."""
import re
import math
from copy import deepcopy

PURCHASE = 'purchase'
PART_ID = re.compile(r'^part:[a-z0-9]+(?:-[a-z0-9.]+)*$')
PURCHASE_ACTION = 'action:purchase-request'
PURCHASE_ROLE = 'role:purchasing'
PURCHASE_SYSTEM = 'sys:erp'
SUPPLIER_POLICIES = ('oem', 'lowest_approved', 'fastest_quote')


class SupplierUnresolved(ValueError):
    """The policy and the quotes are valid, but this policy names no single real supplier for the requested Part (no
    matching quote, a tie, or a supplier without SUPPLIED_BY to the Part). Only that card is impossible; the other policy
    cards are still evaluated (2026-10-23 audit: the cooler core quotes include sup:c, which the graph does not supply,
    and SOP-PUR-13's fastest quote erased SOP-PUR-11 · 12 too). Never replaced by another supplier."""


def resolve_supplier(skill, facts):
    """Bind a source policy to real quotes; never change the stored SOP or quotes."""
    policy = skill.get('supplier_policy')
    if policy is None:
        return deepcopy(skill)
    if policy not in SUPPLIER_POLICIES or skill.get('scope') != PURCHASE or skill.get('executable') is not True:
        raise ValueError('명시 실행 구매 정책의 계약이 올바르지 않습니다')
    actions = skill.get('actions') or []
    if len(actions) != 1 or actions[0].get('code') != 'PR_CREATE' or actions[0].get('value') is not None:
        raise ValueError('동적 구매 정책에는 공급사 미확정 PR_CREATE 하나가 필요합니다')
    quotes = facts.get('spare_quotes')
    if not isinstance(quotes, dict) or not quotes:
        raise ValueError('동적 공급사 선택에 실제 부품별 견적이 필요합니다')
    eligible = []
    for supplier, quote in quotes.items():
        if not isinstance(quote, dict) or type(quote.get('avl')) is not bool or any(
                type(quote.get(k)) not in (int, float) or not math.isfinite(quote[k])
                for k in ('price', 'lead_d', 'fail_rate')):
            raise ValueError('실제 부품별 견적의 수치와 AVL을 확인할 수 없습니다')
        if quote['price'] < 0 or quote['lead_d'] < 0 or not 0 <= quote['fail_rate'] <= 1:
            raise ValueError('실제 부품별 견적의 수치 범위가 잘못되었습니다')
        if policy == 'oem' and quote.get('name') != 'B-OEM (순정)':
            continue
        if policy == 'lowest_approved' and (not quote['avl'] or quote.get('name') == 'B-OEM (순정)'):
            continue
        eligible.append((supplier, quote))
    if not eligible:
        raise SupplierUnresolved('원문 공급사 선택 정책을 충족하는 실제 견적이 없습니다')
    if policy == 'oem':
        if len(eligible) != 1:
            raise SupplierUnresolved('정본 순정 라벨 B-OEM (순정)의 실제 견적이 유일하지 않습니다')
        chosen = eligible[0]
    else:
        metric = 'price' if policy == 'lowest_approved' else 'lead_d'
        minimum = min(q[metric] for _, q in eligible)
        winners = [(s, q) for s, q in eligible if q[metric] == minimum]
        if len(winners) != 1:
            raise SupplierUnresolved('원문에 없는 동률 공급사 선택을 추정하지 않습니다')
        chosen = winners[0]
    supplier, quote = chosen
    part = facts.get('purchase_part')
    if not any(r.get('part') == part and r.get('supplier') == supplier for r in skill.get('partSuppliers') or []):
        raise SupplierUnresolved(f'선택한 실제 견적 공급사({supplier})와 요청 Part의 SUPPLIED_BY 관계가 없습니다')
    result = deepcopy(skill)
    result['actions'][0]['value'] = supplier
    result['resolvedSupplier'] = dict(id=supplier, policy=policy, part=part,
                                      partNo=facts.get('spare_part_no'), quote=deepcopy(quote),
                                      quoteSource='/scm/quotes', quoteSet=deepcopy(quotes),
                                      classificationLabel=quote.get('name'))
    return result


def purchase_shape(body, *, source_backed):
    """Validate explicit fields, without inventing missing supplier/role/parts."""
    if not source_backed:
        raise ValueError('구매 SOP는 보관 원문과 인용을 검증하는 매뉴얼 검토 경로에서만 생성할 수 있습니다')
    if body.get('scope') != PURCHASE:
        raise ValueError('FM 없는 구매 절차는 scope=purchase를 명시해야 합니다')
    if body.get('failureMode') is not None or body.get('relation') is not None or body.get('addresses'):
        raise ValueError('구매 영역 SOP에는 고장 유형·고장 조치 관계·대상 원인을 붙이지 않습니다')
    if body.get('kind') not in (None, 'work_order'):
        raise ValueError('구매 영역 SOP의 종류는 work_order입니다. 설비 제어가 아닙니다')
    parts = body.get('parts')
    if not isinstance(parts, list) or not 1 <= len(parts) <= 20 or any(not isinstance(p, str) or not PART_ID.fullmatch(p) for p in parts):
        raise ValueError('구매 영역에는 원문에 근거한 Part id 범위1~20개를 명시해야 합니다')
    if len(set(parts)) != len(parts):
        raise ValueError('구매 영역 Part 범위가 중복되었습니다')
    executable = body.get('executable')
    if type(executable) is not bool:
        raise ValueError('구매 원문 절차의 실행 후보 여부(executable)를 참/거짓으로 명시하세요')
    actions = body.get('actions') or []
    policy = body.get('supplier_policy')
    if policy is not None and policy not in SUPPLIER_POLICIES:
        raise ValueError('공급사 선택 정책은 oem/lowest_approved/fastest_quote입니다')
    if not isinstance(actions, list):
        raise ValueError('구매 원자 조치는 목록이어야 합니다')
    if not executable:
        if actions or policy is not None:
            raise ValueError('참고 보관 절차에는 실행 Action을 붙이지 않습니다')
    else:
        if len(actions) != 1 or not isinstance(actions[0], dict) or actions[0].get('action') != PURCHASE_ACTION:
            raise ValueError('실행 구매 SOP는 PR_CREATE 구매요청 Action 하나만 명시해야 합니다')
        if body.get('approver') != PURCHASE_ROLE:
            raise ValueError('실행 구매 SOP에는 원문에 명시된 구매 담당 승인 역할(role:purchasing)이 필요합니다')
        value = actions[0].get('value')
        if policy is not None and value is not None:
            raise ValueError('동적 공급사 정책과 고정 Supplier 값을 동시에 지정할 수 없습니다')
        if policy is None and (not isinstance(value, str) or not value.startswith('sup:')):
            raise ValueError('실행 구매 SOP의 공급사 값은 실제 Supplier id로 확인해야 합니다')
    result = dict(scope=PURCHASE, executable=executable, parts=list(parts), kind='work_order',
                  failureMode=None, relation=None)
    if policy is not None:
        result['supplier_policy'] = policy
    return result


def purchase_graph_issues(nodes, relationships):
    """Schema/seed validator's cross-node purchase contract; never writes data."""
    by_id = {n['props'].get('id'): n for n in nodes}
    issues = []
    for n in nodes:
        props = n['props']
        if 'Skill' not in n['labels']:
            continue
        sid = props.get('id')
        outgoing = [r for r in relationships if r['a'] == sid]
        incoming = [r for r in relationships if r['b'] == sid]
        if props.get('scope') != PURCHASE:
            if ('executable' in props and not (props.get('kind') == 'reference' and props.get('executable') is False)) or 'supplier_policy' in props or 'purchase_comparison_policy' in props or any(r['type'] == 'INVOLVES_PART' for r in outgoing):
                issues.append(f'{sid}: 실행 여부와 Part 업무 범위는 명시 purchase SOP에만 둡니다')
            continue
        if props.get('purchase_comparison_policy') is not None:
            try:
                from .purchase_comparison import policy
                contract=policy(props['purchase_comparison_policy'])
                if contract['anchor']['source_id'] != props.get('source_id') or props.get('executable') is not True:
                    raise ValueError('구매 비교 정책은 같은 원문 판본의 실행 구매 절차에만 적용합니다')
            except ValueError as exc:
                issues.append(f'{sid}: {exc}')
        parts = [r['b'] for r in outgoing if r['type'] == 'INVOLVES_PART']
        roles = [r['b'] for r in outgoing if r['type'] == 'APPROVED_BY']
        actions = [dict(action=r['b'], value=r['props'].get('value')) for r in outgoing if r['type'] == 'CONSISTS_OF']
        fms = [r for r in incoming if r['type'] in ('MITIGATED_BY', 'REMEDIED_BY', 'PREVENTED_BY')]
        addresses = [r['b'] for r in outgoing if r['type'] == 'ADDRESSES']
        try:
            purchase_shape(dict(props, parts=parts, actions=actions, approver=roles[0] if len(roles) == 1 else None,
                                failureMode=fms[0]['a'] if fms else None, addresses=addresses), source_backed=True)
        except ValueError as exc:
            issues.append(f'{sid}: {exc}')
        systems = [r['a'] for r in incoming if r['type'] == 'HAS_SKILL' and 'System' in r['la']]
        if systems != [PURCHASE_SYSTEM]:
            issues.append(f'{sid}: 구매 SOP의 수행 시스템은 sys:erp 하나여야 합니다')
        if len(roles) > 1:
            issues.append(f'{sid}: 구매 승인 역할이 중복되었습니다')
        source = props.get('source_id')
        steps = [r['b'] for r in outgoing if r['type'] == 'HAS_STEP']
        if not source or not props.get('citation') or not steps:
            issues.append(f'{sid}: 구매 SOP는 보관 원문과 인용·단계가 필요합니다')
        for step_id in steps:
            step = by_id.get(step_id, {}).get('props', {})
            sections = [r['b'] for r in relationships if r['a'] == step_id and r['type'] == 'REFERS_TO']
            if step.get('source_id') != source or not step.get('citation') or not sections:
                issues.append(f'{sid}: 단계 {step_id}의 원문 인용이 없습니다')
            for section_id in sections:
                section = by_id.get(section_id, {}).get('props', {})
                sources = [r['b'] for r in relationships if r['a'] == section_id and r['type'] == 'PART_OF']
                if section.get('source_id') != source or not any(by_id.get(k, {}).get('props', {}).get('source_id') == source for k in sources):
                    issues.append(f'{sid}: 원문 절 {section_id}의 보관 출처가 일치하지 않습니다')
        for action in actions:
            target = by_id.get(action['action'], {}).get('props', {})
            if target.get('code') != 'PR_CREATE' or target.get('kind') != 'transaction':
                issues.append(f'{sid}: 구매 실행 Action은 PR_CREATE transaction이어야 합니다')
            for part in parts:
                if props.get('supplier_policy') is not None:
                    if not any(r['a'] == part and r['type'] == 'SUPPLIED_BY' for r in relationships):
                        issues.append(f'{sid}: {part}의 실제 공급 관계가 없습니다')
                    continue
                if not any(r['a'] == part and r['type'] == 'SUPPLIED_BY' and r['b'] == action['value'] for r in relationships):
                    issues.append(f'{sid}: {part}와 {action["value"]}의 SUPPLIED_BY 공급 관계가 없습니다')
    # The candidate table cannot make reference procedures executable or mix
    # purchasing with physical/maintenance outputs through a generic FM rule.
    candidate_rules = {r['b'] for r in relationships if r['type'] == 'HAS_RULE' and r['a'] == 'dt:action-candidates'}
    for rid in candidate_rules:
        outputs = [by_id.get(r['b'], {}).get('props', {}) for r in relationships if r['a'] == rid and r['type'] == 'OUTPUTS']
        purchase = [p for p in outputs if p.get('scope') == PURCHASE]
        if not purchase:
            continue
        if any(p.get('executable') is not True for p in purchase):
            issues.append(f'{rid}: 참고 구매 SOP는 후보 Rule 출력이 될 수 없습니다')
        if any(p.get('scope') != PURCHASE for p in outputs):
            issues.append(f'{rid}: 구매와 고장 조치 후보를 같은 Rule에 섞지 않습니다')
        pattern_test = any(r['a'] == rid and r['type'] == 'TESTS' and
                           by_id.get(r['b'], {}).get('props', {}).get('variable') == 'pattern' and
                           r['props'].get('operator') == '==' and r['props'].get('value') == 'SPARE_BELOW_MIN'
                           for r in relationships)
        if not pattern_test:
            issues.append(f'{rid}: 구매 후보 Rule은 pattern == SPARE_BELOW_MIN을 명시해야 합니다')
    return issues
