"""출발본 내보내기 · 불러오기 · 기준으로 되돌리기(procsvc/config_bundle.py).

파일 칸 바꾸기는 순수 함수로, 불러오기 · 되돌리기는 학생 PC 구성(world — 실제 process · DB)과 학생이 띄운 바깥 MCP 서버 자리의 작은 서버로 본다.
"""
import pytest

from conftest import STUDENT_HOST, Served
from procsvc import config_bundle as cb, judgment_eval, mcp_registry, mcp_secrets, agent_trials

TENANT = 'hyd'


# ---------------------------------------------------------------- 파일 칸 (비밀값)
def test_비밀_값_참조는_그대로_담고_설정에_적힌_토큰만_칸_자리표시로_바꾼다():
    entry = {'type': 'url', 'url': 'https://user:pw-1234@h/mcp?api_key=k-5678&q=1', 'transport': 'streamable_http',
             'headers': {'Authorization': 'Bearer ${SECRET:MY_TOKEN}', 'X-Api-Key': 'literal-key-0000', 'Accept': 'json'}}
    item = cb.server_item('my-drive', entry)
    assert item['headers'] == {'Authorization': 'Bearer ${SECRET:MY_TOKEN}', 'X-Api-Key': '${HYD_SECRET:headers.X-Api-Key}', 'Accept': 'json'}
    assert item['url'] == 'https://user:${HYD_SECRET:url.password}@h/mcp?api_key=${HYD_SECRET:url.query.0}&q=1'
    assert [s['slot'] for s in item['secrets']] == ['url.password', 'url.query.0', 'headers.X-Api-Key']
    assert 'pw-1234' not in str(item) and 'k-5678' not in str(item) and 'literal-key-0000' not in str(item)


def test_칸_자리표시에_넣은_값으로_등록_본문을_다시_만든다():
    entry = {'type': 'url', 'url': 'https://h/mcp?api_key=k-5678', 'transport': 'streamable_http',
             'headers': {'Authorization': 'Bearer ${SECRET:MY_TOKEN}', 'X-Api-Key': 'literal-key-0000'}}
    item = cb.server_item('my-drive', entry)
    body = cb.register_body(item, {'headers.X-Api-Key': 'literal-key-0000', 'url.query.0': 'k-5678'})
    assert mcp_registry.entry_from_body(body) == entry


def test_칸에_넣을_값이_없으면_그_칸_이름으로_멈춘다():
    item = cb.server_item('my-drive', {'type': 'url', 'url': 'https://h/mcp', 'headers': {'X-Api-Key': 'literal-key-0000'}})
    with pytest.raises(KeyError) as missing:
        cb.register_body(item, {})
    assert missing.value.args == ('headers.X-Api-Key',)


@pytest.mark.parametrize('a, b, paths', [
    ({'x': 1}, {'x': 1}, []),
    ({'agents': [1]}, {'agents': []}, ['agents (개수 1 ≠ 0)']),
    ({'x': {'y': 1}}, {'x': {'y': 2}}, ['x.y']),
], ids=['같음', '개수 다름', '값 다름'])
def test_적용_뒤_대조는_다른_자리를_경로로_알린다(a, b, paths):
    assert cb._diff_paths(a, b) == paths


# ---------------------------------------------------------------- 학생 PC 구성
@pytest.fixture
def student_server():
    from fastmcp import FastMCP
    from mcp.types import ToolAnnotations
    app = FastMCP('학생 서버')

    @app.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def find_rows(limit: int) -> dict:
        """표에서 행을 찾는다"""
        return {'rows': list(range(limit))}
    served = Served(app.http_app(path='/mcp'), host=STUDENT_HOST)   # 학생 서버는 루프백이 아닌 이 PC 주소
    yield served
    served.close()


