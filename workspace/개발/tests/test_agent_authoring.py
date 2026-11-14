"""에이전트 만들기 · 복제 · 고치기 · 단계 배정(procsvc/agent_authoring.py) — 기본 에이전트는 모두 도구 · 스킬 그대로 복제할 수 있고, 등록 안 된 ·
붙일 수 없는 도구 서버 · 수업 모델 밖 모델 · 같은 이름 · 빠진 칸은 학생이 읽을 까닭과 함께 거절된다. 실제 업무 DB(시드 테넌트 hyd).

옛 판은 수업용 도구 서버 목록(셋)을 따로 적어, 정비 · 구매 서버를 쓰는 기본 정비 · 구매 에이전트의 [복제해서 고치기]가 늘 거절됐다(견적 #7).
"""
import psycopg
import pytest

from procsvc import agent_authoring as A, mcp_registry, procdb
from procsvc.agent_authoring import AuthoringError

SEED_AGENTS = ['sys:agent', 'agent:cooling', 'agent:pm-plan', 'agent:spare-buy', 'agent:handover']
TENANT = 'hyd'


@pytest.fixture
def authoring(pg_dsn):
    repo, made = procdb.PgRepo(pg_dsn), []
    yield repo, made
    with psycopg.connect(pg_dsn, autocommit=True) as db:
        for agent_id in made:
            db.execute('DELETE FROM agent_skills WHERE user_id=%s', (agent_id,))
            db.execute('DELETE FROM users WHERE id=%s', (agent_id,))
    mcp_registry.reset(mcp_registry.store_for(repo), TENANT)


def tools_of(row):
    return sorted(A.csv_list(row.get('tools')))


def full_body(row, **change):
    return dict({'name': row['username'], 'role': row.get('role') or '', 'goal': row.get('goal') or '', 'persona': row.get('persona') or '',
                 'model': '', 'tools': tools_of(row), 'skills': [], 'work_rules': row.get('work_rules') or ''}, **change)


@pytest.mark.parametrize('agent_id', SEED_AGENTS)
def test_기본_에이전트는_모두_도구와_스킬과_업무_규칙을_그대로_복제한다(authoring, agent_id):
    repo, made = authoring
    source = A.get_agent(repo, TENANT, agent_id)
    copy = A.clone_agent(repo, TENANT, agent_id, by='user:me')
    made.append(copy['id'])
    assert (A.origin_of(copy), tools_of(copy), copy.get('work_rules')) == (A.USER, tools_of(source), source.get('work_rules'))
    assert [r['skill_name'] for r in repo.list_agent_skills(TENANT, copy['id'])] == [r['skill_name'] for r in repo.list_agent_skills(TENANT, agent_id)]


@pytest.mark.parametrize('agent_id', SEED_AGENTS)
def test_복제한_에이전트는_모든_칸을_보내_고칠_수_있다(authoring, agent_id):
    repo, made = authoring
    copy = A.clone_agent(repo, TENANT, agent_id, by='user:me')
    made.append(copy['id'])
    edited = A.update_agent(repo, TENANT, copy['id'], full_body(copy, goal='내가 고친 목표'))
    assert (edited['goal'], tools_of(edited)) == ('내가 고친 목표', tools_of(copy))


def test_고치기에_빠진_칸이_있으면_빈_값으로_지우지_않고_거절한다(authoring):
    repo, made = authoring
    copy = A.clone_agent(repo, TENANT, 'agent:cooling', by='user:me')
    made.append(copy['id'])
    body = full_body(copy, goal='바꿈')
    del body['tools'], body['persona']
    with pytest.raises(AuthoringError) as refused:
        A.update_agent(repo, TENANT, copy['id'], body)
    assert refused.value.status == 422 and '빠진 칸: persona, tools' in refused.value.message
    after = A.get_agent(repo, TENANT, copy['id'])
    assert (after['goal'], tools_of(after)) == (copy['goal'], tools_of(copy))


@pytest.mark.parametrize('body, says', [
    (dict(name='내 에이전트', goal='점검', tools=['neo4j', 'no-such-server']), '등록되지 않은 도구 서버'),
    (dict(name='내 에이전트', goal='점검', model='gpt-9-ultra'), '연결된 모델(coding) 하나만'),
    (dict(name='냉각 긴급 대응 에이전트', goal='기본과 같은 이름'), '같은 이름'),
    (dict(name='', goal='이름 없음'), '이름'),
    (dict(name='가' * 61, goal='점검'), '이름 칸이 너무 깁니다'),
    (dict(name='내 에이전트', goal='점검', work_rules='no-such-rules'), 'no-such-rules'),
], ids=['등록 안 된 서버', '수업 밖 모델', '같은 이름', '빈 이름', '이름 61자', '없는 업무 규칙'])
def test_받을_수_없는_에이전트는_까닭과_함께_거절되고_만들어지지_않는다(authoring, body, says):
    repo, _ = authoring
    before = {u['id'] for u in repo.list_users(None, TENANT)}
    with pytest.raises(AuthoringError) as refused:
        A.create_agent(repo, TENANT, body, by='user:me')
    assert says in str(refused.value)
    assert {u['id'] for u in repo.list_users(None, TENANT)} == before


