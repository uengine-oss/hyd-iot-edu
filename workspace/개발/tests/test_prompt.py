"""AI 지시문(worker/prompt.py) — 업무 · 지시(입력 [InputData] 포함) · 앞서 낸 결과 · 피드백 · 결과 제출 형식."""
import json

import pytest

from worker import prompt

ROW = {'activity_name': '원인 진단', 'query': '진단하라\n[InputData] {"asset": "HYD-01"}'}
FORM = [{'key': 'cause', 'label': '원인', 'type': 'text'}, {'key': 'approve', 'label': '승인', 'items': [{'yes': '예'}, {'no': '아니오'}]}]


@pytest.mark.parametrize('output, expect', [
    (None, None), ({'cliagents_session_id': 's'}, None), ({'cause': 'c', 'cliagents_session_id': 's'}, {'cause': 'c'}), ('{"a": 1}', {'a': 1}),
], ids=['첫 실행', '세션 id 만', '앞서 낸 결과', '글로 저장된 JSON'])
def test_앞서_낸_결과는_작업_행_결과에서_세션_id_를_빼고_읽는다(output, expect):
    """G1-27: 「입력 데이터」(context/input.json)는 실제 입력이 아니라 이 값(+ 진행 중 초안)이었고 첫 실행마다 null 파일을 읽게 했다."""
    assert prompt.previous_result({'output': output, 'draft': {'cliagents_session_id': 'x'}}) == expect


def test_첫_실행의_지시문에는_앞서_낸_결과_칸이_없고_입력은_지시의_InputData_라고_말한다():
    text = prompt.build(ROW, {'form_fields': FORM}, workdir='/w')
    assert '## 이 작업이 앞서 낸 결과' not in text and 'context/input.json' not in text and '[InputData]' in text
    assert prompt.PREVIOUS_RESULT_FILE in text and '(A158)' not in text      # runner 가 쓰는 그 파일 이름(G1-27 — 상수 한 곳)


def test_재작업_지시문에는_앞서_낸_결과와_피드백이_있다():
    text = prompt.build(dict(ROW, output={'cause': '이전'}), {'form_fields': FORM, 'summarized_feedback': '근거가 약함'}, workdir='/w')
    assert '## 이 작업이 앞서 낸 결과\n{\n  "cause": "이전"\n}' in text and '근거가 약함' in text


def test_결과_형식은_칸_허용값_골격을_싣고_파일과_메시지_두_길을_말한다():
    contract = prompt.output_contract(FORM)
    assert '`approve`: 승인' in contract and '`yes`(예)' in contract and 'output/result.json' in contract
    assert json.loads(contract.split('```json\n')[1].split('\n```')[0]) == {'cause': '', 'approve': ''}
    assert prompt.output_contract([]) .startswith('## 결과 제출 형식\n작업을 마치면 마지막 메시지에')


def test_긴_앞선_결과는_잘라_보이고_전체는_파일에_있다고_말한다():
    big = {'text': 'x' * (prompt.INLINE_INPUT_LIMIT + 100)}
    text = prompt.build(dict(ROW, output=big), {}, workdir='/w')
    assert '[잘림: ' in text and prompt.PREVIOUS_RESULT_FILE in text
