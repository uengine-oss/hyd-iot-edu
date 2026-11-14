"""출발본 내보내기 · 불러오기 · 기준으로 되돌리기(procsvc/config_bundle.py).

파일 칸 바꾸기는 순수 함수로, 불러오기 · 되돌리기는 학생 PC 구성(world — 실제 process · DB)과 학생이 띄운 바깥 MCP 서버 자리의 작은 서버로 본다.
"""
import copy
import uuid

import pytest

from conftest import STUDENT_HOST, Served
from procsvc import agent_authoring as A, config_bundle as cb, inbox, judgment_eval, mcp_registry, mcp_secrets, agent_trials, progress
from procsvc.bpmn_store import FlowStore

TENANT = 'hyd'
ME = 'user:me'                     # 이 PC의 담당자 — 포털은 불러오기 · 되돌리기에 늘 이 id 를 싣는다


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
    mcp_secrets.put(world.rt.repo, TENANT, 'MY_TOKEN', 'sk-live-0001', ME, 'now')
    mcp_registry.register(store, TENANT, {'name': 'my-rows', 'url': student_server.url + '/mcp',
                                          'headers': {'Authorization': 'Bearer ${SECRET:MY_TOKEN}'}}, by=ME)
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
        cb.import_bundle(world.rt, default_base_loader, {'bundle': bundle, 'by': ME})
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
        cb.import_bundle(world.rt, default_base_loader, {'bundle': bundle, 'by': ME})
    assert refused.value.status == 422 and 'OTHER_PC_TOKEN' in refused.value.reason
    assert mine.servers(TENANT)['my-rows']['headers'] == {'Authorization': 'Bearer ${SECRET:MY_TOKEN}'}


