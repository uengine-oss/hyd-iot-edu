"""Neo4j 드라이버를 여는 곳 하나 — process · agent · detector · dmn-mcp · neo4j_mcp 가 모두 이것을 쓴다.

설정(compose 가 넘긴다):
  NEO4J_URI                     없으면 bolt://neo4j:7687
  NEO4J_AUTH='사용자/비밀번호'   또는  NEO4J_USERNAME + NEO4J_PASSWORD(도구 서버 설정의 꼴)
둘 다 있으면 같은 값이어야 한다 — 다르면 어느 쪽이 맞는지 모르므로 연결하지 않는다. 인증이 없으면 연결하지 않는다
(코드에 비밀번호 기본값을 두지 않는다). 빈 값은 없는 것과 같다.

그래프는 처음에 비어 있고 라벨 · 관계 종류 · 속성 이름은 쓰일 때 생긴다. 그래서 Neo4j 의 「없는 이름」 알림
(UNRECOGNIZED 범주)은 끈다 — 데이터를 비운 처음 상태에서 투영 주기마다 경고 로그를 채워 진짜 오류를 묻었다(H-2).
질의 오류(문법 · 제약 · 인증)는 알림이 아니라 예외라 그대로 올라온다. 인자 이름은 드라이버 6.x 의 것이다(서비스 이미지 ·
개발 환경 모두 neo4j==6.3.1 — 요구 파일이 정본).

liveness_check_timeout=0: 풀에서 꺼낸 연결을 쓰기 전에 살아 있는지 확인한다. neo4j 가 다시 뜨면 풀에 남은 끊긴 연결이
다음 조회를 ServiceUnavailable 로 실패시켰다(2026-10-09 회귀: 승인 조건 검사 실패).
그 밖의 드라이버 설정(시간 한도 · 재시도)은 부르는 쪽이 opts 로 준다 — 위 두 기본값도 opts 가 이긴다.
"""
import os

DEFAULT_URI = 'bolt://neo4j:7687'
DEFAULTS = {'notifications_disabled_classifications': ['UNRECOGNIZED'], 'liveness_check_timeout': 0}


class GraphSettingsError(ValueError):
    """Neo4j 연결 설정이 없거나 서로 어긋난다 — 메시지가 환경 변수 이름과 고칠 곳을 말한다."""


def _value(env, name):
    value = env.get(name)
    return value if value else None


def settings(env=None):
    """(uri, (사용자, 비밀번호)) — 위 규칙대로 읽는다. env 는 os.environ 꼴의 사전(없으면 이 프로세스 환경)."""
    env = os.environ if env is None else env
    uri = _value(env, 'NEO4J_URI') or DEFAULT_URI
    joined = _value(env, 'NEO4J_AUTH')
    user, password = _value(env, 'NEO4J_USERNAME'), _value(env, 'NEO4J_PASSWORD')
    from_auth = None
    if joined is not None:
        name, sep, secret = joined.partition('/')
        if not sep or not name or not secret:
            raise GraphSettingsError("NEO4J_AUTH 는 '사용자/비밀번호' 꼴이어야 합니다 — compose.yaml 의 그 서비스 environment 를 확인하세요")
        from_auth = (name, secret)
    from_pair = None
    if user is not None or password is not None:
        if user is None or password is None:
            missing = 'NEO4J_USERNAME' if user is None else 'NEO4J_PASSWORD'
            raise GraphSettingsError(f'NEO4J_USERNAME 과 NEO4J_PASSWORD 는 함께 있어야 합니다 — {missing} 가 없습니다')
        from_pair = (user, password)
    if from_auth and from_pair and from_auth != from_pair:
        raise GraphSettingsError('NEO4J_AUTH 와 NEO4J_USERNAME · NEO4J_PASSWORD 가 서로 다릅니다 — 한 가지만 두세요')
    auth = from_auth or from_pair
    if auth is None:
        raise GraphSettingsError('Neo4j 인증이 없습니다 — NEO4J_AUTH(사용자/비밀번호) 또는 NEO4J_USERNAME · NEO4J_PASSWORD 를 주세요')
    return uri, auth


def connect(*, asynchronous=False, **opts):
    """설정대로 드라이버를 만든다(연결은 첫 질의 때). asynchronous=True 면 AsyncDriver."""
    uri, auth = settings()
    from neo4j import AsyncGraphDatabase, GraphDatabase
    factory = AsyncGraphDatabase if asynchronous else GraphDatabase
    return factory.driver(uri, auth=auth, **{**DEFAULTS, **opts})
