"""Neo4j 드라이버를 여는 곳 하나(common/hydcommon/graphdb.py) — 결정 2 · H-2.

규칙: 주소 · 인증은 환경 변수에서만(인증 기본값 없음, 두 꼴이 다르면 거절), 「없는 이름」 알림은 끄고 질의 오류는 그대로 올린다.
알림 · 오류 판정은 실제 Neo4j(compose neo4j 이미지의 버릴 컨테이너 — conftest neo4j_graph)로 잰다.
"""
import asyncio

import neo4j
import pytest

from hydcommon import graphdb


@pytest.mark.parametrize('env, expected', [
    ({'NEO4J_AUTH': 'neo4j/pw'}, ('bolt://neo4j:7687', ('neo4j', 'pw'))),                                   # 주소 없으면 compose 이름
    ({'NEO4J_URI': 'bolt://h:1', 'NEO4J_AUTH': 'u/p/with/slash'}, ('bolt://h:1', ('u', 'p/with/slash'))),   # 비밀번호 안의 / 그대로
    ({'NEO4J_USERNAME': 'u', 'NEO4J_PASSWORD': 'p'}, ('bolt://neo4j:7687', ('u', 'p'))),                    # 도구 서버 설정의 꼴
    ({'NEO4J_AUTH': 'u/p', 'NEO4J_USERNAME': 'u', 'NEO4J_PASSWORD': 'p'}, ('bolt://neo4j:7687', ('u', 'p'))),  # 두 꼴이 같으면 됨
    ({'NEO4J_URI': '', 'NEO4J_AUTH': 'u/p'}, ('bolt://neo4j:7687', ('u', 'p'))),                           # 빈 값 = 없음
])
def test_주소와_인증은_환경_변수_두_꼴에서_읽는다(env, expected):
    assert graphdb.settings(env) == expected


@pytest.mark.parametrize('env, names', [
    ({}, ['NEO4J_AUTH', 'NEO4J_USERNAME']),                                        # 인증 없음 — 코드에 기본 비밀번호가 없다
    ({'NEO4J_AUTH': 'nopassword'}, ['NEO4J_AUTH']),                                # / 없음
    ({'NEO4J_AUTH': '/pw'}, ['NEO4J_AUTH']),                                       # 사용자 빈칸
    ({'NEO4J_AUTH': 'u/'}, ['NEO4J_AUTH']),                                        # 비밀번호 빈칸
    ({'NEO4J_USERNAME': 'u'}, ['NEO4J_PASSWORD']),                                 # 짝이 없음
    ({'NEO4J_PASSWORD': 'p'}, ['NEO4J_USERNAME']),
    ({'NEO4J_AUTH': 'u/p', 'NEO4J_USERNAME': 'u', 'NEO4J_PASSWORD': 'other'}, ['NEO4J_AUTH', 'NEO4J_PASSWORD']),  # 서로 다름
])
def test_인증이_없거나_꼴이_틀리거나_두_꼴이_다르면_변수_이름을_대며_거절한다(env, names):
    with pytest.raises(graphdb.GraphSettingsError) as caught:
        graphdb.settings(env)
    assert all(name in str(caught.value) for name in names), caught.value


def test_동기와_비동기_드라이버를_고른다(neo4j_graph):
    with graphdb.connect() as sync:
        assert isinstance(sync, neo4j.Driver)
        sync.verify_connectivity()

    async def use_async():
        adriver = graphdb.connect(asynchronous=True)
        try:
            await adriver.verify_connectivity()
            return adriver
        finally:
            await adriver.close()
    assert isinstance(asyncio.run(use_async()), neo4j.AsyncDriver)


def _unrecognized(driver, cypher):
    """그 질의에 서버가 단 「없는 이름」 상태(GQL status의 분류 UNRECOGNIZED)."""
    with driver.session() as s:
        summary = s.run(cypher).consume()
    return [g for g in summary.gql_status_objects if 'UNRECOGNIZED' in str(g.classification)]


def test_빈_그래프의_없는_라벨_관계_속성_알림은_오지_않는다(neo4j_graph):
    """H-2: 데이터를 비운 처음 상태에서 투영 주기마다 「없는 관계 USES_VERSION」 알림이 로그를 채웠다. 끄지 않은 드라이버는 같은 질의에
    그 알림을 받는다 — 같은 그래프에서 둘을 견준다(검사가 실제로 무엇을 재는지)."""
    cypher = 'MATCH (a:NoSuchLabel)-[:NO_SUCH_REL]->(b) WHERE a.no_such_prop = 1 RETURN b'
    plain = neo4j.GraphDatabase.driver(neo4j_graph.uri, auth=neo4j_graph.auth)
    quiet = graphdb.connect()
    try:
        assert _unrecognized(plain, cypher), '끄지 않은 드라이버가 알림을 받지 못하면 이 테스트는 아무것도 재지 못한다'
        assert _unrecognized(quiet, cypher) == []
    finally:
        plain.close()
        quiet.close()


@pytest.mark.parametrize('cypher, error', [
    ('MATCH (n RETURN n', neo4j.exceptions.CypherSyntaxError),             # 문법 오류는 알림이 아니라 예외
    ('RETURN 1/0', neo4j.exceptions.ClientError),                          # 실행 오류도 그대로
])
def test_질의_오류는_알림을_꺼도_예외로_올라온다(neo4j_graph, cypher, error):
    with graphdb.connect() as driver, driver.session() as s, pytest.raises(error):
        s.run(cypher).consume()


def test_틀린_비밀번호는_연결할_때_인증_오류다(neo4j_graph, monkeypatch):
    monkeypatch.setenv('NEO4J_AUTH', f'{neo4j_graph.auth[0]}/wrong-password')
    with graphdb.connect() as driver, pytest.raises(neo4j.exceptions.AuthError):
        driver.verify_connectivity()

