"""Execution cannot turn source-only documentation into an approved action."""


def require_decision_option(decision, option):
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
    if option.get('pattern') == 'PM_DUE' and (
            option.get('evaluation_mode') != 'execution' or option.get('execution_checked') is not True
            or not isinstance(option.get('maintenancePlan'), dict)):
        raise ValueError('PM 실행에는 검증된 실제 정비 정책·전체 범위 계획이 필요합니다')
    if option.get('pattern') == 'PM_DUE':
        from .maintenance_policy import policy
        approved = option['maintenancePlan']
        policy(approved.get('policy'))
        if approved.get('code') not in ('WO_CREATE','WO_RESCHEDULE') or not approved.get('assets'):
            raise ValueError('PM 실제 실행 범위와 오더 효과가 없습니다')
