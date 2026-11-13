"""AI 결과 해석(worker/outcome.py) — 결과 파일이 있으면 그것이 결과, 없으면 마지막 메시지. 폼이 없는 단계도 같은 규칙, JSON 은 엄격하게."""
import json

import pytest

from worker import outcome
from worker.context import FREEFORM_FIELDS

FORM = [{'key': 'cause', 'label': '원인'}, {'key': 'score', 'label': '점수'}]


def interpret(tmp_path, text, fields, file=None):
    result = tmp_path / 'output' / 'result.json'
    if file is not None:
        result.parent.mkdir(parents=True, exist_ok=True)
        result.write_text(file, encoding='utf8')
    return outcome.interpret(text, fields, result_file=result)


def test_폼이_없는_단계도_결과_파일에_쓴_답이_결과다(tmp_path):
    """G1-01: 자유형식 단계가 파일을 보기 전에 메시지로 끝내 「파일을 썼습니다」 한 줄이 결과로 저장되고 실제 답은 72시간 뒤 지워졌다."""
    out = interpret(tmp_path, '결과를 output/result.json에 작성했습니다.', FREEFORM_FIELDS, json.dumps({'freeform': '쿨러 핀을 세척하세요'}))
    assert out.contract_met and out.source == 'file' and out.outputs == {'freeform': '쿨러 핀을 세척하세요'}


@pytest.mark.parametrize('text, outputs', [('{"freeform": "답"}', {'freeform': '답'}), ('그냥 글로 쓴 답', {})],
                         ids=['메시지 JSON', '메시지 글'])
def test_폼이_없는_단계의_메시지_답은_JSON_이면_칸으로_글이면_글로_받는다(tmp_path, text, outputs):
    out = interpret(tmp_path, text, FREEFORM_FIELDS)
    assert out.contract_met and out.outputs == outputs and out.raw_text == text


@pytest.mark.parametrize('file, needle', [
    ('{"cause": "c", "score": NaN}', 'NaN'),
    ('{"cause": "c", "score": Infinity}', 'Infinity'),
    ('{"cause": "c", ', '올바른 JSON이 아닙니다'),
    ('[1, 2]', '최상위가 JSON 객체가 아닙니다'),
], ids=['NaN', 'Infinity', '문법 오류', '객체 아님'])
def test_결과_파일의_비표준_숫자_상수와_문법_오류는_교정_사유로_돌려보낸다(tmp_path, file, needle):
    """G1-19: NaN 을 받아들여 업무 DB(jsonb) 저장에서 일반 실패가 됐고, 결과 검사 도구는 같은 파일을 거절해 판정이 갈렸다."""
    out = interpret(tmp_path, '파일을 썼습니다', FORM, file)
    assert not out.contract_met and needle in out.mismatch_reason and out.source == 'file'


def test_폼_칸이_비면_그_칸_이름으로_돌려보낸다(tmp_path):
    out = interpret(tmp_path, json.dumps({'cause': 'c', 'score': ''}), FORM)
    assert not out.contract_met and out.missing_fields == ['score']


def test_결과가_없으면_결과가_없다고_한다(tmp_path):
    assert interpret(tmp_path, '  ', FORM).mismatch_reason == outcome.NO_RESULT


def test_메시지_안의_마지막_JSON_객체를_결과로_읽는다(tmp_path):
    out = interpret(tmp_path, '설명입니다.\n```json\n{"cause": "a", "score": 1}\n```\n끝', FORM)
    assert out.contract_met and out.outputs == {'cause': 'a', 'score': 1}


def test_결과_파일에_쓴_보류는_보류로_읽는다(tmp_path):
    (tmp_path / 'r.json').write_text(json.dumps({'__deferred__': {'status': 'UNKNOWN', 'reason': '근거 없음'}}), encoding='utf8')
    assert '__deferred__' in outcome.deferral_in_result_file(tmp_path / 'r.json')
    (tmp_path / 'r.json').write_text('{"cause": "a"}', encoding='utf8')
    assert outcome.deferral_in_result_file(tmp_path / 'r.json') is None
