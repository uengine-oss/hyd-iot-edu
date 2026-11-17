"""도구 서버 등록 · 검사 도장 · 되돌리기(procsvc/mcp_registry.py) — 실제 DB(시드 테넌트 hyd)와, 학생이 띄운 바깥 MCP 서버 자리의 작은 서버.

「에이전트에 붙일 수 있나」는 selectable 한 함수가 정하고 도구 지도(annotate) · 저장 검사(refuse_reasons)가 그 결과를 쓴다.
"""
import json
import re

import psycopg
import pytest

from conftest import STUDENT_HOST, Served
from procsvc import mcp_check, mcp_registry, mcp_secrets, procdb
from procsvc.mcp_registry import RegistryError

TENANT = 'hyd'


@pytest.fixture(scope='module')
def student_url():
    """학생이 띄운 HTTP MCP 서버 자리: 읽기 도구 하나 · 표시 없는 도구 하나 · 쓰기 도구 하나."""
    from fastmcp import FastMCP
    from mcp.types import ToolAnnotations
    app = FastMCP('학생 서버')

    @app.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def find_rows(limit: int) -> dict:
        """표에서 행을 찾는다"""
        return {'rows': list(range(limit))}

    @app.tool()
    def search_docs(text: str) -> dict:
        """문서를 찾는다(표시 없음)"""
        return {'hits': [text]}

    @app.tool(annotations=ToolAnnotations(readOnlyHint=False))
    def save_row(text: str) -> dict:
        """행을 저장한다"""
        return {'saved': text}
    served = Served(app.http_app(path='/mcp'), host=STUDENT_HOST)   # 학생 서버는 루프백이 아닌 이 PC 주소
    yield served.url + '/mcp'
    served.close()


@pytest.fixture
def store(pg_dsn):
    """테넌트 hyd 의 MCP 구성을 시드 상태(학생 서버 · 검사 기록 · 비밀 값 없음)로 두고 시작한다."""
    s = mcp_registry.store_for(procdb.PgRepo(pg_dsn))
    mcp_registry.reset(s, TENANT)
    yield s
    mcp_registry.reset(s, TENANT)


def seed_servers(dsn):
    with psycopg.connect(dsn) as db:
        (mcp,) = db.execute("SELECT mcp FROM tenants WHERE id=%s", (TENANT,)).fetchone()
    return mcp['mcpServers']


# ---------------------------------------------------------------- 등록 본문
@pytest.mark.parametrize('body, status, says', [
    ({'name': 'x', 'command': 'npx', 'args': ['-y', 'some-server']}, 422, '명령형(stdio) 서버는 포털에 등록하지 않습니다'),
    ({'name': 'x', 'url': 'http://169.254.169.254/'}, 422, '링크로컬'),
    ({'name': 'x', 'url': 'http://h/mcp', 'description': '가' * 201}, 422, '설명은 200자 이하'),
    ({'name': 'x', 'url': 'http://h/mcp', 'headers': {'X-New': mcp_check.MASK}}, 422, '이전 설정에 같은 이름의 값이 없습니다'),
    ({'name': 'x', 'url': 'https://h/${SECRET:TOKEN}'}, 422, '접속 헤더 값에만'),
], ids=['명령형', '링크로컬', '설명 201자', '가린 값을 새 이름 칸에', '주소에 비밀 참조'])
def test_받을_수_없는_등록_본문은_까닭과_함께_거절된다(body, status, says):
    with pytest.raises(RegistryError) as refused:
        mcp_registry.entry_from_body(body, {'headers': {'Authorization': 'Bearer old-token-1234'}})
    assert refused.value.status == status and says in refused.value.reason


def test_고칠_때_가린_값은_같은_이름_칸의_옛_값을_그대로_쓴다():
    entry = mcp_registry.entry_from_body({'name': 'x', 'url': 'http://h/mcp', 'headers': {'Authorization': mcp_check.MASK}, 'description': '가' * 200},
                                         {'headers': {'Authorization': 'Bearer old-token-1234'}})
    assert entry == {'type': 'url', 'url': 'http://h/mcp', 'transport': 'streamable_http',
                     'headers': {'Authorization': 'Bearer old-token-1234'}, 'description': '가' * 200}


