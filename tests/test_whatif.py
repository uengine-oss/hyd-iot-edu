"""A7 손익 · What-if · 규칙 바꿔 보기: 손익은 업무 DB 값에서, 경계값은 실제 재계산으로 확인, 원본은 그대로, 같은 입력은 같은 결과."""
import copy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentsvc import cards, whatif
from hydcommon import ranking

ROOT = Path(__file__).resolve().parents[1]
POLICY = (Path(ranking.__file__).with_name('ranking-default.json')).read_text(encoding='utf8')


def T(var, op, val):
    return {'variable': var, 'operator': op, 'value': val}


def R(decision, rule, effect, tests, outputs=(), applies=(), penalty=None, ord_=1, annotation=None):
    return {'decision': decision, 'rule': rule, 'ord': ord_, 'effect': effect, 'penalty': penalty, 'when': rule,
            'annotation': annotation or rule, 'tests': tests, 'outputs': list(outputs), 'applies': list(applies),
            'penalizes': ['msr:mtbf'] if effect == 'PENALTY' else [], 'sources': ['HM-x']}


COOL = ['skill:fan-max', 'skill:fan-max-derate', 'skill:derate-night-clean', 'skill:wo-cooler-clean']
# 그래프(it/neo4j/v2/instances.cypher)의 쿨러 규칙과 같은 모양 — 후보 · 규정 · 순위
DMN = [
    R('dec:action-candidates', 'rule:cand-cooler', 'SELECT', [T('failure_mode', '==', 'fm:cooling-loss')], COOL),
    R('dec:compliance', 'rule:ts1-hard', 'EXCLUDE', [T('forecast_ts1', '>=', 65)], ord_=2),
    R('dec:compliance', 'rule:auto-mode', 'EXCLUDE', [T('skill_kind', '==', 'control'), T('plc_mode', '!=', 'REMOTE_AUTO')], applies=COOL[:3], ord_=3),
    R('dec:compliance', 'rule:ts1-warn', 'WARN', [T('forecast_ts1', '>=', 55)], applies=['skill:fan-max'], ord_=5),
    R('dec:compliance', 'rule:fan-24h', 'PENALTY', [T('fan100_hours', '>', 24)], applies=COOL[:2], penalty=20, ord_=6,
      annotation='팬 100 % 연속 24시간 초과 시 수명 감점'),
    dict(R('dec:rank-actions', 'rule:rank-value', 'RANK', []), rankingPolicy=POLICY),
]


def act(code, value, kind='command'):
    return {'id': 'action:' + code, 'code': code, 'kind': kind, 'value': value}


def skill(sid, sop, name, kind, actions, relation='MITIGATED_BY', level=1, addresses=()):
    return {'skillId': sid, 'sopId': sop, 'name': name, 'kind': kind, 'description': '', 'relation': relation, 'failureModeId': 'fm:cooling-loss',
            'approver': {'id': 'role:x', 'name': 'x', 'level': level}, 'addresses': list(addresses), 'actions': actions, 'steps': [{'id': sop + '/1'}]}


SKILLS = {s['skillId']: s for s in [
    skill('skill:fan-max', 'SOP-COOL-01', '팬 최대', 'control', [act('FAN_SET', 100)]),
    skill('skill:fan-max-derate', 'SOP-COOL-02', '팬 최대 + 부하 80 %', 'control', [act('FAN_SET', 100), act('LOAD_SET', 80)], level=2),
    skill('skill:derate-night-clean', 'SOP-COOL-03', '부하 70 % + 야간 세척', 'control',
          [act('LOAD_SET', 70), act('WO_CREATE', 'SOP-COOL-04', 'transaction')], level=2, addresses=['cause:cooler-fin-fouling']),
    skill('skill:wo-cooler-clean', 'SOP-COOL-04', '쿨러 핀 세척', 'work_order', [act('WO_CREATE', 'SOP-COOL-04', 'transaction')],
          relation='REMEDIED_BY', level=2, addresses=['cause:cooler-fin-fouling']),
]}


def fc(v):
    return {'sv:ts1': {'variableName': '평형 유온', 'value': v, 'unit': '℃', 'method': 'm', 'id': 'f'}}


FORECASTS = {'skill:fan-max': fc(55.4), 'skill:fan-max-derate': fc(49.0), 'skill:derate-night-clean': fc(52.2), 'skill:wo-cooler-clean': fc(70.0)}


