"""정의 판본이 가진 폼 계약(common/hydcommon/process_contracts.py) — 엔진 · 정의 등록 API · AI 워커가 같은 함수로 폼 선언과 단계 결과를 판정한다.

- validate_fields: 폼 칸 선언(fields_json)의 형식 — 등록 때 잘못된 선언을 막는다.
- pinned_form: 단계 도구 `formHandler:<폼>`이 가리키는 폼을 그 정의 판본 안에서 꺼낸다. 폼 선언(forms)이 없는 정의의 폼 도구는 이제
  「검사 없이 통과」(옛 호환 길)가 아니라 오류다(G3b-31 — 저장소 정의는 모두 forms 를 갖고, 등록이 둘 다 요구한다).
- validate_output: 단계 결과가 그 폼의 칸 형식 · 필수 · 선택값에 맞는지.
폼은 저장소의 실제 정의 파일(it/process/definitions)에서 꺼낸다.
"""
import copy
import json
import math

import pytest

from conftest import DEFINITIONS
from hydcommon.process_contracts import pinned_form, validate_fields, validate_output


def _definition(name):
    return json.loads((DEFINITIONS / name).read_text(encoding='utf-8'))


def _form_tools():
    """저장소 정의마다 단계가 부르는 폼 도구 전부."""
    out = []
    for path in sorted(DEFINITIONS.glob('*_v*.json')):
        d = json.loads(path.read_text(encoding='utf-8'))
        out += [(path.name, a['tool']) for a in d.get('activities') or [] if str(a.get('tool', '')).startswith('formHandler:')]
    return out


FORM_TOOLS = _form_tools()


def test_저장소_정의의_폼_도구는_모두_자기_판본_안의_폼을_가리킨다():
    assert len(FORM_TOOLS) >= 10
    for name, tool in FORM_TOOLS:
        form = pinned_form(_definition(name), tool)
        assert form['id'] == tool.split(':', 1)[1]
        validate_fields(form['fields_json'])


@pytest.mark.parametrize('tool', ['mcp:enterprise', 'agent:diagnose', '', None], ids=['MCP 도구', '에이전트', '빈 도구', '도구 없음'])
def test_폼_도구가_아닌_단계는_폼이_없다(tool):
    assert pinned_form(_definition('alert_triage_v1.json'), tool) is None


@pytest.mark.parametrize('change, word', [
    (lambda d: d.pop('forms'), '폼 선언(forms)이 없습니다'),          # G3b-31: 옛 판은 None(검사 없이 저장)
    (lambda d: d.__setitem__('forms', None), '폼 선언(forms)이 없습니다'),
    (lambda d: d.__setitem__('forms', ['alert_triage']), '폼 선언(forms)이 없습니다'),
    (lambda d: d['forms'].pop('alert_triage'), '폼이 없습니다: alert_triage'),
    (lambda d: d['forms'].__setitem__('alert_triage', 'note'), '폼이 없습니다: alert_triage'),
], ids=['forms 없음', 'forms null', 'forms 가 목록', '그 폼 없음', '폼이 객체 아님'])
def test_폼_도구가_가리키는_폼이_판본에_없으면_오류다(change, word):
    d = _definition('alert_triage_v1.json')
    change(d)
    with pytest.raises(ValueError) as caught:
        pinned_form(d, 'formHandler:alert_triage')
    assert word in str(caught.value)


def test_꺼낸_폼은_사본이라_고쳐도_정의_판본이_바뀌지_않는다():
    d = _definition('alert_triage_v1.json')
    before = copy.deepcopy(d)
    form = pinned_form(d, 'formHandler:alert_triage')
    form['fields_json'].append({'key': 'x', 'type': 'text'})
    assert d == before


GOOD_FIELDS = [{'key': 'note', 'type': 'textarea'}, {'key': 'level', 'type': 'select', 'items': ['low', {'high': '높음'}], 'required': False},
               {'key': 'n', 'type': 'integer', 'required': True}]


@pytest.mark.parametrize('fields, word', [
    ({'key': 'a', 'type': 'text'}, '목록'),
    ([{'type': 'text'}], 'key가 필요'),
    ([{'key': '  ', 'type': 'text'}], 'key가 필요'),
    ([{'key': 'a', 'type': 'date'}], '지원하지 않는 폼 타입: date'),
    ([{'key': '__proto__', 'type': 'text'}], '예약된'),
    ([{'key': 'a', 'type': 'text', 'required': 'yes'}], 'boolean'),
    ([{'key': 'a', 'type': 'select'}], 'select items'),
    ([{'key': 'a', 'type': 'select', 'items': []}], 'select items'),
    ([{'key': 'a', 'type': 'select', 'items': [1]}], 'select items'),
    ([{'key': 'a', 'type': 'select', 'items': ['']}], '비어 있지 않은'),
    ([{'key': 'a', 'type': 'select', 'items': [{'': '빈 값'}]}], '비어 있지 않은'),
    ([{'key': 'a', 'type': 'text'}, {'key': 'a', 'type': 'number'}], '중복'),
], ids=['목록 아님', 'key 없음', 'key 공백', '모르는 타입', '예약 key', 'required 글', 'select items 없음', 'select items 빔',
        'select 숫자 항목', 'select 빈 값', 'select 빈 값 객체', 'key 중복'])
