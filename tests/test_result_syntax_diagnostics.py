import json

from worker import outcome


def test_result_file_reports_multiple_extra_braces_without_repairing(tmp_path):
    path = tmp_path / 'result.json'
    raw = '{"rows": [\n{"anchor": {"quote": "first"}}},\n{"anchor": {"quote": "second"}}}\n]}'
    path.write_text(raw, encoding='utf-8')
    value, reason = outcome._read_result_file(path, 10000)
    assert value is None and path.read_text(encoding='utf-8') == raw
    assert '⟦오류 위치⟧' in reason
    assert '2행 31열: }' in reason and '3행 32열: }' in reason
    assert '기호는 ]' in reason


def test_syntax_diagnostic_ignores_quoted_braces_and_is_bounded(tmp_path):
    quoted = json.dumps('literal } ] { [ and "escaped" \\ text')
    raw = '{"quote": ' + quoted + ',"rows":[' + ('{"a":1}},' * 10000) + '{}]}'
    path = tmp_path / 'result.json'
    path.write_text(raw, encoding='utf-8')
    value, reason = outcome._read_result_file(path, 200000)
    assert value is None
    assert reason.count('열린 괄호에 맞는 기호는') == 6
    assert len(reason) < 1200 and '⟦오류 위치⟧' in reason
    first_extra = len('{"quote": ' + quoted + ',"rows":[{"a":1}') + 1
    assert f'1행 {first_extra}열: }}' in reason


def test_valid_result_does_not_need_or_modify_diagnostics(tmp_path):
    path = tmp_path / 'result.json'
    expected = {'rows': [{'quote': '닫는 괄호 } 도 원문이다'}]}
    path.write_text(json.dumps(expected, ensure_ascii=False), encoding='utf-8')
    assert outcome._read_result_file(path, 10000) == (expected, '')
