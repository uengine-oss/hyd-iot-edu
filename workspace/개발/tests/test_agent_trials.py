"""에이전트 시험 비교(procsvc/agent_trials.py) — 같은 입력 스냅숏으로 두 에이전트를 시험해 나란히 비교한다. 처리 건 · 명령을 만들지 않는다.
설정 읽기 · 저장소는 실제 DB, 시험 실행은 실제 agent 서비스(stack)."""
import re

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


COOLER = 'COOLER_DEGRADATION@HYD-01'            # 시험 시나리오 열쇠 = 이상 패턴@설비(agent_trials.scenarios)


def profiles(world):
    return agent_trials.agent_profiles(world.rt, agent_trials.scenarios(agent_trials.call_patterns()))


def test_변형은_이번_시험에만_도구와_스킬을_뺀다():
    profile = {'id': 'a', 'tools': ['neo4j', 'hyd-dmn'], 'skills': [{'name': 'fan-max'}, {'name': 'load-cut'}]}
    used, variant = agent_trials.apply_variant(profile, {'without_tools': 'neo4j', 'without_skills': ['load-cut']})
    assert (used['tools'], [k['name'] for k in used['skills']]) == (['hyd-dmn'], ['fan-max'])
    assert profile['tools'] == ['neo4j', 'hyd-dmn']                           # 저장된 설정은 그대로


def test_시험에_고를_에이전트는_붙인_스킬_본문과_도구_서버를_그대로_읽는다(world):
    out = profiles(world)
    agents = {a['id']: a for a in out['agents']}
    assert 'sys:scada' not in agents                                          # 시스템 수행자는 시험하지 않는다
    from procsvc.agents_store import csv_list
    stored = csv_list(world.rt.repo.list_users(['agent:pm-plan'], TENANT)[0]['tools'])      # 사용자 표에 저장된 도구 서버(시드)
    assert stored and agents['agent:pm-plan']['tools'] == [s for s in stored if s in out['tenant_servers']]
    attached = [r['skill_name'] for r in world.rt.repo.list_agent_skills(TENANT, 'agent:cooling')]
    assert attached and [k['name'] for k in agents['agent:cooling']['skills']] == attached
    assert all(k['content'] and 'missing' not in k for k in agents['agent:cooling']['skills'])
    assert set(out['tenant_servers']) >= {'neo4j', 'hyd-dmn', 'enterprise'}


def test_도구를_적지_않은_에이전트는_시험에서도_실제_실행처럼_모든_도구_서버를_쓴다(world):
    """옛 판: 빈 목록을 넘겨 시험에서는 도구 없이 판단했다 — 실제 실행(지정 없음 = 모든 서버)과 달랐다(FG → FC)."""
    from procsvc import agent_authoring
    agent = agent_authoring.create_agent(world.rt.repo, TENANT, dict(name='도구 지정 없는 시험', goal='점검'))
    try:
        out = profiles(world)
        mine = next(a for a in out['agents'] if a['id'] == agent['id'])
        assert mine['tools'] == out['tenant_servers']
        used, _ = agent_trials.apply_variant(mine, {'without_tools': ['neo4j']})
        assert used['tools'] == [s for s in out['tenant_servers'] if s != 'neo4j']
    finally:
        agent_authoring.delete_agent(world.rt, agent['id'], by='user:me')


def test_시나리오_경보가_열지_않는_흐름만_맡는_에이전트에는_시험이_그_일을_재지_못하는_까닭이_붙는다(world):
    agents = {a['id']: a for a in profiles(world)['agents']}
    for business in ('agent:pm-plan', 'agent:spare-buy'):                  # 정기 정비 · 예비품 구매 — 업무 경보가 여는 흐름
        assert '재지 못합니다' in (agents[business]['trial_note'] or ''), business
    assert agents['sys:agent']['trial_note'] is None                        # 설비 이상 흐름을 맡는다