def path(sid, first, measure, name, direction, dir_, strength):
    edges = [{'key': f'{sid}>{first}', 'type': 'AFFECTS', 'source': sid, 'target': first, 'sign': 1 if dir_ > 0 else -1, 'strength': None},
             {'key': f'{first}>{measure}', 'type': 'INFLUENCES', 'source': first, 'target': measure, 'sign': 1, 'strength': strength}]
    return {'skill': sid, 'measure': measure, 'name': name, 'direction': direction, 'owners': ['생산팀'], 'nodes': [sid, first, measure], 'edges': edges,
            'conds': []}


TRADEOFFS = [
    path('skill:fan-max', 'sv:fan-speed', 'msr:energy-use', '전력 사용량', 'DOWN', 1, 'low'),
    path('skill:fan-max-derate', 'sv:fan-speed', 'msr:energy-use', '전력 사용량', 'DOWN', 1, 'low'),
    path('skill:fan-max-derate', 'sv:load', 'msr:throughput', '생산량', 'UP', -1, 'high'),
    path('skill:derate-night-clean', 'sv:load', 'msr:throughput', '생산량', 'UP', -1, 'high'),
    path('skill:wo-cooler-clean', 'sv:fouling', 'msr:availability', '설비 가동률', 'UP', 1, 'medium'),
]
FACTS = {'failure_mode': 'fm:cooling-loss', 'failure_mode_name': '냉각 성능 상실', 'cause': 'cause:cooler-fin-fouling', 'pattern': 'COOLER_DEGRADATION',
         'plc_mode': 'REMOTE_AUTO', 'plc_state': 'RUN', 'fan100_hours': 0.0,
         'order_due_h': 6.0, 'order_penalty_per_h': 120, 'order_customer_tier': 'OEM', 'hot_lot_claim': 3000, 'hot_lot_qty': 800}


def bundle():
    return {'dmn': copy.deepcopy(DMN), 'skills': copy.deepcopy(SKILLS), 'facts': dict(FACTS), 'forecasts': copy.deepcopy(FORECASTS),
            'tradeoffs': copy.deepcopy(TRADEOFFS), 'precedents': [], 'suppliers': {}, 'forecast_contexts': None}


@pytest.fixture()
def ent(tmp_path, monkeypatch):
    """The real enterprise-sim HTTP contract (memory backend = the same seed values as it/supabase/seed.sql)."""
    monkeypatch.setenv('ENTERPRISE_STATE_PATH', str(tmp_path / 'e.sqlite3'))
    from entsim import main as entmain
    monkeypatch.setattr(entmain, 'ent', entmain.MemoryEnterprise())
    entmain.ent.reset()
    client = TestClient(entmain.app)
    calls = []

    def fetch(endpoint, asset):
        p = endpoint.replace('{asset}', asset)
        calls.append(p)
        r = client.get(p)
        r.raise_for_status()
        return r.json()
    return fetch, calls, client


@pytest.fixture()
def mf(ent):
    return whatif.load_money_facts(ent[0], 'HYD-01')


def by_id(ev):
    return {c['id']: c for c in ev['cards']}


