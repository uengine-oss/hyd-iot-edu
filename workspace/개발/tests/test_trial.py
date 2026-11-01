"""에이전트 시험 실행(it/agent/agentsvc/trial.py) — 에이전트 설정 하나로 읽기 전용 판단, 스킬 본문의 도구 언급 순서가 절차,
같은 입력 묶음(Snapshot)으로 A · B 를 같은 조건에서 비교. 실제 agent 서비스 · 그래프 · 업무 시스템을 지난다."""
import json
import urllib.error
import urllib.request

import pytest

from agentsvc import trial

PATTERNS = ['COOLER_DEGRADATION', 'PUMP_WEAR', 'PM_DUE']


@pytest.mark.parametrize('server, business', [
    ('enterprise', True), ('enterprise-maint', True), ('enterprise-purchase', True), ('enterprisex', False), ('hyd-dmn', False),
], ids=['업무', '정비 C2', '구매 C2', '이름만 비슷', '판단 엔진'])
def test_업무_도구_서버_계열은_enterprise_와_그것을_나눈_서버다(server, business):
    """P3-14: 정비 · 구매로 나눈 서버를 가진 에이전트는 시험 실행에서 업무 사실을 못 읽었다."""
    assert trial.enterprise_family(server) is business


@pytest.mark.parametrize('text, scenario, applies, why', [
    ('냉각 점검 순서', {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'}, True, None),
    ('HYD-02 펌프만', {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'}, False, '다른 설비(HYD-02)'),
    ('PUMP_WEAR 일 때', {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'}, False, '다른 이상 패턴(PUMP_WEAR)'),
    ('HYD-01 COOLER_DEGRADATION', {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'}, True, None),
], ids=['가리키는 곳 없음', '다른 설비', '다른 패턴', '이 설비 이 패턴'])
def test_스킬은_본문이_가리키는_설비_패턴에서만_적용된다(text, scenario, applies, why):
    ok, reason = trial.skill_scope({'name': 's', 'content': text}, scenario, PATTERNS)
    assert ok is applies and (why is None or why in reason)


def test_스킬_절차는_본문의_도구_언급_순서이고_코드_블록은_차례로_짝짓는다():
    content = ('먼저 `mes_orders`로 주문을 보고 cmms_history 를 본다. 그다음 mcp__hyd-dmn__timeseries_query 로\n'
               '```sql\nSELECT 1\n```\n그리고 read_neo4j_cypher 로\n```cypher\nMATCH (n) RETURN n LIMIT 1\n```\n잘 모르는 낱말_하나 · inputs')
    steps = trial.skill_procedure(content)
    assert [s['tool'] for s in steps] == ['mes_orders', 'cmms_history', 'timeseries_query', 'read_neo4j_cypher']
    assert steps[2]['server'] == 'hyd-dmn' and steps[2]['sql'] == 'SELECT 1' and steps[3]['cypher'] == 'MATCH (n) RETURN n LIMIT 1'


def test_입력_묶음은_처음_읽은_값과_실패를_그대로_다시_준다():
    snap = trial.Snapshot()
    assert snap.read('k1', 'tool', lambda: {'v': 1})[0::2] == (True, 'live')
    ok, error, source = snap.read('k2', 'tool', lambda: (_ for _ in ()).throw(RuntimeError('업무 시스템이 답하지 않았습니다')))
    assert (ok, source) == (False, 'live') and '답하지 않았습니다' in error
    replay = trial.Snapshot(snap.added)
    assert replay.read('k1', 'tool', lambda: {'v': 2}) == (True, {'v': 1}, 'snapshot')
    assert replay.read('k2', 'tool', lambda: {'v': 2})[0] is False and replay.added == {}


def test_쓰기_Cypher_는_그래프에_보내기_전에_거절한다():
    with pytest.raises(ValueError) as e:
        trial.read_cypher(None, 'MATCH (n) DETACH DELETE n')
    assert '쓰기 Cypher' in str(e.value)


# ---------------------------------------------------------------- 실제 agent 서비스
def post(url, body, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'null')


from test_decide import cooling  # noqa: E402,F401 — 같은 설비 상태 준비(30분 보고)


SCENARIO = {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'}
SKILL = {'name': 'order-check', 'description': '주문 확인', 'content': '`mes_orders` 로 이 설비의 생산 주문을 먼저 본다'}


def test_정비_업무_서버를_가진_에이전트는_스킬의_업무_조회를_그_서버로_부른다(cooling):
    """P3-14: 스킬의 mes_orders 가 enterprise 로만 불려 enterprise-maint 를 가진 에이전트는 「도구 없음」으로 막혔다."""
    servers = list(cooling.stack.tools)
    agent = {'id': 'a', 'name': 'A', 'tools': ['hyd-dmn', 'enterprise-maint'], 'skills': [SKILL]}
    status, body = post(cooling.stack.services['agent'].url + '/api/agent/trial',
                        {'scenario': SCENARIO, 'agent': agent, 'tenant_servers': servers})
    assert status == 200, body
    skill_calls = [c for c in body['trial']['calls'] if c['by'] == '스킬 order-check']
    assert [(c['server'], c['tool'], c['status']) for c in skill_calls] == [('enterprise-maint', 'mes_orders', 'DONE')], (
        body['trial']['status'], body['trial']['reason'], body['trial']['agent'])


def test_같은_입력_묶음이면_A_B_가_같은_관측으로_판단하고_도구가_빠진_쪽은_그_까닭으로_막힌다(cooling):
    url, servers = cooling.stack.services['agent'].url + '/api/agent/trial', list(cooling.stack.tools)
    a = {'id': 'a', 'name': 'A', 'tools': ['hyd-dmn', 'enterprise'], 'skills': [SKILL]}
    status, first = post(url, {'scenario': SCENARIO, 'agent': a, 'tenant_servers': servers})
    assert status == 200 and first['added']
    b = dict(a, name='B', tools=['hyd-dmn'])
    status, second = post(url, {'scenario': SCENARIO, 'agent': b, 'entries': first['added'], 'tenant_servers': servers})
    assert status == 200 and second['added'] == {}                          # 새로 읽은 것 없음 = 같은 입력
    assert second['trial']['diagnosis'] == first['trial']['diagnosis']
    blocked = [c for c in second['trial']['calls'] if c['by'] == '스킬 order-check']
    assert blocked and blocked[0]['status'] == 'BLOCKED' and 'enterprise' in blocked[0]['reason']


def test_판단_엔진_도구가_없는_에이전트는_원인_진단을_할_수_없다고_말한다(cooling):
    status, body = post(cooling.stack.services['agent'].url + '/api/agent/trial',
                        {'scenario': SCENARIO, 'agent': {'id': 'c', 'name': 'C', 'tools': ['enterprise'], 'skills': []},
                         'tenant_servers': list(cooling.stack.tools)})
    assert status == 200 and body['trial']['status'] == 'NO_ENGINE_TOOL' and 'hyd-dmn' in body['trial']['reason']


@pytest.mark.parametrize('content, status, part, reason', [
    ('`scm_suppliers` 로 P-PMP-SEAL 의 공급사를 본다', 'DONE', 'P-PMP-SEAL', None),
    ('`scm_suppliers` 로 P-PMP-SEAL 과 P-RTN-FLT 의 공급사를 본다', 'FAILED', None, '하나로 정할 수 없습니다(P-PMP-SEAL, P-RTN-FLT)'),
    ('`scm_suppliers` 로 공급사를 본다', 'FAILED', None, '본문에 P-로 시작하는 부품 번호가 없음'),
], ids=['부품 하나', '부품 둘', '부품 없음'])
def test_공급사_조회_스킬은_본문에_적힌_부품_하나로_부르고_못_정하면_그_까닭으로_막힌다(cooling, content, status, part, reason):
    """G1-28: 공급사 조회 인자가 P-CLR-CORE 로 고정돼 스킬이 적은 부품이 무시됐다."""
    skill = {'name': 'supplier-check', 'description': '공급사 확인', 'content': content}
    agent = {'id': 'a', 'name': 'A', 'tools': ['hyd-dmn', 'enterprise'], 'skills': [skill]}
    code, body = post(cooling.stack.services['agent'].url + '/api/agent/trial',
                      {'scenario': SCENARIO, 'agent': agent, 'tenant_servers': list(cooling.stack.tools)})
    assert code == 200, body
    (call,) = [c for c in body['trial']['calls'] if c['by'] == '스킬 supplier-check']
    assert call['status'] == status, call
    if part:
        assert call['args'] == {'part': part}
    else:
        assert reason in call['reason']


def test_시험_실행의_순위는_같은_설비_상태의_수동_판단과_같고_정지_카드도_정지한_설비로_계산한다(cooling):
    """G1-05(시험 배선): 시험 실행(engine_inputs)이 정지 · 세척 카드를 「운전 계속」으로 예측하면 그 카드 점수가 수동 판단과 달라진다."""
    url = cooling.stack.services['agent'].url
    status, d = post(url + '/api/agent/decide', {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'})
    assert status == 200 and 'error_code' not in d, d.get('error')
    agent = {'id': 'a', 'name': 'A', 'tools': ['hyd-dmn', 'enterprise'], 'skills': []}
    status, body = post(url + '/api/agent/trial', {'scenario': SCENARIO, 'agent': agent, 'tenant_servers': list(cooling.stack.tools)})
    assert status == 200, body
    manual = {o['sopId']: o['score'] for o in d['result']['options']}
    trial = {o['sopId']: o['score'] for o in body['trial']['ranking']}
    assert 'SOP-COOL-14' in trial and trial['SOP-COOL-14'] == pytest.approx(manual['SOP-COOL-14'], abs=0.01), (manual, trial)
