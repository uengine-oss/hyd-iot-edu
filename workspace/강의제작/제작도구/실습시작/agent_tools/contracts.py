"""모델 응답과 점검 계획의 구조만 확인한다. 업무 판단은 학생 기능이다."""
import json
import re

def model_json(text):
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text)
    value = json.loads(text)
    if not isinstance(value, dict): raise ValueError('모델 응답은 JSON 객체여야 합니다.')
    if sum(key in value for key in ['tool','calls','finish']) != 1: raise ValueError('tool, calls, finish 중 하나를 반환해야 합니다.')
    if 'calls' in value and (not isinstance(value['calls'],list) or not value['calls']): raise ValueError('calls는 비어 있지 않은 도구 요청 목록입니다.')
    return value


def structural_errors(plan, ledger):
    errors = []
    questions = plan.get('delivery_questions', [])
    if not isinstance(questions, list) or any(not isinstance(q, dict) or not q.get('recipient') or not q.get('question') for q in questions):
        errors.append('전달 요구 질문은 recipient/question을 가진 목록이어야 합니다.')
    if questions and plan.get('next_checks'): errors.append('전달 요구가 미정인 결과에 최종 다음 점검을 함께 넣을 수 없습니다.')
    for name in ['request_id', 'asset', 'as_of', 'candidates', 'next_checks', 'unresolved', 'delivery_reason']:
        if name not in plan: errors.append(f'계획 필수 칸 없음: {name}')
    valid_refs = {item['id'] for item in ledger}
    seen = set()
    for number, item in enumerate(plan.get('candidates', []), 1):
        identity = item.get('cause_id')
        if not identity or identity in seen: errors.append(f'후보 {number}: ID 없음/중복')
        seen.add(identity)
        if item.get('status') not in ['충족', '해당 없음', '보류']: errors.append(f'후보 {number}: 증거 대조 값 꼴 불일치')
        if not item.get('reason'): errors.append(f'후보 {number}: 이유 없음')
        refs = item.get('evidence_refs', [])
        if not isinstance(refs, list) or set(refs)-valid_refs: errors.append(f'후보 {number}: 없는 도구 반환 참조')
    for number, item in enumerate(plan.get('next_checks', []), 1):
        for key in ['recipient', 'action', 'preconditions', 'evidence_refs']:
            if key not in item: errors.append(f'다음 점검 {number}: {key} 없음')
        if set(item.get('evidence_refs', []))-valid_refs: errors.append(f'다음 점검 {number}: 없는 도구 반환 참조')
    return errors