def test_잘못된_폼_칸_선언은_까닭과_함께_거절한다(fields, word):
    with pytest.raises(ValueError) as caught:
        validate_fields(fields)
    assert word in str(caught.value)


def test_올바른_폼_칸_선언은_받는다():
    assert validate_fields(GOOD_FIELDS) is None and validate_fields([]) is None


FORM = {'fields_json': [
    {'key': 't', 'type': 'text'}, {'key': 'num', 'type': 'number'}, {'key': 'int', 'type': 'integer'}, {'key': 'flag', 'type': 'boolean'},
    {'key': 'kind', 'type': 'select', 'items': ['keep', {'stop': '정지'}]}, {'key': 'obj', 'type': 'object'}, {'key': 'arr', 'type': 'array'},
    {'key': 'memo', 'type': 'textarea', 'required': False}]}
GOOD = {'t': '설명', 'num': 1.5, 'int': 3, 'flag': False, 'kind': 'stop', 'obj': {}, 'arr': []}


@pytest.mark.parametrize('change', [
    {}, {'num': 2}, {'memo': '메모'}, {'memo': None}, {'memo': '  '}, {'kind': 'keep'}, {'extra': '폼 밖 칸은 검사 대상이 아니다'},
], ids=['기본', '정수도 number', '선택 칸 있음', '선택 칸 null', '선택 칸 공백', '글 선택값', '폼 밖 칸'])
def test_폼에_맞는_결과는_받는다(change):
    assert validate_output(FORM, dict(GOOD, **change)) is None


@pytest.mark.parametrize('change, word', [
    ({'t': None}, '필수 폼 필드가 비어 있습니다: t'),
    ({'t': '   '}, '필수 폼 필드가 비어 있습니다: t'),
    ({'t': 3}, 't (text)'),
    ({'num': True}, 'num (number)'),                  # 참/거짓은 숫자가 아니다
    ({'num': math.nan}, 'num (number)'),
    ({'num': math.inf}, 'num (number)'),
    ({'num': '1.5'}, 'num (number)'),
    ({'int': 3.0}, 'int (integer)'),
    ({'int': True}, 'int (integer)'),
    ({'flag': 0}, 'flag (boolean)'),
    ({'kind': '정지'}, 'kind (select)'),              # 표시명이 아니라 값만 받는다
    ({'kind': 'reduce'}, 'kind (select)'),
    ({'obj': []}, 'obj (object)'),
    ({'arr': {}}, 'arr (array)'),
    ({'memo': 3}, 'memo (textarea)'),
], ids=['필수 null', '필수 공백', '글 칸에 숫자', '숫자 칸에 참거짓', 'NaN', '무한', '숫자 칸에 글', '정수 칸에 소수', '정수 칸에 참거짓',
        '참거짓 칸에 0', 'select 표시명', 'select 밖 값', '객체 칸에 목록', '목록 칸에 객체', '선택 칸 형식'])
def test_폼과_다른_결과는_그_칸과_형식을_말하며_거절한다(change, word):
    with pytest.raises(ValueError) as caught:
        validate_output(FORM, dict(GOOD, **change))
    assert word in str(caught.value)


@pytest.mark.parametrize('output', [None, [], '결과', 3], ids=['null', '목록', '글', '숫자'])
def test_결과가_객체가_아니면_거절한다(output):
    with pytest.raises(ValueError, match='JSON 객체'):
        validate_output(FORM, output)


def test_실제_정의의_선택_폼은_선택값만_받는다():
    """ask_agent 정의의 ask_answer 폼: status 는 select(필수), 나머지는 선택 칸."""
    form = pinned_form(_definition('ask_agent_v1.json'), 'formHandler:ask_answer')
    status = next(f for f in form['fields_json'] if f['key'] == 'status')
    from hydcommon.process_contracts import choices
    allowed = choices(status)
    assert allowed and validate_output(form, {'status': allowed[0]}) is None
    with pytest.raises(ValueError, match='status'):
        validate_output(form, {'status': 'not-a-status'})
    with pytest.raises(ValueError, match='필수 폼 필드가 비어 있습니다: status'):
        validate_output(form, {'answer': '답'})