# ---------------------------------------------------------------- 등록 = 실제 연결 검사 통과
def test_등록은_실제_연결_검사를_통과해야_하고_읽기_도구만_도장에_든다(store, student_url):
    out = mcp_registry.register(store, TENANT, {'name': 'my-rows', 'url': student_url}, by='user:me')
    entry = store.servers(TENANT)['my-rows']
    assert out['check']['status'] == 'ok'
    assert (entry['hyd']['gate']['read_tools'], sorted(entry['hyd']['gate']['blocked_tools'])) == (['find_rows'], ['save_row', 'search_docs'])
    assert entry['hyd']['gate']['fingerprint'] == mcp_registry.fingerprint(entry)


def test_연결_검사에_실패한_서버는_저장하지_않는다(store):
    with pytest.raises(RegistryError) as refused:
        mcp_registry.register(store, TENANT, {'name': 'my-down', 'url': f'http://{STUDENT_HOST}:9/mcp', 'timeout': 8}, by='user:me')
    assert refused.value.status == 422 and refused.value.check['error_kind'] == 'refused'
    assert 'my-down' not in store.servers(TENANT)


@pytest.mark.parametrize('url', ['http://localhost:8000/api/instances', 'http://127.0.0.1:8000/mcp', 'http://2852039166/mcp'],
                         ids=['localhost', '127.0.0.1', '숫자로 적은 메타데이터 주소'])
def test_학생이_루프백이나_링크로컬을_등록하면_연결하지_않고_까닭과_함께_거절한다(store, url):
    with pytest.raises(RegistryError) as refused:
        mcp_registry.register(store, TENANT, {'name': 'my-self', 'url': url, 'timeout': 8}, by='user:me')
    assert refused.value.status == 422 and refused.value.check is None
    assert ('host.docker.internal' in refused.value.reason) or ('링크로컬' in refused.value.reason)
    assert 'my-self' not in store.servers(TENANT)


# ---------------------------------------------------------------- 붙일 수 있음 — 한 판정
def test_도구_지도와_저장_검사는_같은_붙일_수_있음_판정을_쓴다(store, student_url):
    mcp_registry.register(store, TENANT, {'name': 'my-rows', 'url': student_url}, by='user:me')
    store.replace_server(TENANT, 'my-rows', dict(store.servers(TENANT)['my-rows'], description='고친 설명'))   # 검사 뒤 설정이 바뀜
    view = {s['name']: s for s in mcp_registry.selectable(store, TENANT)['servers']}
    marks = mcp_registry.annotate(store, TENANT)
    assert {n: (s['selectable'], s['reason']) for n, s in view.items()} == {n: (m['selectable'], m['reason']) for n, m in marks.items()}
    assert all(view[n]['selectable'] for n in mcp_registry.BASE_SERVERS)            # 기준 서버는 검사 없이 붙인다
    assert view['my-rows']['selectable'] is False and '설정이 바뀌었습니다' in view['my-rows']['reason']
    assert mcp_registry.refuse_reasons(store, TENANT, ['neo4j', 'my-rows', 'nope']) == [
        f"my-rows: {view['my-rows']['reason']}", 'nope: 등록되지 않은 도구 서버입니다']


def test_읽기_표시가_없는_도구는_강사가_읽기로_확인해야_도장에_든다(store, student_url):
    mcp_registry.register(store, TENANT, {'name': 'my-rows', 'url': student_url}, by='user:me')
    out = mcp_registry.confirm_read(store, TENANT, 'my-rows', 'search_docs', by='user:me', reason='검색 결과만 돌려준다')
    assert sorted(out['gate']['read_tools']) == ['find_rows', 'search_docs'] and out['gate']['confirmed_tools'] == ['search_docs']
    with pytest.raises(RegistryError) as refused:
        mcp_registry.confirm_read(store, TENANT, 'my-rows', 'save_row', by='user:me', reason='x')
    assert refused.value.status == 422


