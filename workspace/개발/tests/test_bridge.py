"""도구 서버 등록(worker/bridge.py) — 실행마다 작업 폴더 .mcp.json, 검사 도장 관문, 비밀 채우기 · 가림, 끝나면 비밀 지우기."""
import json

import pytest

from procsvc import mcp_registry
from worker import bridge

TOKEN = 'drive-token-' + 'x' * 20
STUDENT = {'type': 'url', 'url': 'http://127.0.0.1:9/mcp', 'headers': {'Authorization': 'Bearer ${SECRET:DRIVE}'}}


def stamped(spec, read_tools=('lookup',), blocked=('write_row',)):
    return dict(spec, hyd={'gate': {'fingerprint': mcp_registry.fingerprint(spec), 'read_tools': list(read_tools), 'blocked_tools': list(blocked)}})


def test_검사_도장의_해시는_process_연결_검사와_같은_계산_하나다():
    """P3-21: 주석은 「시험이 두 계산을 대조한다」였는데 그런 시험이 없었다 — 워커는 이제 process 의 함수를 그대로 쓴다."""
    assert bridge.config_fingerprint is mcp_registry.fingerprint
    assert bridge.config_fingerprint(stamped(STUDENT)) == bridge.config_fingerprint(STUDENT)      # hyd 표시는 해시 밖


@pytest.mark.parametrize('spec, reason', [
    (STUDENT, '연결 검사를 통과하지 않은 서버'),
    (dict(stamped(STUDENT), url='http://127.0.0.1:10/mcp'), '설정이 바뀐 서버'),
    (stamped(STUDENT, read_tools=()), '읽기 전용으로 표시한 도구가 없는 서버'),
], ids=['도장 없음', '검사 뒤 바뀜', '읽기 도구 없음'])
def test_학생_서버는_지금_설정의_도장이_있고_읽기_도구가_있을_때만_붙인다(spec, reason):
    config = bridge.attach_secrets({'mcpServers': {'mine': spec}}, {'DRIVE': TOKEN})
    gate = bridge.gate_servers(config, trusted=set())
    assert gate.config['mcpServers'] == {} and reason in gate.dropped['mine']


def test_비밀_값이_없으면_그_이름과_까닭으로_뺀다():
    config = bridge.attach_secrets({'mcpServers': {'mine': stamped(STUDENT)}}, {}, error='표를 읽지 못함')
    gate = bridge.gate_servers(config, trusted=set())
    assert 'DRIVE' in gate.dropped['mine'] and '표를 읽지 못함' in gate.dropped['mine']


def test_붙인_서버는_비밀을_채워_쓰고_그_비밀은_가림_목록에_들며_끝나면_지운다(tmp_path):
    config = bridge.attach_secrets({'mcpServers': {'mine': stamped(STUDENT), 'hyd-dmn': {'type': 'url', 'url': 'http://dmn/mcp'}}}, {'DRIVE': TOKEN})
    gate = bridge.gate_servers(config, trusted={'hyd-dmn'})
    assert gate.read_tools == {'mine': ['lookup']} and gate.blocked_tools == {'mine': ['write_row']}
    result = bridge.install(tmp_path, gate.config, run_headers={'X-HYD-Process-Scope': '{"w":1}'})
    written = json.loads((tmp_path / '.mcp.json').read_text(encoding='utf8'))['mcpServers']
    assert written['mine'] == {'type': 'http', 'url': 'http://127.0.0.1:9/mcp', 'headers': {'Authorization': f'Bearer {TOKEN}'}}
    assert written['hyd-dmn']['headers'] == {'X-HYD-Process-Scope': '{"w":1}'}                  # 판단 서버에만 실행 범위
    assert TOKEN in result.redaction_values and f'Bearer {TOKEN}' in result.redaction_values
    assert sorted(bridge.cleanup(tmp_path)) == ['hyd-dmn', 'mine']
    assert TOKEN not in (tmp_path / '.mcp.json').read_text(encoding='utf8')


def test_읽을_수_없는_도구_서버_설정은_비밀이_남지_않게_통째로_지운다(tmp_path):
    """G1-24: 깨진 .mcp.json 이면 비밀 지우기를 건너뛰어 72시간 보관하는 작업 폴더에 토큰이 남을 수 있었다."""
    (tmp_path / '.mcp.json').write_text('{"mcpServers": {"mine": {"headers": {"Authorization": "Bearer ' + TOKEN + '"', encoding='utf8')
    assert bridge.cleanup(tmp_path) == ['*'] and not (tmp_path / '.mcp.json').exists()


def test_워커의_명령형_창구는_그대로_쓰고_주소는_호스트_워커용으로_바꾼다(tmp_path):
    window = {'command': 'python', 'args': ['-m', 'worker.question_tools', '--url', 'http://process:8080'], 'env': {'PYTHONPATH': '/srv'}}
    bridge.install(tmp_path, {'mcpServers': {'neo4j': window}}, host_rewrite=bridge.parse_host_rewrite('process:8080=127.0.0.1:18080'))
    entry = json.loads((tmp_path / '.mcp.json').read_text(encoding='utf8'))['mcpServers']['neo4j']
    assert entry == {'command': 'python', 'args': ['-m', 'worker.question_tools', '--url', 'http://127.0.0.1:18080'], 'env': {'PYTHONPATH': '/srv'}}