# ---------------------------------------------------------------- ① 손익: 업무 DB 값에서
def test_money_items_are_computed_from_business_db_values_with_sources(mf):
    ev = whatif.evaluate(bundle(), mf)
    c = by_id(ev)
    due = mf['values']['mes.due_in_h']['value']
    assert 5.9 < due <= 6.0 and mf['values']['mes.hour_value']['value'] == 50 and mf['values']['erp.penalty_per_h']['value'] == 120
    derate = {i['key']: i for i in c['skill:fan-max-derate']['money']['items']}
    assert derate['production']['value_won'] == round(-50 * due * (1 - 80 / 90) * whatif.WON)
    assert derate['delay']['value_won'] == 0                                       # 1500 ea ÷ (300 × 80/90) = 5.6 h < 6 h
    assert derate['quality']['value_won'] == 0                                     # 예측 49 ℃ < 55 ℃
    fan = {i['key']: i for i in c['skill:fan-max']['money']['items']}
    assert fan['quality']['value_won'] == round(-0.05 * 3000 * whatif.WON)        # QMS 불량 확률 × 클레임
    night = {i['key']: i for i in c['skill:derate-night-clean']['money']['items']}
    assert night['work']['value_won'] == -40 * whatif.WON                          # CMMS 쿨러 핀 세척 작업비 (설비별 정비 기준)
    late = 3 + 1500 / (300 * 70 / 90) - due
    assert night['delay']['value_won'] == round(-120 * late * whatif.WON)
    assert night['failure']['value_won'] == 0 and fan['failure']['value_won'] == round(-900 * due / 1400 * whatif.WON)
    for card in ev['cards']:
        m = card['money']
        assert m['complete'] and m['total_won'] == sum(i['value_won'] for i in m['items'])
        for item in m['items']:
            # 출처 없는 값 0: 값이 있는 항목은 모두 출처가 있고, 업무 DB 필드를 쓴 항목은 그 필드 · 경로를 적는다
            assert item['sources'] and all(s['kind'] in ('데이터', '문서', '가정', '시험값') and s['where'] for s in item['sources'])
    # 화면에 보이는 문장(where · 식 · 라벨)에는 영문 id · 열 이름이 없다 — 원천 위치는 ref에만
    import re
    shown = [s['where'] for c in ev['cards'] for i in c['money']['items'] for s in i['sources']] + \
        [i['formula'] or i.get('missing') or '' for c in ev['cards'] for i in c['money']['items']] + [whatif.summary(ev)]
    assert not [t for t in shown if re.search(r'\b(?:skill|msr|sv|ext|sup|rule|cause|fm):|\b[a-z]+_[a-z_]+\b', t)]
    assert any('MES hour_value = 50' in s['ref'] and '시간당 생산 가치 50 만원/h' in s['where'] for s in derate['production']['sources'] if s.get('ref'))
    assert ev['top']['money'] == 'skill:fan-max-derate'


def test_a_value_missing_from_the_business_db_is_reported_not_counted_as_zero(mf):
    broken = copy.deepcopy(mf)
    broken['values']['mes.hour_value']['value'] = None
    broken['tasks'].pop('SOP-COOL-04')
    c = by_id(whatif.evaluate(bundle(), broken))
    m = c['skill:fan-max']['money']
    assert m['total_won'] is None and not m['complete'] and '생산 감소' in m['missing']
    night = c['skill:derate-night-clean']['money']
    assert {i['key']: i for i in night['items']}['work']['value_won'] is None and 'SOP-COOL-04' in {i['key']: i for i in night['items']}['work']['missing']


def test_parts_use_the_business_db_part_price_and_fx_trial(mf):
    pump = skill('skill:wo-pump-seal', 'SOP-PMP-04', '펌프 축 씰 교체', 'work_order',
                 [act('PR_CREATE', 'sup:b', 'transaction'), act('WO_CREATE', 'SOP-PMP-04', 'transaction')], relation='REMEDIED_BY')
    o = dict(pump, id=pump['skillId'], forecast=[])
    items = {i['key']: i for i in whatif.card_money(o, mf)['items']}
    assert items['parts']['value_won'] == -50 * whatif.WON and items['work']['value_won'] == -60 * whatif.WON   # 씰 표준단가 · 작업비
    assert '표준단가 50만원' in items['parts']['sources'][0]['where'] and 'P-PMP-SEAL' in items['parts']['sources'][0]['ref']
    up = {i['key']: i for i in whatif.card_money(o, mf, {'fx_pct': 10.0, 'part_price_pct': 20.0})['items']}
    assert up['parts']['value_won'] == round(-50 * 1.2 * 1.1 * whatif.WON)
    assert {s['kind'] for s in up['parts']['sources']} >= {'데이터', '시험값', '가정'}


def test_the_money_view_does_not_change_the_existing_decision_ranking(mf):
    b = bundle()
    plain = cards.evaluate(b['dmn'], b['skills'], b['facts'], b['forecasts'], b['tradeoffs'], [], {}, None)
    ev = whatif.evaluate(b, mf)
    assert ev['top']['decision'] == plain['recommended']
    assert [c['id'] for c in ev['cards']] == [o['id'] for o in plain['options']]
    assert by_id(ev)['skill:wo-cooler-clean']['feasible'] is False and by_id(ev)['skill:wo-cooler-clean']['moneyRank'] is None


