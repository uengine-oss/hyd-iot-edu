"""Form-owned correction guidance; never apply extraction rules to other forms."""

ASK_INSTRUCTIONS = (
    'status는 answered 또는 cannot_answer입니다. answered이면 answer와 evidence를 제출하세요. '
    'evidence의 각 항목은 {"tool": "서버/도구", "query": 실행한 질의 또는 인자, "result": 조회 결과 요약}입니다. '
    'tool에는 실제 서버/도구 이름(또는 mcp__서버__도구)을 쓰세요. SQL·Cypher 같은 질의는 실행한 전체 문자열 그대로, '
    '일반 MCP 도구는 실제 호출의 전체 arguments JSON 객체를 query에 쓰세요. 인자 없는 호출은 {}이며, '
    '중첩 값·숫자·불리언·배열 타입과 생략 여부를 그대로 보존하세요. 성공한 호출만 인용하며 도구·인자·결과를 지어내지 마세요. '
    '근거를 얻지 못했다면 cannot_answer와 reason을 제출하세요.'
)


def instructions(contract):
    return ASK_INSTRUCTIONS if contract == 'ask-answer-v1' else ''


def guidance(form):
    contract = (form or {}).get('contract')
    if contract == 'manual-source-proposal-v1':
        return ('추출 제안', '원문 검증',
                '입력 데이터의 이전 proposal을 고쳐 같은 형식으로 다시 제출하세요. 인용(anchor)은 page.text의 '
                '정확한 부분 문자열과 좌표여야 하며, 모든 페이지에 page_reviews가 있어야 합니다. 원문에 없는 절차를 추가하지 마세요.')
    if contract == 'ask-answer-v1':
        return '질문 답변', '답변 계약 검사', ASK_INSTRUCTIONS
    if contract == 'manual-golden-report-v1':
        return ('문서 질문 보고', '보고 계약 검사',
                '입력 golden_request의 질문에 맞춰 이전 golden_report를 수정하세요. 문서에서 확인한 답과 근거만 제출하고 확인하지 못한 이유를 명시하세요.')
    if contract == 'legacy-meaning-candidates-v1':
        return ('열 의미 후보', '의미 후보 계약 검사',
                '입력 legacy_request의 열에 맞춰 이전 meanings를 수정하세요. 관찰한 원문·표본·주석에 근거한 후보와 확신도를 제출하고 확정하지 마세요.')
    return '작업 결과', '출력 계약 검사', '이전 결과를 해당 폼의 필드와 검사 사유에 맞춰 수정해 다시 제출하세요.'