@pytest.mark.parametrize('change, says', [
    ({'name': '가' * 61}, '이름 칸이 너무 깁니다'),
    ({'goal': ''}, '목표 칸을 채워야 합니다'),
    ({'model': 'gpt-9-ultra'}, '연결된 모델(coding) 하나만'),
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
    je_store.golden_put(item, ME, create=True)
    out = cb.reset_all(world.rt, by=ME)
    steps = {s['step']: s for s in out['steps']}
    assert set(steps) == {'knowledge_reset', 'deploy_reset', 'flows_reset', 'agents_reset', 'mcp_reset', 'ask_reset', 'eval_reset', 'trials_reset'}
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
    out = cb.import_bundle(world.rt, default_base_loader, {'bundle': bundle, 'by': ME})
    assert out['verified'] is True
    again = cb.export_bundle(world.rt, default_base_loader)['content']
    for f in again['flows']:
        assert [int(v) for v in (x['version'] for x in f['versions'])] > [int(v) for v in flows[f['definition_id']]]   # 새 번호
    routes = {r['definition']: r['version'] for r in flow_deploy.routes(world.rt)['flows']}
    for d in again['deployments']['flows']:
        assert routes[d['definition_id']] == d['version']                      # 배포는 새로 매긴 번호를 가리킨다
    assert {d['definition_id'] for d in again['deployments']['flows']} == deployed


def _mine_kept(mine, world):
    return (mine.servers(TENANT)['my-rows']['headers'] == {'Authorization': 'Bearer ${SECRET:MY_TOKEN}'}
            and mcp_secrets.load(world.rt.repo, TENANT) == {'MY_TOKEN': 'sk-live-0001'})


@pytest.mark.parametrize('body', [None, {}, {'by': '  '}], ids=['본문 없음', '칸 없음', '빈 칸'])
def test_담당자_없이_온_되돌리기는_이름을_지어_넣지_않고_400_으로_거절한다(world, mine, body):
    """옛 판은 빈 칸을 「수강생」으로 채워 감사 기록에 사람처럼 남겼다. 거절은 아무것도 지우기 전이다(학생 구성이 그대로)."""
    status, out = world.api('POST', '/api/config/reset', body)
    assert status == 400 and '담당자 정보 없이 온 요청' in out['detail'], out
    assert _mine_kept(mine, world)


@pytest.mark.parametrize('extra', [{}, {'by': '  '}], ids=['칸 없음', '빈 칸'])
def test_담당자_없이_온_불러오기는_이름을_지어_넣지_않고_400_으로_거절한다(world, mine, extra):
    """수업 단계의 불러오기 API 는 단계 문지기가 먼저 막으므로(403) 불러오기 함수로 본다 — 멀쩡한 출발본이어도 담당자가 비면 바꾸기 전에 멈춘다."""
    from fastapi import HTTPException
    from procsvc.flows_api import default_base_loader
    bundle = cb.export_bundle(world.rt, default_base_loader)
    with pytest.raises(HTTPException) as refused:
        cb.import_bundle(world.rt, default_base_loader, {'bundle': bundle, **extra})
    assert refused.value.status_code == 400 and '담당자 정보 없이 온 요청' in refused.value.detail
    assert _mine_kept(mine, world)


def test_불러오기_본문은_출발본을_bundle_칸에_싣는다_본문이_곧_파일인_꼴은_받지_않는다(world, mine):
    """옛 판은 본문에 format 칸이 있으면 본문 전체를 파일로 읽었다(「또는 파일 그대로」). 담당자(by)가 필수가 된 뒤로 그 꼴은 파일에 by 를 끼워 넣어야만
    통과하는, 화면도 도구도 쓰지 않는 둘째 입구였다 — 입구는 {bundle, by} 하나다. 거절은 아무것도 바꾸기 전이다."""
    from procsvc.flows_api import default_base_loader
    bundle = cb.export_bundle(world.rt, default_base_loader)
    with pytest.raises(cb.BundleError) as refused:
        cb.import_bundle(world.rt, default_base_loader, {**bundle, 'by': ME})
    assert refused.value.status == 422 and '출발본 파일이 JSON 객체가 아닙니다' in refused.value.reason
    assert _mine_kept(mine, world)


def test_되돌리기_전_확인은_되돌리기가_지울_흐름의_처리_건만_세고_막은_처리_건을_JSON_으로_답한다(world):
    """관리 탭 [기준으로 되돌리기]는 수업 흐름(c3_cooling — 강사가 배포한 학생 판본)을 남긴다. 옛 판의 되돌리기 전 확인은 수업 흐름을 빼지 않고 세어,
    수업 흐름 처리 건이 진행 중이면 「내가 가져온 흐름으로 진행 중」이라는 틀린 사유로 거절했다(전수검사 12-2). 내가 가져온 흐름의 처리 건은 막는다.
    2026-10-31 실제 스택: 막은 처리 건 행의 시작 시각(datetime)이 거절 본문에 그대로 실려 409 대신 500 이 났다 — 포털과 같은 라우트로 부른다."""
    import psycopg
    from procsvc.course_policy import HANDOVER
    _, cooling, _ = world.start_cooling()
    assert world.api('POST', '/api/flows/import', {'xml': HANDOVER['xml'], 'file_name': 'shift-handover.bpmn'})[0] == 200
    status, registered = world.api('POST', '/api/flows/ShiftHandover/register', {'mapping': HANDOVER['mapping'], 'by': ME})
    assert status == 201, registered
    mine = world.rt.start_definition('ShiftHandover', registered['version'], 'bundle-test:' + uuid.uuid4().hex,
                                     values={'asset': 'HYD-01', 'shift_label': '다음 교대', 'as_of': world.now_iso(), 'work_notes': '작업 메모'})['proc_inst_id']
    try:
        status, body = world.api('POST', '/api/config/reset', {'by': ME})
        assert status == 409, body
        assert body['detail']['reason'].startswith('진행 중인 처리 건이 있어 되돌리지 않았습니다')
        [flows] = [b for b in body['detail']['blocking'] if b['step'] == 'flows_reset']
        assert [i['proc_inst_id'] for i in flows['items']] == [mine]                  # 수업 흐름의 처리 건은 세지 않는다
        assert flows['reason'].startswith('내가 가져온 흐름으로 진행 중인 처리 건 1건') and isinstance(flows['items'][0]['start_date'], str)
        # 출발본 불러오기는 수업 흐름도 지우고 다시 세우므로 둘 다 세고, 그렇다고 말한다
        [both] = [b for b in cb.blocking(world.rt, keep_class=False) if b['step'] == 'flows_reset']
        assert {i['proc_inst_id'] for i in both['items']} == {cooling, mine} and '기본 제공 흐름' in both['reason']
    finally:
        with psycopg.connect(world.dsn) as db, db.transaction():                      # 내 흐름의 처리 건을 닫는다(집히지 않은 AI 단계를 닫는 제품 길은 없다)
            db.execute("UPDATE todolist SET status='CANCELLED' WHERE proc_inst_id=%s AND status NOT IN ('DONE','CANCELLED')", (mine,))
            db.execute("UPDATE bpm_proc_inst SET status='CANCELLED' WHERE proc_inst_id=%s", (mine,))
    status, out = world.api('POST', '/api/config/reset', {'by': ME})                  # 수업 흐름의 처리 건이 진행 중이어도 되돌린다
    assert status == 200, out
    assert world.inst(cooling)['status'] == 'RUNNING'
    assert cooling in {i['proc_inst_id'] for i in world.rt.repo.list_instances(limit=None, tenant_id=TENANT)}      # 숨기지도 않았다
    assert FlowStore(world.rt.repo, TENANT).versions('ShiftHandover') == []


def test_기준으로_되돌리기가_적은_진행_기록에_단계마다_지운_것이_남는다(world, mine):
    rid = str(uuid.uuid4())
    status, out = world.api('POST', '/api/config/reset', {'by': ME, 'request_id': rid})
    assert status == 200, out
    seen = world.api('GET', f'/api/progress/{rid}')[1]
    assert seen['state'] == 'done' and [s['key'] for s in seen['steps']] == ['check'] + [k for k, _ in cb.RESET_STEPS]
    assert all(s['state'] == 'ok' for s in seen['steps'])
    assert {s['key']: s['note'] for s in seen['steps'][1:]} == {s['step']: s['text'] for s in out['steps']}      # 화면에 주는 「지운 것」과 같은 글
    assert 'my-rows' in next(s['note'] for s in seen['steps'] if s['key'] == 'mcp_reset')


# ---------------------------------------------------------------- 학생이 만든 역할 (전수검사 12-1)
ROLE_NAME, ROLE_ID, LANE_FLOW = '칸 시험 인계 담당', 'role:u-lane-test', 'RoleLaneHandover'


def _lane_flow():
    """제공 교대 흐름 그림을 다른 id 로 가져온 학생 흐름 — 인계자 검토 단계들의 담당을 학생이 만든 역할로 고른다(G10: 내 흐름의 담당 = 내 역할)."""
    from procsvc.course_policy import HANDOVER
    mapping = copy.deepcopy(HANDOVER['mapping'])
    for task in ('task_sender', 'task_sender_r2', 'task_sender_r3'):
        mapping['tasks'][task]['role'] = ROLE_NAME
    return HANDOVER['xml'].replace('ShiftHandover', LANE_FLOW), mapping


def _wipe_authored(world):
    out = FlowStore(world.rt.repo, TENANT).reset(LANE_FLOW)
    for pid in out['projection_instances']:
        world.rt._project({'proc_inst_id': pid})
    world.rt.cleanup_removed_definitions()
    A.reset(world.rt, by=ME)


@pytest.fixture
def authored(world, mine):
    """학생이 만든 것 한 벌: 역할 → 그 역할이 사람 단계를 맡는 흐름, 스킬 → 그 스킬과 내 도구 서버를 붙인 에이전트 → 그 흐름의 단계 배정."""
    from procsvc import bpmn_import
    from procsvc.flows_api import default_base_loader
    rt, repo = world.rt, world.rt.repo
    _wipe_authored(world)
    A.create_role(repo, TENANT, {'name': ROLE_NAME, 'key': ROLE_ID.split(':', 1)[1]}, by=ME)
    A.create_skill(repo, TENANT, {'skill_name': 'lane-check', 'description': '인계 점검', 'content': '# 인계 점검\n1. 본다'}, by=ME)
    agent = A.create_agent(repo, TENANT, dict(name='칸 시험 에이전트', goal='인계안을 쓴다', tools=['my-rows'], skills=['lane-check']), by=ME)
    xml, mapping = _lane_flow()
    store = FlowStore(repo, TENANT)
    store.save_draft(LANE_FLOW, xml, 'lane.bpmn', mapping)
    result = bpmn_import.check(bpmn_import.parse_bpmn(xml), mapping, {
        'catalog': bpmn_import.catalog(default_base_loader(rt), repo.list_users(None, TENANT)), 'definition_id': LANE_FLOW,
        'version': store.next_version(LANE_FLOW), 'file_name': 'lane.bpmn', 'xml_sha256': bpmn_import.xml_sha256(xml), 'name': None})
    assert result['ok'], result['problems']
    assert ROLE_ID in [r.get('endpoint') for r in result['definition']['roles']]      # 흐름이 학생 역할을 담당으로 쓴다
    store.register(result['definition'], xml, 'lane.bpmn')
    A.set_assignment(rt, LANE_FLOW, 'task_draft', agent['id'], by=ME)
    yield {'agent': agent['id']}
    _wipe_authored(world)


def _made(world):
    """학생이 만든 것의 지금 모습(흐름 판본 번호와 만든 시각은 뺀다 — 이 PC 는 되돌린 뒤 같은 번호를 다시 쓰지 않는다)."""
    from procsvc.flows_api import default_base_loader
    c = cb.export_bundle(world.rt, default_base_loader, include_secrets=True)['content']
    return {'roles': c['roles'], 'skills': c['skills'], 'agents': c['agents'], 'assignments': c['assignments'],
            'mcp_servers': [(s['name'], s['url'], s['headers']) for s in c['mcp_servers']],
            'flows': {f['definition_id']: [v['definition_sha256'] for v in f['versions']] for f in c['flows']},
            'deployed': sorted(d['definition_id'] for d in c['deployments']['flows']),
            'role_members': inbox.members_of(world.rt.repo, TENANT, ROLE_ID)}


def test_학생이_만든_역할은_출발본에_담기고_불러오면_흐름보다_먼저_다시_서며_담당자가_구성원이다(world, authored):
    """옛 출발본에는 역할 없이 「역할 ← 사람」 줄만 있었다. 같은 PC 에서 불러오면 되돌리기가 그 역할을 지운 뒤 업무분장 단계가 「그런 역할이
    없습니다」로 실패하고, 이어서 불러오기 전 상태로 되돌리기까지 실패해 학생이 만든 것이 모두 지워진 채 끝났다."""
    from procsvc.flows_api import default_base_loader
    before = _made(world)
    bundle = cb.export_bundle(world.rt, default_base_loader)
    assert bundle['format_version'] == 3 and 'role_members' not in bundle['content']
    assert bundle['content']['roles'] == [{'id': ROLE_ID, 'name': ROLE_NAME, 'kind': 'manager'}] and bundle['summary']['roles'] == 1
    rid = str(uuid.uuid4())
    out = progress.tracked(rid, 'config_import', lambda p: cb.import_bundle(world.rt, default_base_loader, {'bundle': bundle, 'by': ME}, progress=p))()
    assert out['verified'] is True
    order = [a['step'] for a in out['applied']]
    assert order.index('roles') < order.index('flows')
    assert next(a['items'] for a in out['applied'] if a['step'] == 'roles') == [ROLE_NAME]      # 되돌리기가 지운 역할을 새로 만들었다
    after = _made(world)
    assert after == before and after['role_members'] == [ME]                               # 담당자는 만들 때 구성원이 된다 — 파일에 없다
    seen = progress.read(rid)
    assert seen['state'] == 'done' and all(s['state'] == 'ok' for s in seen['steps'])
    assert [s['key'] for s in seen['steps']] == (['validate', 'check', 'backup', 'deploy_reset', 'flows_reset', 'agents_reset', 'mcp_reset']
                                                 + [k for k, _ in cb.STEPS] + ['verify'])
    assert {s['key']: s['note'] for s in seen['steps'] if s['key'] in dict(cb.STEPS)} == {a['step']: f"{a['count']}건" for a in out['applied']}


def test_사례_하나만_내보내면_그_사례의_흐름이_담당으로_쓰는_학생_역할만_담긴다(world, authored):
    """사례로 고른 출발본(student_cases.select_bundle)에 역할이 통째로 빠지면 불러온 PC 에서 흐름의 레인이 가리킬 역할이 없고, 쓰지 않는 역할까지
    담기면 남의 PC 에 관계없는 역할이 생긴다. 흐름에 꼬리표를 붙이고, 어느 흐름도 쓰지 않는 역할을 하나 더 만든 뒤 그 사례만 고른다."""
    from procsvc import student_cases
    from procsvc.flows_api import default_base_loader
    spare = A.create_role(world.rt.repo, TENANT, {'name': '칸 시험 안 쓰는 역할', 'key': 'u-lane-spare'}, by=ME)
    tags = student_cases.Store(world.rt.repo, TENANT)
    tags.set('flows', LANE_FLOW, '칸 시험 사례')
    try:
        bundle = cb.export_bundle(world.rt, default_base_loader)
        assert {r['id'] for r in bundle['content']['roles']} == {ROLE_ID, spare['id']}
        picked = student_cases.select_bundle(world.rt, bundle, '칸 시험 사례')
    finally:
        tags.set('flows', LANE_FLOW, '')
        A.delete_role(world.rt, spare['id'], by=ME)
    assert picked['content']['roles'] == [{'id': ROLE_ID, 'name': ROLE_NAME, 'kind': 'manager'}] and picked['summary']['roles'] == 1
    assert [f['definition_id'] for f in picked['content']['flows']] == [LANE_FLOW]
    cb.validate(world.rt, default_base_loader, picked)                  # 고른 묶음은 그대로 불러올 수 있는 출발본이다(레인의 역할이 파일 안에 있다)


def test_불러오기가_중간에_실패하면_학생이_만든_역할_에이전트_스킬_흐름_도구_서버가_불러오기_전_그대로다(world, authored):
    """파일의 둘째 도구 서버가 꺼져 있어 적용이 MCP 단계에서 멈춘다 — 그때는 되돌리기가 학생 것을 이미 다 지운 뒤다. 「불러오기 전 상태로
    되돌렸습니다」가 참인지: 역할(과 구성원) · 스킬 · 에이전트(붙인 스킬 · 도구) · 흐름 · 단계 배정 · 도구 서버가 모두 전과 같아야 한다."""
    from procsvc.flows_api import default_base_loader
    before = _made(world)
    assert before['roles'] and before['agents'] and before['skills'] and LANE_FLOW in before['flows'] and before['assignments'] and before['mcp_servers']
    bundle = cb.export_bundle(world.rt, default_base_loader)
    bundle['content']['mcp_servers'].append({'name': 'new-down', 'transport': 'streamable_http', 'url': f'http://{STUDENT_HOST}:9/mcp',
                                             'headers': {}, 'secrets': []})
    rid = str(uuid.uuid4())
    with pytest.raises(cb.BundleError) as failed:
        progress.tracked(rid, 'config_import', lambda p: cb.import_bundle(world.rt, default_base_loader, {'bundle': bundle, 'by': ME}, progress=p))()
    detail = failed.value.detail()
    assert (detail['failed_step'], detail['rolled_back'], detail['rollback_error']) == ('mcp', True, None)
    assert _made(world) == before
    seen = progress.read(rid)
    steps = {s['key']: s for s in seen['steps']}
    assert seen['state'] == 'failed' and '불러오기 전 상태로 되돌려 놓았습니다' in seen['error']
    assert [steps[k]['state'] for k in ('validate', 'check', 'backup', 'deploy_reset', 'flows_reset', 'agents_reset', 'mcp_reset')] == ['ok'] * 7
    assert steps['mcp']['state'] == 'fail' and '연결 검사 실패' in steps['mcp']['note']
    assert [steps[k]['state'] for k in ('skills', 'agents', 'roles', 'flows', 'assignments', 'deployments', 'verify')] == ['wait'] * 7
    assert list(steps)[-1] == 'restore' and steps['restore']['state'] == 'ok'


def test_역할_없이_구성원_줄만_있는_옛_형식_출발본은_읽지_않고_다시_내보내라고_거절한다():
    """판수 2 파일을 읽어 주는 길을 두지 않는다 — 형식 검사는 아무것도 읽기 전이라 처리 엔진 없이 판정된다."""
    old = {'format': cb.FORMAT, 'format_version': 2, 'content': {'role_members': [{'role_id': ROLE_ID, 'user_id': ME}]}}
    with pytest.raises(cb.BundleError) as refused:
        cb.validate(None, None, old)
    assert refused.value.status == 422 and '옛 형식' in refused.value.reason and '다시 내보내세요' in refused.value.reason


@pytest.mark.parametrize('role, says', [
    ({'id': 'role:operator', 'name': '내 운전원'}, '기본 역할과 겹칩니다'),
    ({'id': 'u-x', 'name': '내 역할'}, '모양이 아닙니다'),
    ({'id': 'role:u-x', 'name': ''}, '역할 이름 칸을 채워야 합니다'),
    ({'id': 'role:u-x', 'name': '내 역할', 'kind': 'boss'}, '역할 종류'),
], ids=['기본 역할 id', 'role: 없는 id', '이름 없음', '없는 종류'])
def test_출발본의_역할_칸은_만들기와_같은_규칙으로_불러오기_전에_거절한다(world, role, says):
    from procsvc.flows_api import default_base_loader
    bundle = {'format': cb.FORMAT, 'format_version': cb.FORMAT_VERSION, 'content': {'roles': [role]}}
    with pytest.raises(cb.BundleError) as refused:
        cb.validate(world.rt, default_base_loader, bundle)
    assert refused.value.status == 422 and says in refused.value.reason


# ---------------------------------------------------------------- 한 번에 처음 상태로: 지식까지(전수검사 10-G17 · G18 · S6, 요청문 7)
def _knowledge(world):
    """지금 지식의 모습: 문서마다 맨 위 판의 묶음, 화면에서 만든 조치 방법, 업무 DB 표 정의 묶음."""
    heads = {r['filename']: r['batch'] for r in world.api('GET', '/api/kg/manuals')[1] if r.get('current')}
    screen = sorted(k['sopId'] for k in world.api('GET', '/api/kg/skills')[1] if not k['source_document'])
    return heads, screen, sorted({r['batch'] for r in world.api('GET', '/api/kg/ingests')[1]})


def test_기준으로_되돌리기는_내가_적재한_문서_판과_표_정의와_화면에서_만든_조치_방법까지_처음_지식으로_되돌린다(world):
    """전에는 [기준으로 되돌리기]가 지식을 남겼다 — 학생이 다시 적재한 문서 판, 연결한 업무 DB 표 정의, 화면에서 만든 조치 방법(지우는 길 자체가
    없었다)이 다음 실습의 판단에 그대로 섞였다. 이미 있는 묶음별 되돌리기를 전체 되돌리기가 부른다."""
    import class_knowledge
    from conftest import SAMPLES
    from test_class_knowledge import portal_commit
    start = _knowledge(world)
    assert start[1] == [] and start[2] == [], start                       # 시작 상태: 기본 제공 문서의 지식만
    hm8 = next(i for i in class_knowledge.reviewed() if i['doc'] == 'HM-8')
    portal_commit(world, hm8, by=ME)                                      # 기본 제공 문서를 포털에서 다시 적재(문서 개정 실습)
    fm = world.stack.graph._run('MATCH (f:FailureMode) RETURN f.id AS id ORDER BY f.id LIMIT 1')[0]['id']
    status, made = world.api('POST', '/api/kg/skills', {'sopId': 'SOP-RESET-01', 'name': '되돌리기 시험 조치', 'description': '시험', 'kind': 'work_order',
                                                         'failureMode': fm, 'relation': 'REMEDIED_BY', 'steps': '본다\n적는다',
                                                         'approver': 'role:maint-mgr', 'by': ME, 'request_id': str(uuid.uuid4())})
    assert status == 200, made
    text = (SAMPLES / 'legacy-plant-db.sql').read_text(encoding='utf8')
    status, plan = world.api('POST', '/api/kg/ddl/preview', {'filename': 'legacy-plant-db.sql', 'text': text,
                                                             'systems': {'T_EQP00': 'sys:cmms', 'T_EQP01': 'sys:cmms', 'T_MNT10': 'sys:cmms'}})
    assert status == 200, plan
    status, ddl = world.api('POST', '/api/kg/ddl/commit', dict(plan, by=ME))
    assert status == 200, ddl
    changed = _knowledge(world)
    assert changed[0][hm8['filename']] != start[0][hm8['filename']] and changed[1] == ['SOP-RESET-01'] and changed[2] == [ddl['batch']]

    out = cb.reset_all(world.rt, by=ME)
    done = next(s for s in out['steps'] if s['step'] == 'knowledge_reset')['result']
    assert [(d['filename'], d['restored_batch']) for d in done['documents']] == [(hm8['filename'], start[0][hm8['filename']])]   # 앞 판(기본 제공 판)으로
    assert [k['sopId'] for k in done['skills']] == ['SOP-RESET-01'] and done['ddl_batches'] == [ddl['batch']]
    assert _knowledge(world) == start
    assert world.stack.graph._run("MATCH (r:Rule) WHERE r.id STARTS WITH 'rule:cand-' RETURN count(r) AS n")[0]['n'] == 0   # 화면이 만든 후보 규칙도 없다
    # 응답은 실제로 한 일과 남긴 것을 말한다(화면이 「지우는 것 · 남는 것」을 이 목록으로 그린다)
    assert '적재한 문서 판 1개' in out['removed'] and '화면에서 만든 조치 방법 1개' in out['removed'] and '업무 DB 표 정의 묶음 1개' in out['removed']
    assert any('처리 건 기록' in line for line in out['kept']) and any('[초기화]' in line for line in out['kept'])
    assert out['base_missing'] == []                                          # 기본 제공 문서의 지식은 모두 제자리다


def test_문서의_규칙이_가리키는_조치_방법이_있어_지식을_되돌리지_못하면_구성을_지우기_전에_멈추고_무엇이_왜인지_말한다(world, mine):
    """지식 되돌리기는 맨 앞 단계다 — 여기서 멈추면 에이전트 · 도구 서버 · 흐름은 손대지 않은 채이고, 그때까지 되돌린 것이 응답에 실린다."""
    fm = world.stack.graph._run('MATCH (f:FailureMode) RETURN f.id AS id ORDER BY f.id LIMIT 1')[0]['id']
    status, made = world.api('POST', '/api/kg/skills', {'sopId': 'SOP-RESET-02', 'name': '규칙이 가리키는 조치', 'description': '시험', 'kind': 'work_order',
                                                         'failureMode': fm, 'relation': 'REMEDIED_BY', 'steps': '본다', 'approver': 'role:maint-mgr',
                                                         'by': ME, 'request_id': str(uuid.uuid4())})
    assert status == 200, made
    # 다른 문서의 규칙이 이 조치 방법을 적용 대상으로 쓴다(그 문서를 되돌리기 전에는 지울 수 없다) — 포털 밖에서 넣은 규칙이라 되돌릴 묶음이 없다
    world.stack.graph._run("MATCH (k:Skill {sopId:'SOP-RESET-02'}) CREATE (:Rule {id:'rule:outside-doc', effect:'WARN'})-[:APPLIES_TO]->(k)")
    try:
        with pytest.raises(cb.BundleError) as stopped:
            cb.reset_all(world.rt, by=ME)
        assert stopped.value.status == 409 and stopped.value.extra['failed_step'] == 'knowledge_reset'
        assert '「규칙이 가리키는 조치」' in stopped.value.reason and 'rule:outside-doc' in stopped.value.reason and '문서 등록' in stopped.value.reason
        assert stopped.value.extra['done'] == [] and 'my-rows' in mine.servers(TENANT)          # 구성은 그대로
    finally:
        world.stack.graph._run("MATCH (r:Rule {id:'rule:outside-doc'}) DETACH DELETE r")
        assert world.api('DELETE', f"/api/kg/skills/{made['id']}?by={ME}")[0] == 200


def test_내_도구_서버를_만들_수_없는_단계의_전체_되돌리기는_서버와_비밀_값을_남기고_그렇게_말한다(world, mine):
    """도구 서버는 만들 수 있는 단계에서만 지운다 — 전체 되돌리기도 같다(지우면 되살릴 길이 없다). 포털의 요청 그대로(지금 단계 = 제공된 것만 쓰는 단계)."""
    from procsvc import course_policy as cp
    status, out = world.api('POST', '/api/config/reset', {'by': ME})
    assert status == 200, out
    step = next(s for s in out['steps'] if s['step'] == 'mcp_reset')
    assert step['result']['kept_servers'] == ['my-rows'] and step['result']['removed_servers'] == []
    assert 'my-rows' in step['text'] and cp.Policy.ACTIONS['tool_servers.register'] in step['text']
    assert 'my-rows' in mine.servers(TENANT) and mcp_secrets.load(world.rt.repo, TENANT) == {'MY_TOKEN': 'sk-live-0001'}
    assert any('내 도구 서버 1개와 비밀 값 1개' in line for line in out['kept']) and not any('도구 서버' in line for line in out['removed'])


def test_출발본_요약은_내가_만든_흐름만_세고_함께_담긴_기본_제공_흐름은_따로_센다(world, authored):
    """전에는 아무것도 만들지 않은 PC 의 출발본도 「흐름 3 · 배포 3」으로 셌고(시작할 때 설치되는 흐름을 내 것으로 셈), 파일 안 설명은 흐름을 담지
    않는다고 했다."""
    from procsvc import student_cases
    from procsvc.flows_api import default_base_loader
    bundle = cb.export_bundle(world.rt, default_base_loader)
    provided = cb.class_flow_ids(world.rt)
    assert provided and {f['definition_id'] for f in bundle['content']['flows']} == provided | {LANE_FLOW}      # 파일에는 둘 다 담긴다
    assert (bundle['summary']['flows'], bundle['summary']['flow_versions'], bundle['summary']['deployments']) == (1, 1, 0)
    assert bundle['summary']['provided_flows'] == len(provided)
    assert '기본 제공 흐름은 지금 배포된 판본을 함께 담습니다' in bundle['note']
    picked = student_cases.select_bundle(world.rt, dict(bundle, case_tags=[{'kind': 'flows', 'asset_id': LANE_FLOW, 'label': '칸 시험 사례'}]), '칸 시험 사례')
    assert (picked['summary']['flows'], picked['summary']['provided_flows']) == (1, 0)          # 사례 하나만 고른 묶음도 같은 셈


def test_내_사례_목록은_자산마다_기본_제공인지_알려_준다(world, authored):
    """화면이 흐름 목록을 한 번 더 읽어 가르지 않게 — 시작할 때 설치되는 흐름만 기본 제공이고, 출발본에 담기는 그 밖의 것은 모두 내가 만든 것이다."""
    from procsvc import student_cases
    from procsvc.flows_api import default_base_loader
    rows = {a['asset_id']: a['builtin'] for a in student_cases.catalog(cb.export_bundle(world.rt, default_base_loader))['assets']}
    provided = cb.class_flow_ids(world.rt)
    assert provided and all(rows[d] for d in provided) and rows[LANE_FLOW] is False and rows['lane-check'] is False and rows['my-rows'] is False