def test_연결_검사를_통과하지_않은_학생_서버는_폼에서_까닭과_함께_보이고_붙이면_거절된다(authoring):
    repo, _ = authoring
    store = mcp_registry.store_for(repo)
    store.insert_server(TENANT, 'my-rows', {'type': 'url', 'url': 'http://127.0.0.1:9/mcp', 'transport': 'streamable_http',
                                            'hyd': {'origin': 'user'}})
    option = next(o for o in A.server_options(repo, TENANT) if o['name'] == 'my-rows')
    assert (option['selectable'], option['reason']) == (False, "연결 검사를 통과하지 않은 서버입니다 — '연결 검사'를 먼저 하세요")
    assert all(o['selectable'] for o in A.server_options(repo, TENANT) if o['name'] in mcp_registry.BASE_SERVERS)
    with pytest.raises(AuthoringError) as refused:
        A.create_agent(repo, TENANT, dict(name='내 에이전트', goal='점검', tools=['my-rows']))
    assert option['reason'] in refused.value.message


@pytest.mark.parametrize('versions, latest', [(['1', '2', '9', '10'], '10'), (['1.9', '1.10'], '1.10'), (['2.2', '10.0'], '10.0')],
                         ids=['열 번째 판', '마디 열', '큰 판'])
def test_흐름의_최신_판본은_글자_순이_아니라_숫자_순으로_고른다(versions, latest):
    assert max(versions, key=A.version_key) == latest


def test_에이전트가_맡는_단계는_에이전트_모드와_워커_실행인_단계만이다():
    raw = {'roles': [{'name': '에이전트', 'endpoint': 'sys:agent'}, {'name': '운전원', 'endpoint': 'role:operator'}],
           'activities': [{'id': 'T_agent', 'name': '판단', 'role': '에이전트', 'agentMode': 'COMPLETE', 'orchestration': 'cliagents'},
                          {'id': 'T_human', 'name': '승인', 'role': '운전원'},
                          {'id': 'T_other', 'name': '다른 실행기', 'role': '에이전트', 'agentMode': 'COMPLETE', 'orchestration': 'crewai'},
                          {'id': 'T_named', 'name': '지정', 'role': '운전원', 'agent': 'agent:cooling', 'agentMode': 'COMPLETE'}]}
    assert A.agent_steps_of('d', raw) == [
        {'definition_id': 'd', 'activity_id': 'T_agent', 'name': '판단', 'default_agents': ['sys:agent']},
        {'definition_id': 'd', 'activity_id': 'T_named', 'name': '지정', 'default_agents': ['agent:cooling']}]


# ---------------------------------------------------------------- 실제 process(학생 PC 구성)
def test_등록된_흐름의_최신_판본으로_배정_단계를_정한다(world):
    latest = {d['id']: d['prod_version'] for d in A.latest_definitions(world.rt)}
    rows = world.rt.repo.list_definitions(TENANT)
    for def_id, version in latest.items():
        mine = [r['prod_version'] for r in rows if r['id'] == def_id]
        assert not mine or version == max(mine, key=A.version_key)


def test_기준으로_되돌리기는_만든_에이전트_스킬_역할을_지우고_센_수를_돌려준다(world):
    repo = world.rt.repo
    agent = A.create_agent(repo, TENANT, dict(name='되돌리기 시험', goal='점검'))
    A.create_skill(repo, TENANT, {'skill_name': 'reset-check', 'description': '점검', 'content': '# 점검\n1. 본다'})
    A.attach_skill(repo, TENANT, agent['id'], 'reset-check')
    role = A.create_role(repo, TENANT, {'name': '되돌리기 시험 역할'})
    out = A.reset(world.rt, by='수강생')
    assert (out['agents'], out['skills'], out['attachments'], out['roles']) == (1, 1, 1, 1)
    assert not repo.list_users([agent['id'], role['id']], TENANT)


def test_역할을_만들면_이_PC의_담당자가_그_역할의_구성원이다(world):
    """사람은 담당자 한 명이고 모든 역할의 구성원이다 — 역할에 사람을 넣고 빼는 길은 없고, 만들 때 넣는 이 한 곳뿐이다.
    구성원이 없으면 그 역할의 사람 단계가 작업함에 뜨지 않아 처리 건이 멈춘다."""
    from procsvc import inbox
    repo = world.rt.repo
    role = A.create_role(repo, TENANT, {'name': '구성원 시험 역할'})
    try:
        assert role['members'] == ['user:me'] == inbox.members_of(repo, TENANT, role['id'])
        assert role['id'] in inbox.roles_of(repo, TENANT, 'user:me')
    finally:
        A.delete_role(world.rt, role['id'], by='user:me')