# ---------------------------------------------------------------- 되돌리기 · 보관 · 다시 쓰기
@pytest.mark.parametrize('secrets, left', [(True, {}), (False, {'MY_TOKEN': 'sk-1234'})], ids=['관리 되돌리기', '출발본 불러오기 안'])
def test_되돌리기는_학생_서버를_지우고_비밀_값은_불러오기_안에서는_남긴다(store, student_url, secrets, left):
    mcp_secrets.put(store.repo, TENANT, 'MY_TOKEN', 'sk-1234', '강사', 'now')
    mcp_registry.register(store, TENANT, {'name': 'my-rows', 'url': student_url}, by='user:me')
    out = mcp_registry.reset(store, TENANT, secrets=secrets)
    assert out['removed_servers'] == ['my-rows'] and sorted(store.servers(TENANT)) == sorted(mcp_registry.BASE_SERVERS)
    assert mcp_secrets.load(store.repo, TENANT) == left


def test_보관한_MCP_행은_서버가_꺼져_있어도_검사_없이_그대로_다시_쓴다(store, student_url):
    mcp_registry.register(store, TENANT, {'name': 'my-rows', 'url': student_url}, by='user:me')
    before = store.servers(TENANT)['my-rows']
    snap = mcp_registry.snapshot(store, TENANT)
    mcp_registry.reset(store, TENANT, secrets=False)
    gone = dict(snap, servers={'my-rows': dict(before, url=f'http://{STUDENT_HOST}:9/mcp')})   # 그 순간 꺼진 서버라도
    gone['servers']['my-rows']['hyd'] = before['hyd']
    assert mcp_registry.restore(store, TENANT, gone, '포털') == ['my-rows']
    after = store.servers(TENANT)['my-rows']
    assert (after['url'], after['hyd']['gate']) == (f'http://{STUDENT_HOST}:9/mcp', before['hyd']['gate'])
    assert store.checks(TENANT)['my-rows']['status'] == 'ok'


def test_학생_서버가_남은_채로는_보관본을_다시_쓰지_않는다(store, student_url):
    mcp_registry.register(store, TENANT, {'name': 'my-rows', 'url': student_url}, by='user:me')
    with pytest.raises(RegistryError) as refused:
        mcp_registry.restore(store, TENANT, mcp_registry.snapshot(store, TENANT), '포털')
    assert refused.value.status == 409


# ---------------------------------------------------------------- 워커와 같은 계산 · 같은 기준 서버
def test_설정_해시는_워커가_도장을_대조하는_해시와_같다(student_url):
    from worker import bridge
    entry = mcp_registry.entry_from_body({'name': 'x', 'url': student_url, 'headers': {'Authorization': 'Bearer ${SECRET:MY_TOKEN}'}})
    entry['hyd'] = {'gate': {'fingerprint': 'anything'}}
    assert mcp_registry.fingerprint(entry) == bridge.config_fingerprint(entry)


def test_기준_서버는_시드의_도구_서버이자_워커_기본_허용_목록의_서버다(pg_dsn):
    from worker import settings
    allowed = set(re.findall(r'mcp__([a-z0-9-]+)__', settings.DEFAULT_ALLOWED_TOOLS))
    assert set(mcp_registry.BASE_SERVERS) == set(seed_servers(pg_dsn)) == allowed


def test_기준_서버_설정은_모두_포털이_연결하는_HTTP_주소다(pg_dsn):
    for name, entry in seed_servers(pg_dsn).items():
        assert mcp_check.normalize(entry)['transport'] == 'streamable_http', name


# ---------------------------------------------------------------- 진행 기록(progress) — 연결 검사가 실제 경계에서 단계를 적는다
def _steps(request_id):
    from procsvc import progress
    out = progress.read(request_id)
    return out['state'], [(s['key'], s['state'], s['note']) for s in out['steps']]


def _tracked(kind, work):
    import uuid
    from procsvc import progress
    rid = str(uuid.uuid4())
    return rid, progress.tracked(rid, kind, work)


def test_등록이_도는_동안의_진행_기록에_인사_도구_목록_저장이_차례로_남는다(store, student_url):
    rid, work = _tracked('mcp_register', lambda p: mcp_registry.register(store, TENANT, {'name': 'my-rows', 'url': student_url}, by='user:me', progress=p))
    out = work()
    state, steps = _steps(rid)
    assert state == 'done' and [(k, s) for k, s, _ in steps] == [('initialize', 'ok'), ('tools', 'ok'), ('save', 'ok')]
    notes = {k: n for k, _, n in steps}
    assert '학생 서버' in notes['initialize']                                   # 서버가 인사에서 밝힌 이름
    assert notes['tools'] == f"도구 {len(out['check']['tools'])}개" == '도구 3개'