# ---------------------------------------------------------------- ② 값 바꿔 보기 · 경계값
def _at(b, mf, x, value):
    """경계값 항목 x의 축을 value로 바꿔 다시 계산한 1순위."""
    if x['variable'].startswith('w:'):
        pol = {'weights': {x['variable'][2:]: value}, 'penalties': {}}
        return whatif.evaluate(b, mf, None, pol)['top'][x['kind']]
    if x['variable'].startswith('p:'):
        return whatif.evaluate(b, mf, None, {'weights': {}, 'penalties': {x['variable'][2:]: value}})['top'][x['kind']]
    return whatif.evaluate(b, mf, {x['variable']: value})['top'][x['kind']]


def test_every_boundary_really_changes_the_first_place_when_recomputed(mf):
    b = bundle()
    base = whatif.evaluate(b, mf)['top']
    found = whatif.find_boundaries(b, mf)
    kinds = {(x['kind'], x['variable']) for x in found}
    assert {('money', 'hour_value'), ('money', 'claim'), ('money', 'due_h'), ('decision', 'w:forecast')} <= kinds
    for x in found:
        top = whatif.evaluate(b, mf, x['trial'] or None, x['policy'] or None)['top'][x['kind']]
        assert top == x['topAfter'] == _at(b, mf, x, x['value']) != base[x['kind']], x
        if x['card'] != base[x['kind']]:
            assert top == x['card']
    # 기준값과 경계값 사이(경계 바로 앞)에서는 아직 원래 1순위다
    for x in [y for y in found if y['card'] == base[y['kind']]]:
        eps = (x['value'] - x['base']) * 0.02
        assert _at(b, mf, x, x['value'] - eps) == base[x['kind']], x


def test_claim_boundary_flips_money_first_place_to_the_card_that_keeps_production(mf):
    b = bundle()
    found = [x for x in whatif.find_boundaries(b, mf, ['claim']) if x['kind'] == 'money' and x['card'] == 'skill:fan-max']
    assert len(found) == 1 and found[0]['direction'] == '이하'
    x = found[0]['value']
    assert whatif.evaluate(b, mf, {'claim': x})['top']['money'] == 'skill:fan-max'
    assert whatif.evaluate(b, mf, {'claim': x + 50})['top']['money'] == 'skill:fan-max-derate'


def test_trial_values_are_checked_with_readable_reasons():
    with pytest.raises(ValueError, match='바꿀 수 없는 값'):
        whatif.check_trial({'secret': 1})
    with pytest.raises(ValueError, match='숫자'):
        whatif.check_trial({'due_h': 'abc'})
    with pytest.raises(ValueError, match='허용 범위'):
        whatif.check_trial({'due_h': -1})


# ---------------------------------------------------------------- ④ 규칙 바꿔 보기
def test_one_ranking_weight_changes_the_decision_order(mf):
    b = bundle()
    base = whatif.evaluate(b, mf)
    flipped = None
    for comp in [c['key'] for c in whatif.policy_view(b['dmn'])['components']]:
        for w in (0.0, 3.0, -1.0):
            ev = whatif.evaluate(b, mf, None, whatif.check_policy(b['dmn'], {'weights': {comp: w}}))
            if ev['top']['decision'] != base['top']['decision']:
                flipped = (comp, w, ev['top']['decision'])
                break
        if flipped:
            break
    assert flipped, '가중치 하나로 순위가 바뀌는 항목이 있어야 한다'
    assert whatif.policy_view(b['dmn'])['components'] == whatif.policy_view(DMN)['components']   # 원본 정책 그대로


def test_one_penalty_value_changes_the_score_only_where_the_rule_fires(mf):
    b = bundle()
    b['facts']['fan100_hours'] = 30.0                                     # 24 h 초과 → 감점 규칙 발동
    low = by_id(whatif.evaluate(b, mf, None, {'weights': {}, 'penalties': {'rule:fan-24h': 0.0}}))
    high = by_id(whatif.evaluate(b, mf, None, {'weights': {}, 'penalties': {'rule:fan-24h': 100.0}}))
    assert high['skill:fan-max']['score'] == round(low['skill:fan-max']['score'] - 5, 2)
    assert high['skill:derate-night-clean']['score'] == low['skill:derate-night-clean']['score']
    with pytest.raises(ValueError, match='감점 규칙이 아닙니다'):
        whatif.check_policy(b['dmn'], {'penalties': {'rule:ts1-hard': 5}})
    with pytest.raises(ValueError, match='없는 항목'):
        whatif.check_policy(b['dmn'], {'weights': {'nope': 2}})
    with pytest.raises(ValueError, match='-10 ~ 10'):
        whatif.check_policy(b['dmn'], {'weights': {'bsc': 99}})