def test_기본_담당을_찾을_수_없는_열린_단계가_있으면_에이전트를_지우지_않고_409(world):
    """옛 판: 경고만 남기고 넘어간 뒤 에이전트를 지워, 그 단계가 지워진 에이전트 id 로 남아 프로필 없이 실행됐다(P3-24)."""
    import json
    from conftest import DEFINITIONS, start_handover
    rt = world.rt
    raw = json.loads((DEFINITIONS / 'shift_handover_v1.json').read_text(encoding='utf8'))
    raw.update(processDefinitionId='orphan_test', processDefinitionName='기본 담당 없는 시험 흐름')
    raw['roles'] = [dict(r, endpoint='') if r['name'] == '인계안 에이전트' else r for r in raw['roles']]
    rt.register_definition(raw)
    agent = A.create_agent(rt.repo, TENANT, dict(name='고아 시험 에이전트', goal='점검'))
    inst = None
    try:
        rt.repo.put_agent_map({'tenant_id': TENANT, 'proc_def_id': 'orphan_test', 'activity_id': 'task:draft', 'agent_id': agent['id'],
                               'origin': A.USER, 'by_user': '수강생'})
        inst = start_handover(rt, definition='orphan_test', version=raw['version'])
        [row] = [w for w in rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id'], limit=None) if w['activity_id'] == 'task:draft']
        assert row['user_id'] == agent['id']
        with pytest.raises(AuthoringError) as refused:
            A.delete_agent(rt, agent['id'], by='수강생')
        assert refused.value.status == 409 and '기본 담당을 찾을 수 없는 열린 단계' in refused.value.message
        assert A.get_agent(rt.repo, TENANT, agent['id'])                       # 지우지 않았다
    finally:
        # 이 시험이 만든 것은 이 시험이 치운다 — 열린 「인계안 작성」을 남기면 뒤 시험(test_config_bundle)의 되돌리기 · 불러오기가
        # 「기본 담당을 찾을 수 없는 열린 단계」로 거절됐다(FC 검증 P3-01, 순서 의존). 집히지 않은 AI 단계를 닫는 제품 길은 없다(실행 취소는
        # 실행 중일 때만, 닫기는 멈춘 단계만) — 그래서 world 준비(EngineWorld)와 같은 시험 정리로 이 처리 건과 그 단계를 취소 표시한다
        rt.repo.drop_agent_map(TENANT, 'orphan_test', 'task:draft')
        if inst is not None:
            import psycopg
            with psycopg.connect(world.dsn) as db, db.transaction():
                db.execute("UPDATE todolist SET status='CANCELLED' WHERE proc_inst_id=%s AND status NOT IN ('DONE','CANCELLED')", (inst['proc_inst_id'],))
                db.execute("UPDATE bpm_proc_inst SET status='CANCELLED' WHERE proc_inst_id=%s", (inst['proc_inst_id'],))
        A.delete_agent(rt, agent['id'], by='수강생')


# ---------------------------------------------------------------- 역할의 정본은 업무 DB 하나 — 지식 그래프의 Role 은 그 투영(전수검사 11-#8)
def _graph_roles(world):
    return {r['id']: (r['name'], r['level']) for r in world.stack.graph._run('MATCH (r:Role) RETURN r.id AS id, r.name AS name, r.level AS level')}


def _db_roles(world):
    from procsvc import inbox
    return {u['id']: u.get('username') for u in inbox.role_users(world.rt.repo, TENANT) if not u.get('is_agent')}


def test_업무_DB의_역할과_지식_지도의_역할은_같은_목록이고_지식이_아는_등급은_그대로다(world):
    """전에는 두 목록이 따로였다: 지식에는 품질팀장 · 공장장이 있고 인계자 · 인수자가 없었으며, 업무 DB 는 그 반대였다."""
    A.project_roles(world.rt.repo, TENANT, world.stack.graph._run)
    graph, db = _graph_roles(world), _db_roles(world)
    assert {rid: name for rid, (name, _) in graph.items()} == db
    assert {'role:quality-mgr', 'role:plant-mgr', 'role:shift-out', 'role:shift-in'} <= set(db)
    # 지식(시드)이 정한 등급은 덮지 않고, 지식에 없던 역할은 종류에서 정한다(운전원 종류 = 1)
    assert (graph['role:plant-mgr'][1], graph['role:purchasing'][1], graph['role:shift-out'][1]) == (3, 1, 1)
    assert A.project_roles(world.rt.repo, TENANT, world.stack.graph._run) == {'created': [], 'renamed': [], 'removed': [], 'kept': []}   # 같으면 쓰지 않는다
    # 이름은 업무 DB 가 정한다: DB 에서 바뀐 이름은 지식의 역할로 옮기되, 지식이 아는 등급(공장장 3)은 종류에서 온 값(2)으로 덮지 않는다
    with psycopg.connect(world.dsn, autocommit=True) as db:
        db.execute("UPDATE users SET username='공장 총괄' WHERE id='role:plant-mgr'")
    try:
        assert A.project_roles(world.rt.repo, TENANT, world.stack.graph._run)['renamed'] == ['role:plant-mgr']
        assert _graph_roles(world)['role:plant-mgr'] == ('공장 총괄', 3)
    finally:
        with psycopg.connect(world.dsn, autocommit=True) as db:
            db.execute("UPDATE users SET username='공장장' WHERE id='role:plant-mgr'")
        A.project_roles(world.rt.repo, TENANT, world.stack.graph._run)


def test_지식이_아는_역할은_모두_담당자가_그_역할로_승인할_수_있다(world):
    """문서가 「품질팀장 승인」을 쓰면 적재는 됐는데 승인이 「구성원 아님」으로 막혔다 — 지식의 역할이 업무 DB 에 없었다."""
    from procsvc import inbox
    A.project_roles(world.rt.repo, TENANT, world.stack.graph._run)
    for role in _graph_roles(world):
        assert inbox.check_actor(world.rt.repo, TENANT, 'user:me', role) == 'user:me', role


@pytest.fixture
def my_role(world):
    """포털에서 만든 역할 하나(HTTP — 지식 그래프로 바로 옮겨진다)와, 그 역할을 승인 역할로 쓰는 화면 조치 방법을 만드는 함수. 끝나면 둘 다 지운다."""
    from procsvc import skill_graph
    from procsvc.main import SKILL_Q
    status, role = world.api('POST', '/api/roles', {'name': '역할 정본 시험 담당', 'key': 'u-source-test', 'by': 'user:me'})
    assert status == 201 and role['id'] in role['knowledge']['created'], role

    def skill():
        fm = world.stack.graph._run('MATCH (f:FailureMode) RETURN f.id AS id ORDER BY f.id LIMIT 1')[0]['id']
        with world.stack.graph.driver.session() as session:
            return skill_graph.write(session, SKILL_Q, 'skill:sop-role-01', {
                'name': '역할 시험 조치', 'description': '시험', 'kind': 'work_order', 'sopId': 'SOP-ROLE-01', 'failureMode': fm,
                'relation': 'REMEDIED_BY', 'steps': ['본다'], 'approver': role['id'], 'affects': None}, create=True, by='user:me')
    yield role, skill
    world.stack.graph._run("MATCH (k:Skill {id:'skill:sop-role-01'}) OPTIONAL MATCH (k)-[:HAS_STEP]->(s) DETACH DELETE k, s")
    if role['id'] in _db_roles(world):
        A.delete_role(world.rt, role['id'], by='user:me')


def test_포털에서_만든_역할은_문서_적재_검사와_조치_방법의_승인_역할로_쓸_수_있다(world, my_role):
    """포털에서 만든 역할은 업무 DB 에만 생겨, 그 역할을 승인 역할로 쓰는 문서는 「지금 지식에 없습니다」로 적재할 수 없었다."""
    from procsvc import manual_knowledge
    role, skill = my_role
    with world.stack.graph.driver.session() as session:
        assert role['id'] in {r['id'] for r in manual_knowledge.catalog(session)['roles']}        # 문서 적재 전 검사가 읽는 지금 지식
    assert skill()['approver'] == {'id': role['id'], 'name': '역할 정본 시험 담당', 'level': 2}


def test_조치_방법이_승인_역할로_쓰는_역할은_지우지_않고_무엇이_쓰는지_말한다(world, my_role):
    role, skill = my_role
    skill()
    with pytest.raises(AuthoringError) as refused:
        A.delete_role(world.rt, role['id'], by='user:me')
    assert refused.value.status == 409 and '역할 시험 조치' in refused.value.message and role['id'] in _graph_roles(world)


def test_기준으로_되돌리기도_조치_방법이_쓰는_역할은_남긴다(world, my_role):
    role, skill = my_role
    skill()
    assert role['id'] in A.reset(world.rt, by='user:me')['kept_roles'] and role['id'] in _db_roles(world) and role['id'] in _graph_roles(world)


def test_역할을_지우면_지식_지도의_역할도_없어진다(world, my_role):
    role, _ = my_role
    gone = A.delete_role(world.rt, role['id'], by='user:me')
    assert gone['knowledge']['removed'] == [role['id']] and role['id'] not in _graph_roles(world)