def test_저장하지_않는_연결_검사는_저장_단계를_적지_않는다(store, student_url):
    rid, work = _tracked('mcp_check', lambda p: mcp_registry.dry_check(store, TENANT, {'name': 'my-rows', 'url': student_url}, progress=p))
    work()
    assert [(k, s) for k, s, _ in _steps(rid)[1]] == [('initialize', 'ok'), ('tools', 'ok')]


def test_연결되지_않는_서버의_등록은_멈춘_단계에_사유가_남고_그_뒤_단계는_하지_않은_채다(store):
    rid, work = _tracked('mcp_register', lambda p: mcp_registry.register(store, TENANT, {'name': 'my-down', 'url': f'http://{STUDENT_HOST}:9/mcp', 'timeout': 8},
                                                                        by='user:me', progress=p))
    with pytest.raises(RegistryError):
        work()
    state, steps = _steps(rid)
    assert state == 'failed' and [(k, s) for k, s, _ in steps] == [('initialize', 'fail'), ('tools', 'wait'), ('save', 'wait')]
    assert '연결 거부' in steps[0][2]


def test_등록된_서버_검사는_검사_기록을_저장한_것까지_적는다(store, student_url):
    mcp_registry.register(store, TENANT, {'name': 'my-rows', 'url': student_url}, by='user:me')
    rid, work = _tracked('mcp_check_saved', lambda p: mcp_registry.check_saved(store, TENANT, 'my-rows', by='user:me', progress=p))
    work()
    assert [(k, s) for k, s, _ in _steps(rid)[1]] == [('initialize', 'ok'), ('tools', 'ok'), ('save', 'ok')]


def test_비밀_값이_없어_연결하지_않은_검사는_하지_않은_단계를_적지_않는다(store):
    rid, work = _tracked('mcp_check', lambda p: mcp_registry.dry_check(
        store, TENANT, {'name': 'my-rows', 'url': f'http://{STUDENT_HOST}:9/mcp', 'headers': {'Authorization': 'Bearer ${SECRET:NO_SUCH}'}}, progress=p))
    out = work()
    assert out['check']['error_kind'] == 'secret' and _steps(rid) == ('done', [])


def test_진행_기록에_적는_글에서도_채운_비밀_값을_지운다(store):
    """서버가 인사에서 밝힌 이름을 진행 기록에 적는다 — 그 이름에 접속 토큰이 섞여 와도(되돌려 주는 서버) 기록으로 새지 않는다."""
    from fastmcp import FastMCP
    from mcp.types import ToolAnnotations
    app = FastMCP('server-for-sk-live-7777')

    @app.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def find_rows(limit: int) -> dict:
        """표에서 행을 찾는다"""
        return {'rows': list(range(limit))}
    served = Served(app.http_app(path='/mcp'), host=STUDENT_HOST)
    try:
        mcp_secrets.put(store.repo, TENANT, 'MY_TOKEN', 'sk-live-7777', '수강생', 'now')
        rid, work = _tracked('mcp_check', lambda p: mcp_registry.dry_check(
            store, TENANT, {'name': 'my-rows', 'url': served.url + '/mcp', 'headers': {'Authorization': 'Bearer ${SECRET:MY_TOKEN}'}}, progress=p))
        work()
    finally:
        served.close()
    note = _steps(rid)[1][0][2]
    assert 'sk-live-7777' not in note and mcp_secrets.REDACTED in note


def test_연결되지_않는_서버의_연결_검사는_요청은_끝나도_멈춘_단계가_실패로_남는다(store):
    """[연결 검사만]은 실패해도 요청 자체는 검사 결과와 함께 정상으로 끝난다 — 그래도 진행 기록의 단계는 「하는 중」으로 남지 않는다."""
    rid, work = _tracked('mcp_check', lambda p: mcp_registry.dry_check(store, TENANT, {'name': 'my-down', 'url': f'http://{STUDENT_HOST}:9/mcp', 'timeout': 8},
                                                                      progress=p))
    out = work()
    state, steps = _steps(rid)
    assert out['check']['status'] == 'failed' and state == 'done'
    assert [(k, s) for k, s, _ in steps] == [('initialize', 'fail'), ('tools', 'wait')] and steps[0][2] == out['check']['error']
