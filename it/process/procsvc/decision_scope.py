"""Bind a submitted decision to the exact producing work item and generation.

The consumer is a claim fence, not user authentication. Generation-zero legacy
submissions remain explicit compatibility; rework requires a claimed producer.
"""
from . import engine


def expected(inst, workitem):
    return {'tenant': inst['tenant_id'], 'instance': inst['proc_inst_id'], 'workitem': workitem['id'],
            'generation': int(workitem.get('generation') or 0), 'version': workitem.get('version')}


def validate_submission(inst, defn, workitem, scope):
    if not isinstance(scope, dict):
        raise ValueError('새 판단에는 생산 작업과 세대의 process_scope가 필요합니다')
    if (not workitem or workitem.get('tenant_id') != inst['tenant_id']
            or workitem.get('proc_inst_id') != inst['proc_inst_id']
            or workitem.get('version') != inst['proc_def_version']):
        raise ValueError('판단을 생산할 작업의 소유권/판본이 일치하지 않습니다')
    if type(scope.get('generation')) is not int or any(scope.get(k) != v for k, v in expected(inst, workitem).items()):
        raise ValueError('판단의 작업/세대/정의 판본이 일치하지 않습니다')
    if inst.get('status') != 'RUNNING' or inst.get('is_deleted'):
        raise ValueError('종료된 인스턴스의 판단을 접수할 수 없습니다')
    if scope['generation'] != int(inst.get('rework_generation') or 0):
        raise ValueError('이전 세대의 판단을 새 세대에 접수할 수 없습니다')
    if (workitem['status'] != 'IN_PROGRESS' or workitem.get('draft_status') != 'STARTED'
            or not workitem.get('consumer') or scope.get('consumer') != workitem.get('consumer')):
        raise ValueError('현재 판단 작업의 유효한 worker claim이 필요합니다')
    activity = defn.activities.get(workitem['activity_id']) or {}
    if workitem.get('agent_orch') != 'cliagents' or 'decision_id' not in activity.get('outputData', []):
        raise ValueError('판단 ID를 출력하는 에이전트 작업만 판단을 등록할 수 있습니다')


def validate_output(inst, workitem, decision):
    if not isinstance(decision, dict):
        raise ValueError('작업 결과의 판단 원문을 찾을 수 없습니다')
    values = engine.variables(inst)
    origin = decision.get('origin') or {}
    scope = origin.get('process_scope') or {}
    if (origin.get('incident') != values.get('incident') or decision.get('asset') != values.get('asset')
            or any(scope.get(k) != v for k, v in expected(inst, workitem).items())):
        raise ValueError('이 작업·세대가 새로 제출한 판단 ID가 아닙니다')
    if decision.get('state') != 'PENDING_APPROVAL':
        raise ValueError('이미 처리한 판단을 새 판단 작업의 결과로 재사용할 수 없습니다')