# ---------------------------------------------------------------- 원본 불변 · 쓰기 없음
def test_trials_never_touch_the_original_bundle_policy_or_business_db(ent, mf):
    fetch, calls, client = ent
    b = bundle()
    before = whatif.original_fingerprint(b, mf)
    snapshot = copy.deepcopy(b['dmn'])
    whatif.evaluate(b, mf, {'due_h': 1.0, 'claim': 10.0, 'fx_pct': 50.0}, {'weights': {'bsc': 3.0}, 'penalties': {'rule:fan-24h': 90.0}})
    whatif.find_boundaries(b, mf, ['due_h', 'hour_value'])
    whatif.weeks(b, mf, 'skill:fan-max-derate', 4, {'load_pct': 70})
    assert whatif.original_fingerprint(b, mf) == before and b['dmn'] == snapshot
    assert all(not p.startswith('/api/') for p in calls)                  # 업무 DB는 읽기 엔드포인트만
    assert client.get('/api/transactions').json() == []                   # 실행 기록 0


# ---------------------------------------------------------------- ③ 몇 주 What-if
def test_weeks_change_one_value_and_show_four_indicators_deterministically(mf):
    b = bundle()
    r1 = whatif.weeks(b, mf, 'skill:fan-max-derate', 4, {'load_pct': 70})
    r2 = whatif.weeks(bundle(), copy.deepcopy(mf), 'skill:fan-max-derate', 4, {'load_pct': 70})
    assert r1 == r2                                                       # 같은 입력 = 같은 결과
    assert len(r1['base']) == len(r1['changed']) == 4
    for k in ('availability', 'output', 'cost_won', 'profit_won'):
        assert all(row[k] is not None for row in r1['base'])
    assert all(d['output'] < 0 for d in r1['delta'])                      # 부하를 낮추면 매주 생산량이 준다
    for c in r1['coefficients']:
        assert c['kind'] in ('데이터', '문서', '가정', '시험값') and c['source'], c
    assert not r1['missing']


def test_weeks_mitigation_keeps_risk_while_remedy_clears_it_after_week_one(mf):
    b = bundle()
    mitigate = whatif.weeks(b, mf, 'skill:fan-max', 4)
    remedy = whatif.weeks(b, mf, 'skill:derate-night-clean', 4)
    assert all(r['failure_p'] > 0 for r in mitigate['base'])
    assert all(r['failure_p'] == 0 for r in remedy['base'])
    assert remedy['base'][0]['availability'] < 100 and remedy['base'][1]['availability'] == 100     # 첫 주 세척 정지 뒤 정상
    assert remedy['base'][1]['load'] == 90 and mitigate['base'][3]['load'] == 90                     # fan-max는 부하 명령 없음
    with pytest.raises(ValueError, match='값 하나'):
        whatif.weeks(b, mf, 'skill:fan-max', 4, {'due_h': 3, 'claim': 1})
    with pytest.raises(ValueError, match='없는 카드'):
        whatif.weeks(b, mf, 'skill:none', 4)
    more = whatif.weeks(b, mf, 'skill:fan-max', 4, {'mtbf_h': 700})
    assert all(d['cost_won'] > 0 for d in more['delta'])                 # MTBF가 짧아지면 매주 고장 위험 비용이 는다


# ---------------------------------------------------------------- 업무 DB 계약 (memory · supabase · migration)
def test_cmms_tasks_contract_in_both_backends_and_migration(ent):
    fetch, _, _ = ent
    tasks = {t['sop']: t for t in fetch('/cmms/tasks?asset={asset}', 'HYD-01')['records']}
    assert tasks['SOP-COOL-04']['source'] == 'maintenance_profiles' and tasks['SOP-COOL-04']['stop_h'] == 3
    assert tasks['SOP-PMP-04']['part_no'] == 'P-PMP-SEAL' and tasks['SOP-FAN-04']['stop_h'] == 3
    seal = fetch('/scm/suppliers?part=P-PMP-SEAL', 'HYD-01')
    assert seal['facts']['std_price'] == 50 and seal['records'] == []     # 코어 견적을 씰 견적으로 섞지 않는다
    core = fetch('/scm/suppliers?part=P-CLR-CORE', 'HYD-01')
    assert {r['id'] for r in core['records']} == {'sup:a', 'sup:b', 'sup:c'}
    from entsim.supabase_backend import READS
    assert READS['cmms_tasks'] == ('ent.cmms_tasks', ('asset',))
    sql = (ROOT / 'it/supabase/migrations/20261008000037_cmms_task_standards.sql').read_text(encoding='utf-8')
    for needle in ('create table if not exists ent.task_standards', 'function ent.cmms_tasks(p_asset text)', "'P-PMP-SEAL', '펌프 축 씰 키트', 50",
                   "('SOP-PMP-04', '펌프 축 씰 교체', false, 4, 60, 'P-PMP-SEAL', 1)", 'enable row level security', 'hyd_enterprise_reader'):
        assert needle in sql