@pytest.fixture
def mine(world, student_server):
    """학생 구성: 비밀 값 하나 + 그 비밀을 참조하는 학생 서버 하나(실제 연결 검사로 등록)."""
    store = mcp_registry.store_for(world.rt.repo)
    mcp_registry.reset(store, TENANT)
    mcp_secrets.put(world.rt.repo, TENANT, 'MY_TOKEN', 'sk-live-0001', '수강생', 'now')
    mcp_registry.register(store, TENANT, {'name': 'my-rows', 'url': student_server.url + '/mcp',
                                          'headers': {'Authorization': 'Bearer ${SECRET:MY_TOKEN}'}}, by='수강생')
    yield store
    mcp_registry.reset(store, TENANT)


def test_불러오기가_실패하면_학생_MCP_서버는_그_서버가_꺼져_있어도_검사_없이_그대로_되살아난다(world, mine, student_server):
    from procsvc.flows_api import default_base_loader
    before = mine.servers(TENANT)['my-rows']
    bundle = cb.export_bundle(world.rt, default_base_loader)
    bundle['content']['mcp_servers'].append({'name': 'new-down', 'transport': 'streamable_http', 'url': f'http://{STUDENT_HOST}:9/mcp',
                                             'headers': {}, 'secrets': []})
    student_server.close()                                      # 그 순간 학생 서버가 꺼져 있다 — 옛 판은 실시간 검사로 되살리다 구성을 잃었다
    with pytest.raises(cb.BundleError) as failed:
        cb.import_bundle(world.rt, default_base_loader, {'bundle': bundle})
    detail = failed.value.detail()
    assert (detail['failed_step'], detail['rolled_back'], detail['rollback_error']) == ('mcp', True, None)
    after = mine.servers(TENANT)['my-rows']
    assert (after['headers'], after['hyd']['gate']) == (before['headers'], before['hyd']['gate'])
    assert mcp_secrets.load(world.rt.repo, TENANT) == {'MY_TOKEN': 'sk-live-0001'}     # 불러오기는 비밀 값을 지우지 않는다


def test_다른_PC의_출발본이_이_PC_비밀_값에_없는_이름을_참조하면_아무것도_바꾸기_전에_멈춘다(world, mine):
    from procsvc.flows_api import default_base_loader
    bundle = cb.export_bundle(world.rt, default_base_loader)
    bundle['content']['mcp_servers'][0]['headers'] = {'Authorization': 'Bearer ${SECRET:OTHER_PC_TOKEN}'}
    with pytest.raises(cb.BundleError) as refused:
        cb.import_bundle(world.rt, default_base_loader, {'bundle': bundle})
    assert refused.value.status == 422 and 'OTHER_PC_TOKEN' in refused.value.reason
    assert mine.servers(TENANT)['my-rows']['headers'] == {'Authorization': 'Bearer ${SECRET:MY_TOKEN}'}


@pytest.mark.parametrize('change, says', [
    ({'name': '가' * 61}, '이름 칸이 너무 깁니다'),
    ({'goal': ''}, '목표 칸을 채워야 합니다'),
    ({'model': 'gpt-9-ultra'}, '수업 모델'),
], ids=['이름 61자', '목표 없음', '수업 밖 모델'])
def test_에이전트_칸_규칙은_불러오기_전_검증에서_저장과_같은_규칙으로_거절한다(world, change, says):
    from procsvc.flows_api import default_base_loader
    agent = dict({'id': 'agent:u-00ab', 'name': '내 에이전트', 'goal': '점검', 'role': '', 'persona': '', 'model': '', 'tools': [], 'skills': [],
                  'work_rules': ''}, **change)
    bundle = {'format': cb.FORMAT, 'format_version': cb.FORMAT_VERSION, 'content': {'agents': [agent]}}
    with pytest.raises(cb.BundleError) as refused:
        cb.validate(world.rt, default_base_loader, bundle)
    assert refused.value.status == 422 and says in refused.value.reason