def test_되돌리기는_이_테넌트의_시험_기록과_입력_스냅숏을_지운다(pg_dsn):
    store = agent_trials.store_for(procdb.PgRepo(pg_dsn))
    store.reset(TENANT)
    snap = store.create_snapshot(TENANT, {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'})
    store.save_trial({'id': 'TRY-test-1', 'tenant_id': TENANT, 'snapshot_id': snap['id'], 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION',
                      'agent_id': 'sys:agent', 'setting': {}, 'variant': {}, 'status': 'EVALUATED', 'fingerprint': 'f', 'result': {},
                      'created_at': agent_trials._now()})
    assert store.reset(TENANT) == {'trials': 1, 'snapshots': 1}
    assert store.list_trials(TENANT) == []


def test_같은_입력으로_두_에이전트를_시험하면_비교가_붙고_처리_건은_생기지_않는다(world):
    before = len(world.rt.repo.list_instances(limit=None, tenant_id=TENANT))
    svc = agent_trials.TrialService(world.rt)
    out = svc.run({'scenario': COOLER, 'a': {'agent': 'sys:agent'}, 'b': {'agent': 'sys:agent', 'variant': {'without_tools': ['enterprise']}}})
    assert out['a']['snapshot_id'] == out['b']['snapshot_id'] and out['diff']['same_input'] is True
    assert len(world.rt.repo.list_instances(limit=None, tenant_id=TENANT)) == before


def test_시험_시나리오는_지식_지도의_설비_이상_경보와_설비로_만들고_그_밖이면_까닭과_함께_거절한다(world, course_graph):
    """전수검사 02-3: 시나리오가 쿨러 · 펌프 · 팬 셋을 설비 하나씩 고정한 목록이었고 이 시험이 그 목록을 정답으로 지켰다 — 같은 경보를 다른
    설비에서 시험할 수 없었다. 목록은 지식 지도의 이상 패턴(업무 경보 제외) × 설비이고, 그 밖의 시나리오는 거절한다."""
    from hydcommon.topics import ASSETS
    patterns = agent_trials.call_patterns()
    sensor = sorted(p['code'] for p in patterns if p['code'] not in agent_trials.BUSINESS_PATTERNS)
    expected = sorted(r['code'] for r in course_graph.query('MATCH (p:AnomalyPattern) RETURN p.code AS code')
                      if r['code'] not in agent_trials.BUSINESS_PATTERNS)
    assert sensor == expected and 'COOLER_DEGRADATION' in sensor
    listed = agent_trials.TrialService(world.rt).options()['scenarios']
    assert sorted((s['pattern'], s['asset']) for s in listed) == sorted((p, a) for p in sensor for a in ASSETS)
    assert not any(s['pattern'] in agent_trials.BUSINESS_PATTERNS for s in listed)
    for key in ('boiler', 'PM_DUE@HYD-02', 'COOLER_DEGRADATION@HYD-09'):
        with pytest.raises(ValueError) as refused:
            agent_trials.TrialService(world.rt).run({'scenario': key, 'a': {'agent': 'sys:agent'}})
        assert '시나리오 목록에서 고르세요' in str(refused.value), key


def test_시험_비교가_적은_진행_기록에_입력_고정_A_B_비교가_차례로_남는다(world):
    """시험 비교는 두 에이전트의 판단이 모두 끝나야 결과를 준다 — 그동안 화면이 읽는 진행 기록에 실제 단계와 결과가 남는지(포털과 같은 라우트)."""
    import uuid
    rid = str(uuid.uuid4())
    status, out = world.api('POST', '/api/agent-trials/run', {'request_id': rid, 'scenario': COOLER, 'a': {'agent': 'sys:agent'},
                                                              'b': {'agent': 'sys:agent', 'variant': {'without_tools': ['enterprise']}}})
    assert status == 200, out
    seen = world.api('GET', f'/api/progress/{rid}')[1]
    assert seen['state'] == 'done' and seen['kind'] == 'agent_trial'
    steps = {s['key']: s for s in seen['steps']}
    assert list(steps) == ['input', 'side:0', 'side:1', 'compare'] and all(s['state'] == 'ok' for s in steps.values())
    assert steps['input']['note'].startswith('새 입력 스냅숏을 만듦')                 # 지난 입력을 다시 쓰라고 하지 않았다
    fixed = [int(re.search(r'이번에 고정한 입력 값 (\d+)개$', steps[k]['note']).group(1)) for k in ('side:0', 'side:1')]
    assert sum(fixed) == out['snapshot']['entries'] and fixed[0] > 0                 # 입력은 A 가 원천을 읽을 때 고정되고 B 는 그것을 다시 쓴다
    assert steps['side:0']['note'].startswith(agent_trials.said(out['a'])) and f"도구 호출 {len(out['a']['result']['calls'])}회" in steps['side:0']['note']
    assert steps['compare']['note'] == ('두 결과가 같음' if out['diff']['same_result'] else '두 결과가 다름')


def test_한_에이전트만_시험하면_진행_기록에_B와_비교_단계가_없다(world):
    import uuid
    from procsvc import progress
    rid = str(uuid.uuid4())
    work = progress.tracked(rid, 'agent_trial', lambda p: agent_trials.TrialService(world.rt).run({'scenario': COOLER, 'a': {'agent': 'sys:agent'}}, p))
    work()
    assert [(s['key'], s['state']) for s in progress.read(rid)['steps']] == [('input', 'ok'), ('side:0', 'ok')]
