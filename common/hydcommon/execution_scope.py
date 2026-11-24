"""Execution cannot turn source-only documentation into an approved action."""
from .maintenance_policy import PM_PATTERN


def require_decision_option(decision, option):
    """판단 장부의 카드 하나를 승인 · 실행해도 되는가. 판단과 카드 둘 다 판단 엔진이 실행 준비를 검사했다는 표시(evaluation_mode ·
    execution_checked)를 실어야 한다 — 판단을 등록하는 길은 판단 엔진 하나이고(agentsvc decide → cards.evaluate) 늘 싣는다. 표시가 없는 판단 ·
    카드는 검사한 적이 없는 것이라 열린 쪽으로 통과시키지 않는다(전에는 표시가 둘 다 없으면 검사 없이 통과했다 — 전수검사 13A-3).
    흐름의 승인 단계가 고른 안(판단 장부 밖 — 학생 에이전트의 제안)은 require_executable 이 본다."""
    for what, item in (('판단', decision), ('조치 후보', option)):
        if 'evaluation_mode' not in item and 'execution_checked' not in item:
            raise ValueError(f'이 {what}에는 실행 준비를 검사했다는 표시가 없어 승인·실행할 수 없습니다 — 판단 엔진이 등록한 판단만 승인합니다')
    require_executable({key: decision[key] for key in ('evaluation_mode','execution_checked') if key in decision})
    pattern = ((decision.get('origin') or {}).get('pattern') or
               (decision.get('scenario') or {}).get('pattern') or
               (decision.get('facts') or {}).get('pattern') or option.get('pattern'))
    require_executable(dict(option, pattern=pattern))


def require_executable(option):
    if option.get('evaluation_mode') == 'rule_analysis' or option.get('execution_checked') is False:
        raise ValueError('규칙 비교 결과는 실제 실행 준비를 검사하지 않아 승인·실행할 수 없습니다')
    if ('evaluation_mode' in option or 'execution_checked' in option) and (
            option.get('evaluation_mode') != 'execution' or option.get('execution_checked') is not True):
        raise ValueError('명시한 실행 검사 모드·확인 상태가 올바르지 않습니다')
    if option.get('kind') == 'reference' or option.get('executable') is False:
        raise ValueError('참고 보관 절차는 승인하거나 설비·업무 조치로 실행할 수 없습니다')
    if option.get('pattern') == PM_PATTERN and (
            option.get('evaluation_mode') != 'execution' or option.get('execution_checked') is not True
            or not isinstance(option.get('maintenancePlan'), dict)):
        raise ValueError('PM 실행에는 검증된 실제 정비 정책·전체 범위 계획이 필요합니다')
    if option.get('pattern') == PM_PATTERN:
        from .maintenance_policy import policy
        approved = option['maintenancePlan']
        policy(approved.get('policy'))
        if approved.get('code') not in ('WO_CREATE','WO_RESCHEDULE') or not approved.get('assets'):
            raise ValueError('PM 실제 실행 범위와 오더 효과가 없습니다')
