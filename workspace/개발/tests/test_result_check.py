"""결과 검사 도구(worker/result_check.py) — output/result.json 의 JSON 문법만 본다(의미 검증 아님). 읽기는 결과 해석과 같은 엄격한 함수."""
import pytest

from worker import result_check


@pytest.mark.parametrize('content, ok, needle', [
    ('{"a": 1}', True, None),
    ('{"a": NaN}', False, '비표준 상수'),
    ('{"a": [1, 2}', False, None),
    ('[1]', False, '최상위는 JSON 객체'),
    (b'\xff\xfe', False, 'UTF-8'),
], ids=['정상', 'NaN', '괄호 어긋남', '객체 아님', 'UTF-8 아님'])
def test_결과_파일_문법을_판정하고_틀린_자리를_알린다(tmp_path, content, ok, needle):
    target = tmp_path / 'output' / 'result.json'
    target.parent.mkdir()
    target.write_bytes(content if isinstance(content, bytes) else content.encode('utf8'))
    out = result_check.check(tmp_path, 1000)
    assert out['ok'] is ok
    if needle:
        assert needle in out['error']
    if content == '{"a": [1, 2}':
        assert out['line'] == 1 and '불일치' in out['hint']


def test_크기_상한을_넘거나_파일이_없으면_읽지_않는다(tmp_path):
    assert result_check.check(tmp_path, 10)['ok'] is False
    (tmp_path / 'output').mkdir()
    (tmp_path / 'output' / 'result.json').write_text('{"a": "' + 'x' * 50 + '"}', encoding='utf8')
    assert result_check.check(tmp_path, 10)['error'] == '결과 파일 크기 상한 초과'


def test_창구는_학생_서버가_같은_이름을_써도_워커_것으로_덮는다(tmp_path):
    config = result_check.attach({'mcpServers': {result_check.SERVER: {'url': 'http://x'}}}, tmp_path, 1000)
    entry = config['mcpServers'][result_check.SERVER]
    assert entry['args'][:2] == ['-m', 'worker.result_check'] and 'url' not in entry
