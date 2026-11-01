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
    copy = A.clone_agent(repo, TENANT, agent_id, by='user:kim-op')
    made.append(copy['id'])
    assert (A.origin_of(copy), tools_of(copy), copy.get('work_rules')) == (A.USER, tools_of(source), source.get('work_rules'))
    assert [r['skill_name'] for r in repo.list_agent_skills(TENANT, copy['id'])] == [r['skill_name'] for r in repo.list_agent_skills(TENANT, agent_id)]


@pytest.mark.parametrize('agent_id', SEED_AGENTS)
def test_복제한_에이전트는_모든_칸을_보내_고칠_수_있다(authoring, agent_id):
    repo, made = authoring
    copy = A.clone_agent(repo, TENANT, agent_id, by='user:kim-op')
    made.append(copy['id'])
    edited = A.update_agent(repo, TENANT, copy['id'], full_body(copy, goal='내가 고친 목표'))
    assert (edited['goal'], tools_of(edited)) == ('내가 고친 목표', tools_of(copy))


def test_고치기에_빠진_칸이_있으면_빈_값으로_지우지_않고_거절한다(authoring):
    repo, made = authoring
    copy = A.clone_agent(repo, TENANT, 'agent:cooling', by='user:kim-op')
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
    (dict(name='내 에이전트', goal='점검', model='gpt-9-ultra'), '수업 모델'),
    (dict(name='냉각 긴급 대응 에이전트', goal='기본과 같은 이름'), '같은 이름'),
    (dict(name='', goal='이름 없음'), '이름'),
    (dict(name='가' * 61, goal='점검'), '이름 칸이 너무 깁니다'),
    (dict(name='내 에이전트', goal='점검', work_rules='no-such-rules'), 'no-such-rules'),
], ids=['등록 안 된 서버', '수업 밖 모델', '같은 이름', '빈 이름', '이름 61자', '없는 업무 규칙'])
def test_받을_수_없는_에이전트는_까닭과_함께_거절되고_만들어지지_않는다(authoring, body, says):
    repo, _ = authoring
    before = {u['id'] for u in repo.list_users(None, TENANT)}
    with pytest.raises(AuthoringError) as refused:
        A.create_agent(repo, TENANT, body, by='user:kim-op')
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
