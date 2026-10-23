"""Approved PM scheduling effects, using actual CMMS identities and windows."""
from copy import deepcopy
import math


#: Plan values that change with elapsed time alone. Each is the PM counter plus the hours left until the planned window
#: (ent.pm_status / entsim pm_row hours_at_next_window · hours_at_following_window, computed from now() and rounded to
#: 0.01 h), so it falls by 0.01 every 36 s while the window, counter, package, parts and limit stay the same.
#: Neither is consent content: the window id · start, counter, parts and limit_hours stay compared, and execution re-reads
#: the current value and only checks it against the limit — ent.pm_scope_check (056) reads v_hours from ent.pm_scope_row
#: and raises only when it exceeds interval*(1+tolerance); ent.pm_reschedule (054) checks hours_at_following_window
#: against the same limit. Neither compares the planned value. (2026-10-23 audit: B approvals more than ~36 s after the
#: decision were refused as 'maintenancePlan changed' (approval) and, on the memory backend, at execution (E5).)
ELAPSED_APPLICABILITY_FIELDS = ('target_hours',)   # assets[].applicability
ELAPSED_PLAN_FIELDS = ('hours_at_window',)          # top level of a WO_RESCHEDULE plan


def without_elapsed(value):
    """A copy of a maintenance plan without the values that change with elapsed time alone (the consent comparison form)."""
    if not isinstance(value, dict):
        return value
    result = deepcopy(value)
    for key in ELAPSED_PLAN_FIELDS:
        result.pop(key, None)
    for member in result.get('assets') or []:
        applicability = member.get('applicability') if isinstance(member, dict) else None
        if isinstance(applicability, dict):
            for key in ELAPSED_APPLICABILITY_FIELDS:
                applicability.pop(key, None)
    return result


def plan(skill, facts, window):
    from .maintenance_policy import policy, scope
    if not isinstance(skill.get('source_id'),str) or not skill['source_id'].strip():
        raise ValueError('실제 PM 실행 정책이 연결된 원문 판본을 확인할 수 없습니다')
    contract=policy(skill.get('maintenance_policy'))
    if any(contract[key].get('source_id')!=skill.get('source_id') for key in ('anchor','model_anchor')):
        raise ValueError('정비 정책과 동일 모델 인용이 실행 SOP의 원문 판본과 다릅니다')
    context=facts.get('pm_context') or {}
    scoped=scope(contract,context,context.get('asset'),window)
    actions = skill.get('actions') or []
    changes = [a for a in actions if a.get('code') == 'WO_RESCHEDULE']
    creates = [a for a in actions if a.get('code') == 'WO_CREATE']
    if not changes and not creates:
        raise ValueError('PM 실행 후보에 원문 기반 오더 발행 또는 일정 변경 Action이 없습니다')
    if len(changes) + len(creates) != 1:
        raise ValueError('PM 후보의 오더 효과가 중복되거나 충돌합니다')
    if not isinstance(window, dict) or (not window.get('id') and window.get('immediate') is not True):
        raise ValueError('PM 후보의 실제 목표 정비 창을 확인할 수 없습니다')
    effect = 'WO_RESCHEDULE' if changes else 'WO_CREATE'
    if (effect=='WO_RESCHEDULE') != (contract['stock_effect']=='preserve'):
        raise ValueError('원문 일정 변경은 기존 부품 할당 보존이고 새 오더는 명시 예약 또는 출고입니다')
    if effect == 'WO_CREATE':
        return dict(code=effect,window=deepcopy(window),source_id=skill.get('source_id'),
                    policy=contract,**scoped)
    if changes[0].get('kind') != 'transaction' or changes[0].get('target') != 'sys:cmms':
        raise ValueError('PM 일정 변경은 실제 CMMS transaction Action이어야 합니다')
    if not window.get('id') or window.get('basis') != 'hours_at_following_window':
        raise ValueError('기존 PM 오더의 일정 변경에는 실제 그다음 정비 창이 필요합니다')
    hours = facts.get('hours_at_following_window')
    limit = facts.get('pm_limit_hours')
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (hours,limit)) or hours > limit:
        raise ValueError('일정 변경의 실제 운전시간과 허용 상한을 확인할 수 없거나 초과했습니다')
    order = facts.get('existing_pm_order')
    if not isinstance(order,dict) or not isinstance(order.get('id'),str) or not order['id']:
        raise ValueError('이번 PM 계획의 실제 기존 정비 오더가 없습니다')
    if order.get('status') != '배정됨' or order.get('completed_at') is not None:
        raise ValueError('기존 PM 오더가 일정 변경 가능한 배정 상태가 아닙니다')
    if order.get('id') != facts.get('pm_planned_wo'):
        raise ValueError('기존 오더와 이번 PM 계획의 연결이 일치하지 않습니다')
    if type(facts.get('pm_cycle')) is not int or facts['pm_cycle'] < 1:
        raise ValueError('이번 PM 회차의 실제 번호를 확인할 수 없습니다')
    return dict(code=effect,ref=order['id'],expected_order=deepcopy(order),
                window=deepcopy(window),hours_at_window=hours,limit_hours=limit,
                cycle=facts.get('pm_cycle'),source_id=skill.get('source_id'),policy=contract,**scoped)


def recheck(approved,context):
    from .maintenance_policy import policy,scope
    if not isinstance(approved,dict) or approved.get('code') not in ('WO_CREATE','WO_RESCHEDULE'):
        raise ValueError('승인한 원문 정비 계획이 없습니다')
    current=scope(policy(approved.get('policy')),context,context.get('asset'),approved.get('window'))
    # scope() fails when the current target hours exceed the source limit; the elapsed value itself is not compared.
    now,then=without_elapsed(current),without_elapsed(approved)
    for key in ('scope','stock_effect','assets','staffing','parts_totals','model_applicability'):
        if now.get(key)!=then.get(key):
            raise ValueError('승인 뒤 실제 정비 범위·패키지·운전시간·부품·인원 조건이 변경되었습니다')
    return current
