"""에이전트 설정 · 스킬 읽기(procsvc/agents_store.py) — 워커가 실행마다 읽는 한 곳. 「이 실행이 실제로 쓰는 도구 서버」 규칙(run_servers)도 여기 하나다."""
import pytest

from hydcommon.handover_tools import HANDOVER_READS, QUESTION_READS
from procsvc import agents_store
from worker.settings import PROVIDER

TENANT_SERVERS = ['neo4j', 'enterprise', 'hyd-dmn', 'enterprise-maint', 'enterprise-purchase', 'my-rows']


def _settings(profile=None, **fields):
    return agents_store.AgentSettings(agent_id='agent:cooling', profile=profile, **fields)


def test_배정된_스킬은_워커_CLI가_찾는_자리의_SKILL_파일로_지시에_실린다():
    skills = [{'skill_name': 'fan-max', 'description': '팬 최대', 'content': '# 팬'}, {'skill_name': 'load-cut', 'content': '# 부하'}]
    text = _settings(profile={'username': '냉각 담당', 'role': 'agent', 'goal': '원인 정리'}, skills=skills).instructions()
    root = agents_store.SKILL_ROOTS[PROVIDER]                    # 워커가 실행하는 CLI 의 스킬 자리
    assert '- 역할: AI 에이전트' in text and '- 목표: 원인 정리' in text
    assert f'- `fan-max`: 팬 최대 — `{root}/fan-max/SKILL.md`' in text and f'`{root}/load-cut/SKILL.md`' in text


def test_프로필도_스킬도_없는_작업은_지시를_더하지_않는다():
    assert _settings().instructions() == ''


@pytest.mark.parametrize('tools, contract, expected', [
    (None, None, {s: None for s in TENANT_SERVERS}),                                    # 지정 없음 = 등록된 서버 전부
    (['neo4j', 'my-rows'], None, {'neo4j': None, 'my-rows': None}),
    (['neo4j', 'not-registered'], None, {'neo4j': None}),                               # 등록 안 된 이름은 빠진다
    ([], None, {}),                                                                     # 에이전트와 단계 선언이 겹치지 않음
    (None, agents_store.QUESTION_CONTRACT, {s: list(QUESTION_READS[s]) for s in QUESTION_READS}),
    (['enterprise-maint', 'hyd-dmn'], agents_store.QUESTION_CONTRACT, {'hyd-dmn': list(QUESTION_READS['hyd-dmn'])}),   # 조회 도구 표 밖 서버는 질문에 쓰지 않는다
    (['my-rows', 'neo4j'], agents_store.HANDOVER_CONTRACT, {'neo4j': list(HANDOVER_READS['neo4j'])}),
], ids=['지정 없음', '에이전트 도구', '등록 안 된 이름', '겹침 없음', '질문 지정 없음', '질문 표 밖 서버', '교대 초안'])
def test_실행이_쓰는_도구_서버는_선택과_단계의_정해진_조회_도구로_정한다(tools, contract, expected):
    assert agents_store.run_servers(tools, TENANT_SERVERS, contract) == expected


def _student(url, read_tools, *, stale=False):
    """학생이 등록한 서버의 설정 — 연결 검사가 그 설정에 찍은 도장(mcp_registry.gate_of 꼴)과 함께. stale: 검사한 뒤 설정이 바뀜."""
    from procsvc import mcp_registry
    spec = {'type': 'http', 'url': url}
    stamp = {'fingerprint': mcp_registry.fingerprint(spec), 'read_tools': read_tools, 'blocked_tools': ['place_order']}
    return dict(spec, url=url + ('/v2' if stale else ''), hyd={'origin': 'user', 'gate': stamp})


@pytest.mark.parametrize('contract, table', [(agents_store.QUESTION_CONTRACT, QUESTION_READS), (agents_store.HANDOVER_CONTRACT, HANDOVER_READS)],
                         ids=['질문', '교대 초안'])
def test_정해진_조회_단계도_학생이_등록하고_읽기_도구를_검사받은_서버는_그_도장의_읽기_도구로_쓴다(contract, table):
    """탐사 S: 정해진 조회 도구 표는 기본 제공 서버의 것이라(수업 녹화가 쓰는 도구), 학생 에이전트에게 물어도 학생 서버가 빠졌다. 학생 서버는
    흐름 단계처럼 연결 검사가 지금 설정에 찍은 읽기 도구로 쓴다(None — 워커가 그 도장으로 허용). 도장이 없거나 설정이 바뀐 서버, 표에 없는 기본
    제공 서버는 그대로 빠진다."""
    servers = {'neo4j': {'type': 'http', 'url': 'http://neo4j-mcp/mcp'}, 'enterprise-maint': {'type': 'http', 'url': 'http://maint/mcp'},
               'my-stock': _student('http://host.docker.internal:8311/mcp', ['find_stock']),
               'my-old': _student('http://host.docker.internal:8312/mcp', ['find_stock'], stale=True),
               'my-unchecked': {'type': 'http', 'url': 'http://host.docker.internal:8313/mcp', 'hyd': {'origin': 'user'}}}
    plan = agents_store.run_servers(None, servers, contract)
    assert plan == {'neo4j': list(table['neo4j']), 'my-stock': None}, plan
    assert agents_store.stamped_reads(servers, 'my-stock') == ['find_stock'] and agents_store.stamped_reads(servers, 'my-old') == []


def test_단계의_폼_계약을_정의에서_읽는다():
    definition = {'activities': [{'id': 'task:draft', 'tool': 'formHandler:handover_draft', 'tools': ['neo4j']}, {'id': 'task:other'}],
                  'forms': {'handover_draft': {'contract': agents_store.HANDOVER_CONTRACT}}}
    assert agents_store.activity_capabilities(definition, 'task:draft') == {
        'agent_config': {}, 'skills': [], 'tools': ['neo4j'], 'contract': agents_store.HANDOVER_CONTRACT}
    assert agents_store.activity_capabilities(definition, 'task:other')['contract'] is None
    assert agents_store.activity_capabilities(definition, 'task:none') == {}


@pytest.mark.parametrize('value, expected', [('a, b,,c ', ['a', 'b', 'c']), (['a', ' ', 'b'], ['a', 'b']), (None, []), (3, [])],
                         ids=['쉼표 글', '목록', '없음', '다른 형'])
def test_도구_칸은_쉼표_글과_목록을_같은_이름_목록으로_읽는다(value, expected):
    assert agents_store.csv_list(value) == expected


@pytest.mark.parametrize('content, expected', [
    ('---\nname: fan-max\ndescription: 팬\n---\n# 본문\n', '---\nname: fan-max\ndescription: 팬\n---\n# 본문\n'),
    ('# 본문', '---\nname: fan-max\ndescription: 팬 최대\n---\n\n# 본문\n'),
], ids=['머리말 있음', '본문만'])
def test_스킬_파일은_머리말이_없으면_이름과_설명을_붙여_쓴다(content, expected):
    assert agents_store.skill_markdown({'skill_name': 'fan-max', 'description': '팬 최대', 'content': content}) == expected
