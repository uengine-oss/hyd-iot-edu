"""Shift handover contracts. Confirmation records communication, never repairs."""
from datetime import datetime

from . import ask

DEFINITION_ID = 'shift_handover'
DRAFT = 'shift-handover-draft-v1'
SENDER = 'shift-handover-sender-v1'
RECEIVER = 'shift-handover-receiver-v1'
AREAS = {'equipment', 'work_orders', 'parts', 'work_notes'}


def optional_inputs(form):
    contract = (form or {}).get('contract')
    return {'sender_notes', 'receiver_notes'} if contract == DRAFT else {'receiver_notes'} if contract == SENDER else set()


def validate_start(values):
    allowed = {'asset', 'shift_label', 'as_of', 'work_notes'}
    if not isinstance(values, dict) or set(values) != allowed:
        raise ValueError('인수인계 시작에는 설비·교대·기준시각·작업 메모만 입력하세요')
    for key, maximum in [('asset', 80), ('shift_label', 120), ('work_notes', 4000), ('as_of', 80)]:
        value = values[key]
        if not isinstance(value, str) or not value.strip() or len(value)>maximum:
            raise ValueError('인수인계 시작 입력이 비어 있거나 한도를 넘었습니다: '+key)
    try:
        moment = datetime.fromisoformat(values['as_of'].replace('Z', '+00:00'))
        if moment.utcoffset() is None: raise ValueError()
    except ValueError:
        raise ValueError('기준시각에는 시간대가 포함된 ISO 시각을 입력하세요') from None


def validate_result(form, inst, output):
    contract = (form or {}).get('contract')
    if contract == DRAFT:
        if set(output) != {'handover_summary', 'checks', 'evidence'}:
            raise ValueError('인계안은 handover_summary·checks·evidence만 제출하세요')
        checks, evidence = output['checks'], output['evidence']
        if not isinstance(checks, list) or len(checks) != 4 or \
                any(not isinstance(c, dict) for c in checks) or {c.get('area') for c in checks} != AREAS:
            raise ValueError('설비·열린 작업지시·부품·작업 메모를 각각 한 번씩 확인하세요')
        if not isinstance(evidence, list) or len(evidence)>40:
            raise ValueError('조회 근거는 40개 이하 목록이어야 합니다')
        if evidence:
            ask.validate_answer(dict(status='answered', answer=output['handover_summary'], evidence=evidence))
        for check in checks:
            if set(check) != {'area', 'state', 'finding', 'next_action', 'evidence_indices'}:
                raise ValueError('각 확인 항목에는 area·state·finding·next_action·evidence_indices가 필요합니다')
            if check['state'] not in ('observed', 'needs_check', 'conflict'):
                raise ValueError('확인 상태는 observed·needs_check·conflict 중 하나입니다')
            if any(not isinstance(check[k], str) or not check[k].strip() or len(check[k])>2000 for k in ('finding', 'next_action')):
                raise ValueError('확인 사실과 다음 근무자가 확인할 일을 구체적으로 적으세요')
            refs = check['evidence_indices']
            if not isinstance(refs, list) or any(type(i) is not int or not 0 <= i < len(evidence) for i in refs):
                raise ValueError('근거 번호는 evidence의 0부터 시작하는 유효한 번호여야 합니다')
            if check['state'] != 'needs_check' and check['area'] != 'work_notes' and not refs:
                raise ValueError('조회 근거가 없으면 확인 필요(needs_check)로 남기세요')
    elif contract in (SENDER, RECEIVER):
        prefix = 'sender' if contract == SENDER else 'receiver'
        decision = output.get(prefix+'_decision')
        choices = ('approve', 'revise', 'reject') if contract == SENDER else ('confirm', 'revise')
        if decision not in choices:
            raise ValueError('인수인계 검토 선택이 올바르지 않습니다')
        note = output.get(prefix+'_notes')
        if not isinstance(note, str) or not note.strip() or len(note)>2000:
            raise ValueError('확인 사항 또는 보완·거절 사유를 적으세요')
        if contract == RECEIVER and decision == 'confirm' and output.get('communication_only') is not True:
            raise ValueError('인계 확인은 설비 조치·발주·정비 완료가 아님을 확인하세요')


def validate_trace(repo, wi, form, output):
    if (form or {}).get('contract') != DRAFT or not output.get('evidence'):
        return
    calls = ask.tool_calls(repo.list_events(todo_id=wi['id']), repo.get_event_payload)
    verdict = ask.verdict(dict(answer=output['handover_summary'], evidence=output['evidence']), calls)
    evidence = verdict.get('evidence') or []
    if len(evidence) != len(output['evidence']) or any(not e['verified'] for e in evidence):
        raise ValueError('인계안의 모든 조회 근거가 현재 작업의 성공한 실제 도구 호출과 일치해야 합니다')
