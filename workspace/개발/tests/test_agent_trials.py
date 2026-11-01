"""에이전트 시험 비교(procsvc/agent_trials.py) — 같은 입력 스냅숏으로 두 에이전트를 시험해 나란히 비교한다. 처리 건 · 명령을 만들지 않는다.
설정 읽기 · 저장소는 실제 DB, 시험 실행은 실제 agent 서비스(stack)."""
import pytest

from procsvc import agent_trials, procdb

TENANT = 'hyd'


def call(server, tool, args=None, status='DONE', summary=''):
    return {'server': server, 'tool': tool, 'args': args or {}, 'status': status, 'summary': summary}


@pytest.mark.parametrize('a, b, rows', [
    ([call('s', 'x'), call('s', 'y')], [call('s', 'x'), call('s', 'y')], [(0, 0, True), (1, 1, True)]),
    ([call('s', 'x')], [call('s', 'x'), call('s', 'z')], [(0, 0, True), (None, 1, False)]),
    ([call('s', 'x', summary='1')], [call('s', 'x', summary='2')], [(0, 0, False)]),                # 같은 호출, 다른 결과
    ([], [], []),
], ids=['같음', 'B에만 하나 더', '결과 요약 다름', '둘 다 없음'])
def test_두_도구_호출_순서를_맞춰_같은_호출과_한쪽에만_있는_호출을_가린다(a, b, rows):
    assert [(r['a'], r['b'], r['same']) for r in agent_trials.align(a, b)] == rows


@pytest.mark.parametrize('variant, says', [({'without_tools': ['not-mine']}, 'not-mine'), ({'without_skills': ['ghost']}, 'ghost')],
                         ids=['없는 도구', '없는 스킬'])
def test_에이전트_설정에_없는_도구_스킬은_뺄_수_없다(variant, says):
    profile = {'tools': ['neo4j'], 'skills': [{'name': 'fan-max'}]}
    with pytest.raises(ValueError) as refused:
        agent_trials.apply_variant(profile, variant)
    assert says in str(refused.value)


def test_변형은_이번_시험에만_도구와_스킬을_뺀다():
    profile = {'id': 'a', 'tools': ['neo4j', 'hyd-dmn'], 'skills': [{'name': 'fan-max'}, {'name': 'load-cut'}]}
    used, variant = agent_trials.apply_variant(profile, {'without_tools': 'neo4j', 'without_skills': ['load-cut']})
    assert (used['tools'], [k['name'] for k in used['skills']]) == (['hyd-dmn'], ['fan-max'])
    assert profile['tools'] == ['neo4j', 'hyd-dmn']                           # 저장된 설정은 그대로


def test_시험에_고를_에이전트는_붙인_스킬_본문과_도구_서버를_그대로_읽는다(world):
    out = agent_trials.agent_profiles(world.rt)
    agents = {a['id']: a for a in out['agents']}
    assert 'sys:scada' not in agents                                          # 시스템 수행자는 시험하지 않는다
    assert agents['agent:pm-plan']['tools'] == ['neo4j', 'hyd-dmn', 'enterprise-maint']
    attached = [r['skill_name'] for r in world.rt.repo.list_agent_skills(TENANT, 'agent:cooling')]
    assert attached and [k['name'] for k in agents['agent:cooling']['skills']] == attached
    assert all(k['content'] and 'missing' not in k for k in agents['agent:cooling']['skills'])
    assert set(out['tenant_servers']) >= {'neo4j', 'hyd-dmn', 'enterprise'}


def test_도구를_적지_않은_에이전트는_시험에서도_실제_실행처럼_모든_도구_서버를_쓴다(world):
    """옛 판: 빈 목록을 넘겨 시험에서는 도구 없이 판단했다 — 실제 실행(지정 없음 = 모든 서버)과 달랐다(FG → FC)."""
    from procsvc import agent_authoring
    agent = agent_authoring.create_agent(world.rt.repo, TENANT, dict(name='도구 지정 없는 시험', goal='점검'))
    try:
        out = agent_trials.agent_profiles(world.rt)
        mine = next(a for a in out['agents'] if a['id'] == agent['id'])
        assert mine['tools'] == out['tenant_servers']
        used, _ = agent_trials.apply_variant(mine, {'without_tools': ['neo4j']})
        assert used['tools'] == [s for s in out['tenant_servers'] if s != 'neo4j']
    finally:
        agent_authoring.delete_agent(world.rt, agent['id'], by='수강생')


def test_시나리오_경보가_열지_않는_흐름만_맡는_에이전트에는_시험이_그_일을_재지_못하는_까닭이_붙는다(world):
    agents = {a['id']: a for a in agent_trials.agent_profiles(world.rt)['agents']}
    for business in ('agent:pm-plan', 'agent:spare-buy'):                  # 정기 정비 · 예비품 구매 — 업무 경보가 여는 흐름
        assert '재지 못합니다' in (agents[business]['trial_note'] or ''), business
    assert agents['sys:agent']['trial_note'] is None                        # 설비 이상 흐름을 맡는다


def test_되돌리기는_이_테넌트의_시험_기록과_입력_스냅숏을_지운다(pg_dsn):
    store = agent_trials.store_for(procdb.PgRepo(pg_dsn))
    store.reset(TENANT)
    snap = store.create_snapshot(TENANT, agent_trials.BY_KEY['cooler'])
    store.save_trial({'id': 'TRY-test-1', 'tenant_id': TENANT, 'snapshot_id': snap['id'], 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION',
                      'agent_id': 'sys:agent', 'setting': {}, 'variant': {}, 'status': 'EVALUATED', 'fingerprint': 'f', 'result': {},
                      'created_at': agent_trials._now()})
    assert store.reset(TENANT) == {'trials': 1, 'snapshots': 1}
    assert store.list_trials(TENANT) == []


def test_같은_입력으로_두_에이전트를_시험하면_비교가_붙고_처리_건은_생기지_않는다(world):
    before = len(world.rt.repo.list_instances(limit=None, tenant_id=TENANT))
    svc = agent_trials.TrialService(world.rt)
    out = svc.run({'scenario': 'cooler', 'a': {'agent': 'sys:agent'}, 'b': {'agent': 'sys:agent', 'variant': {'without_tools': ['enterprise']}}})
    assert out['a']['snapshot_id'] == out['b']['snapshot_id'] and out['diff']['same_input'] is True
    assert len(world.rt.repo.list_instances(limit=None, tenant_id=TENANT)) == before


def test_고정_시나리오가_아니면_까닭과_함께_거절한다(world):
    with pytest.raises(ValueError) as refused:
        agent_trials.TrialService(world.rt).run({'scenario': 'boiler', 'a': {'agent': 'sys:agent'}})
    assert '고정 시나리오가 아닙니다' in str(refused.value)