# ---------------------------------------------------------------- 에이전트 API (시험 실행 경로 끝까지)
@pytest.fixture()
def api(ent, monkeypatch):
    from agentsvc import main
    fetch, calls, entclient = ent
    monkeypatch.setattr(main.mcp_ent, 'fetch', fetch)
    monkeypatch.setattr(main, 'whatifs', whatif.Sessions())
    monkeypatch.setattr(main, 'kg', object())

    def manual(k, req, capture=None):
        b = bundle()
        if capture is not None:
            capture.update(b)
        res = cards.evaluate(b['dmn'], b['skills'], b['facts'], b['forecasts'], b['tradeoffs'], [], {}, None)
        return {'id': 'DEC-T', 'created': '2026-10-08T00:00:00Z', 'asset': req.asset, 'status': 'EVALUATED', 'result': res,
                'causes': [{'id': 'cause:cooler-fin-fouling', 'name': '쿨러 핀 오염', 'failureMode': '냉각 성능 상실'}]}
    monkeypatch.setattr(main, '_manual_decide', manual)
    return TestClient(main.app), calls, entclient


def test_whatif_api_runs_trials_boundaries_and_weeks_without_writes(api):
    client, calls, entclient = api
    r = client.post('/api/agent/whatif', json={'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'})
    assert r.status_code == 200, r.text
    base = r.json()
    sid = base['id']
    assert base['top'] == base['baseTop'] == {'decision': 'skill:fan-max-derate', 'money': 'skill:fan-max-derate'}
    assert base['original']['unchanged'] and base['variables'] and base['policy']['components']
    t = client.post(f'/api/agent/whatif/{sid}/try', json={'values': {'claim': 500}}).json()
    assert t['top']['money'] == 'skill:fan-max' and '바뀌었습니다' in t['summary'] and t['original']['unchanged']
    assert client.post(f'/api/agent/whatif/{sid}/try', json={}).json()['top'] == base['top']          # 원래대로
    bnd = client.post(f'/api/agent/whatif/{sid}/boundaries', json={}).json()['boundaries']
    assert any(x['variable'] == 'claim' and x['kind'] == 'money' for x in bnd)
    w = client.post(f'/api/agent/whatif/{sid}/weeks', json={'card': 'skill:fan-max', 'weeks': 3, 'change': {'mtbf_h': 700}}).json()
    assert len(w['base']) == 3 and w['change']['label'] == '평균 고장 간격(MTBF)'
    assert client.post(f'/api/agent/whatif/{sid}/try', json={'values': {'due_h': 'x'}}).status_code == 400
    assert client.post(f'/api/agent/whatif/{sid}/try', json={'policy': {'weights': {'nope': 1}}}).status_code == 400
    assert client.post('/api/agent/whatif/WI-none/try', json={}).status_code == 404
    assert all(not p.startswith('/api/') for p in calls) and entclient.get('/api/transactions').json() == []


def test_decide_api_attaches_money_or_a_readable_reason(api, monkeypatch):
    client, _, _ = api
    d = client.post('/api/agent/decide', json={'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'}).json()
    assert all(o['money']['complete'] for o in d['result']['options']) and 'moneyError' not in d
    from agentsvc import main

    def down(*_):
        raise OSError('connection refused')
    monkeypatch.setattr(main.mcp_ent, 'fetch', down)
    d = client.post('/api/agent/decide', json={'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'}).json()
    assert '업무 DB를 읽지 못했습니다' in d['moneyError'] and all('money' not in o for o in d['result']['options'])
    r = client.post('/api/agent/whatif', json={'asset': 'HYD-01'})
    assert r.status_code == 503 and '업무 DB를 읽지 못했습니다' in r.json()['detail']