def test_기준으로_되돌리기는_비밀_값과_채점_시험_기록까지_지우고_무엇을_지웠는지_말한다(world, mine):
    je_store = judgment_eval.PgEvalStore(world.dsn, TENANT)
    je_store.reset()
    item = judgment_eval.validate_item({'id': 'cooler-auto', 'title': '쿨러', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'facts': {},
                                        'expected': {'cause': 'cause:a', 'failure_mode': 'fm:a'}, 'allowed_top': ['skill:a'],
                                        'forbidden': [], 'required_evidence': ['evd:a']})
    je_store.golden_put(item, '수강생', create=True)
    out = cb.reset_all(world.rt, by='수강생')
    steps = {s['step']: s for s in out['steps']}
    assert set(steps) == {'deploy_reset', 'flows_reset', 'agents_reset', 'mcp_reset', 'ask_reset', 'eval_reset', 'trials_reset'}
    assert steps['mcp_reset']['text'].endswith('비밀 값 1') and steps['eval_reset']['text'] == '정답표 항목 1 · 채점 실행 0'
    assert mcp_secrets.load(world.rt.repo, TENANT) == {} and je_store.golden_list() == []
    assert agent_trials.store_for(world.rt.repo).list_trials(TENANT) == []


def test_같은_PC에서_같은_출발본을_두_번_불러와도_흐름_판본을_새로_매기고_배포까지_맞춘다(world):
    """이 PC 는 되돌린 뒤에도 한 번 쓴 판본 번호를 다시 쓰지 않는다(bpmn_store). 옛 판은 파일의 번호(1)와 다시 매긴 번호(2)가 달라
    불러오기 · 그 실패 복원이 「판본 1 대신 2 로 등록됐습니다」로 멈추고 학생 구성을 잃었다(P3-01)."""
    from procsvc import flow_deploy
    from procsvc.flows_api import default_base_loader
    bundle = cb.export_bundle(world.rt, default_base_loader)
    flows = {f['definition_id']: [v['version'] for v in f['versions']] for f in bundle['content']['flows']}
    deployed = {d['definition_id'] for d in bundle['content']['deployments']['flows']}
    assert flows and deployed                                                  # 수업 흐름(c3_*)이 들어 있다 — 시험이 성립한다
    out = cb.import_bundle(world.rt, default_base_loader, {'bundle': bundle})
    assert out['verified'] is True
    again = cb.export_bundle(world.rt, default_base_loader)['content']
    for f in again['flows']:
        assert [int(v) for v in (x['version'] for x in f['versions'])] > [int(v) for v in flows[f['definition_id']]]   # 새 번호
    routes = {r['definition']: r['version'] for r in flow_deploy.routes(world.rt)['flows']}
    for d in again['deployments']['flows']:
        assert routes[d['definition_id']] == d['version']                      # 배포는 새로 매긴 번호를 가리킨다
    assert {d['definition_id'] for d in again['deployments']['flows']} == deployed


def test_진행_중인_처리_건이_있으면_되돌리기_API_는_409_와_막은_처리_건을_JSON_으로_답한다(world):
    """2026-10-31 실제 스택: 막은 처리 건 행의 시작 시각(datetime)이 거절 본문에 그대로 실려 409 대신 500(JSON 으로 못 씀)이 났고
    BundleError 트레이스가 로그에 남았다. 수업 흐름(c3_cooling — 학생 판본)으로 진행 중인 처리 건 하나를 두고 포털과 같은 라우트로 부른다."""
    _, pid, _ = world.start_cooling()
    status, body = world.api('POST', '/api/config/reset', {'by': '수강생'})
    assert status == 409, body
    assert body['detail']['reason'].startswith('진행 중인 처리 건이 있어 되돌리지 않았습니다')
    [flows] = [b for b in body['detail']['blocking'] if b['step'] == 'flows_reset']
    [held] = [i for i in flows['items'] if i['proc_inst_id'] == pid]
    assert isinstance(held['start_date'], str) and held['proc_def_id'] == 'c3_cooling'
