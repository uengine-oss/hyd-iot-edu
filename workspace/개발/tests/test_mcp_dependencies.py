"""흐름 가져오기의 도구 호출 단계 사전 진단(procsvc/mcp_dependencies.py) — 저장된 검사 기록만 읽고 서버를 부르지 않는다."""
import pytest

from procsvc import mcp_dependencies, mcp_registry

ENTRY = {'type': 'url', 'url': 'http://h/mcp', 'transport': 'streamable_http'}
RECORD_OK = {'fingerprint': mcp_registry.fingerprint(ENTRY), 'status': 'ok',
             'tools': [{'name': 'find_rows', 'read_only': True, 'confirmable': False}, {'name': 'search', 'read_only': False, 'confirmable': True},
                       {'name': 'save', 'read_only': False, 'confirmable': False}]}
PARSED = {'tasks': [{'id': 'T1', 'name': '찾기'}]}


def mapping(server, tool, effect=False):
    return {'tasks': {'T1': {'part': 'svc:mcp-call', 'config': {'server': server, 'tool': tool, 'effect': effect}}}}


@pytest.mark.parametrize('server, tool, effect, servers, checks, status', [
    ('', '', False, {}, {}, 'needs_check'),
    ('neo4j', 'read_neo4j_cypher', False, {}, {}, 'internal'),
    ('my-rows', 'find_rows', False, {}, {}, 'missing_server'),
    ('my-rows', 'find_rows', False, {'my-rows': ENTRY}, {}, 'needs_check'),                                   # 검사 전
    ('my-rows', 'find_rows', False, {'my-rows': dict(ENTRY, url='http://other/mcp')}, {'my-rows': RECORD_OK}, 'needs_check'),   # 검사 뒤 바뀜
    ('my-rows', 'nope', False, {'my-rows': ENTRY}, {'my-rows': RECORD_OK}, 'missing_tool'),
    ('my-rows', 'search', False, {'my-rows': ENTRY}, {'my-rows': RECORD_OK}, 'read_unconfirmed'),
    ('my-rows', 'save', True, {'my-rows': ENTRY}, {'my-rows': RECORD_OK}, 'saved_check'),                     # 승인 뒤 쓰기 단계
    ('my-rows', 'find_rows', False, {'my-rows': ENTRY}, {'my-rows': RECORD_OK}, 'saved_check'),
], ids=['서버 · 도구 없음', '수업 기본 연결', '등록 안 된 서버', '검사 전', '검사 뒤 설정 바뀜', '없는 도구', '읽기 확인 안 됨', '쓰기 단계', '통과'])
def test_도구_호출_단계마다_저장된_검사로_무엇을_해야_하는지_말한다(server, tool, effect, servers, checks, status):
    out = mcp_dependencies.diagnose(PARSED, mapping(server, tool, effect), servers, checks, internal_names=('neo4j',))
    [row] = out['items']
    assert (row['node_name'], row['status']) == ('찾기', status)
    assert out['attention_count'] == (0 if status in ('saved_check', 'internal') else 1)
    assert out['blocking'] is False and out['input_schema_verified'] is False


def test_도구_호출이_아닌_단계는_진단하지_않는다():
    out = mcp_dependencies.diagnose(PARSED, {'tasks': {'T1': {'part': 'svc:notify'}}}, {}, {})
    assert (out['items'], out['attention_count']) == ([], 0)


@pytest.mark.parametrize('task, as_mapping, called', [
    ({'part': 'svc:mcp-call', 'config': {'server': 'my-rows', 'tool': 'save'}}, True, ('my-rows', 'save')),
    ({'tool': 'mcp:call', 'service': {'server': 'my-rows', 'tool': 'save'}}, False, ('my-rows', 'save')),
    ({'part': 'svc:mcp-call', 'config': {}}, True, ('', '')),                               # 아직 적지 않은 칸
    ({'part': 'svc:report', 'config': {'server': 'my-rows'}}, True, None),                  # 다른 부품의 같은 이름 칸
    ({'tool': 'formHandler:approve', 'service': {'server': 'my-rows'}}, False, None),
    ({'tool': 'mcp:call', 'service': {'server': 'my-rows', 'tool': 'save'}}, True, None),   # 등록된 정의의 모양을 초안으로 읽지 않는다
], ids=['초안의 호출 단계', '등록된 정의의 호출 단계', '빈 설정', '다른 부품', '사람 승인', '모양이 다른 쪽'])
def test_흐름_단계가_부르는_서버와_도구는_초안과_등록된_정의_두_모양에서_같은_판정으로_읽는다(task, as_mapping, called):
    """흐름 검사(diagnose)와 도구 서버 지우기 전 확인(steps_using)이 이 한 함수를 쓴다 — 「승인 뒤 MCP 호출」 단계만 서버를 부른다."""
    assert mcp_dependencies.call_of(task, mapping=as_mapping) == called
