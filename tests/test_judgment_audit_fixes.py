"""2026-10-23 판단 엔진 검수(.evidence/audit2/agent.md 1 · 2 · 3, enterprise.md E5, portal.md P14)를 고친 뒤의 올바른 동작.

1 · E5: 정비 계획의 경과 시간 값(창까지 남은 시간으로 계산한 운전시간)은 36초마다 0.01 h씩 줄어든다. 승인 비교(approval.consented)와
        메모리 백엔드 실행 재확인(maintenance_plan.recheck)이 같은 목록(without_elapsed)으로 그 값만 빼고, 창 · 계수기 · 부품 · 상한은 계속 비교한다.
2: dmn-mcp submit_decision · submit_purchase 는 process 가 저장한 판단만 성공 봉투로 낸다. 거절 사유(decide.SubmitRefused)는 오류 봉투에 그대로 있다.
   evaluate_cards 는 오류를 오류 봉투로, 후보 0개를 결과의 outcome · notice 로 밝힌다.
3: 쿨러 코어 SOP-PUR-13(최단 납기)이 그래프에 공급 관계가 없는 sup:c 를 고르면 그 카드만 불가(사유)이고 SOP-PUR-11 · 12 는 평가된다.
P14: 예측 승인 재검사 거절 문구에 영문 키 대신 한국어 이름을 쓴다.
"""
from copy import deepcopy
from datetime import timedelta

import pytest

from agentsvc import approval, cards, decide, forecasting
from dmn_mcp import tools as dmn
from entsim import data
from entsim.state import EnterpriseState
from hydcommon import maintenance_plan
from hydcommon.maintenance_plan import plan, recheck, without_elapsed

import test_pm_scoped_schedule as scoped
from test_cards import DMN, R, SKILLS, T, TRADE
from test_dmn_mcp import FakeKG, FakeTSDB
from test_purchase_scope_model import runtime_skill


# ---------------------------------------------------------------- 1 · E5: elapsed plan values

def _reschedule_contract():
    basic = [dict(part_no='P-PMP-SEAL', qty=1, name='펌프 축 씰 키트'), dict(part_no='P-RTN-FLT', qty=1, name='리턴 필터 엘리먼트')]
    return dict(version=1, scope='single', stock_effect='preserve', interval_h=2000, tolerance_pct=10,
                model_assets=['HYD-01', 'HYD-02', 'HYD-03'], anchor=dict(source_id='test:pm', quote='q'),
                model_anchor=dict(source_id='test:pm', quote='q'), packages=[
                    dict(interval_h=2000, sop='SOP-PM-21', name='2000', parts=deepcopy(basic)),
                    dict(interval_h=4000, sop='SOP-PM-22', name='4000', parts=deepcopy(basic)),
                    dict(interval_h=8000, sop='SOP-PM-23', name='8000',
                         parts=deepcopy(basic) + [dict(part_no=None, qty=None, name='작동유', mapping_reason='미상')])])


def _reschedule_facts(following_h, window_id='MW-M', limit=2200.0):
    order = dict(id='WO-1', asset='HYD-02', status='배정됨', completed_at=None,
                 reserved_parts=[dict(part_no='P-PMP-SEAL', qty=1), dict(part_no='P-RTN-FLT', qty=1)])
    row = dict(asset='HYD-02', pm_interval_h=2000, pm_tolerance_pct=10, pm_since_h=1950, pm_total_h=11950, cycle=1,
               following_window_id=window_id, following_window_at='2026-10-30T00:00:00+00:00', hours_at_following_window=following_h,
               night_window_id='MW-N', night_window_at='2026-10-23T19:00:00+00:00', hours_at_next_window=1958.98,
               pm_crew_available=2, existing_pm_order=order, pm_planned_wo='WO-1', service_position=5)
    parts = [dict(part_no='P-PMP-SEAL', available=3, on_hand=4, reserved=1), dict(part_no='P-RTN-FLT', available=4, on_hand=5, reserved=1)]
    return dict(pm_context=dict(asset='HYD-02', records=[row], parts=parts), hours_at_following_window=following_h,
                pm_limit_hours=limit, existing_pm_order=order, pm_planned_wo='WO-1', pm_cycle=1)


RESCHEDULE = dict(skillId='skill:pm-defer', sopId='SOP-PM-13', source_id='test:pm', maintenance_policy=_reschedule_contract(),
                  actions=[dict(code='WO_RESCHEDULE', kind='transaction', target='sys:cmms')])


def _window(window_id='MW-M'):
    return dict(id=window_id, starts_at='2026-10-30T00:00:00+00:00', name='그다음', basis='hours_at_following_window')


def _consent(value):
    return approval.canonical(approval.consented('maintenancePlan', value))


def test_reschedule_plan_consent_ignores_elapsed_hours_at_window():
    reviewed = plan(RESCHEDULE, _reschedule_facts(2120.55), _window())
    later = plan(RESCHEDULE, _reschedule_facts(2120.54), _window())          # 36 s later: same order, window, counter, parts
    assert reviewed['hours_at_window'] != later['hours_at_window']
    assert reviewed['assets'][0]['applicability']['target_hours'] != later['assets'][0]['applicability']['target_hours']
    assert _consent(reviewed) == _consent(later)


def test_reschedule_plan_consent_still_compares_window_limit_order_and_parts():
    reviewed = plan(RESCHEDULE, _reschedule_facts(2120.55), _window())
    other_window = deepcopy(reviewed); other_window['window']['id'] = 'MW-X'
    other_limit = deepcopy(reviewed); other_limit['limit_hours'] = 2400.0
    other_order = deepcopy(reviewed); other_order['ref'] = 'WO-2'
    other_parts = deepcopy(reviewed); other_parts['parts_totals'][0]['qty'] = 2
    other_start = deepcopy(reviewed); other_start['assets'][0]['applicability']['common_start'] = '2026-10-31T00:00:00+00:00'
    for changed in (other_window, other_limit, other_order, other_parts, other_start):
        assert _consent(changed) != _consent(reviewed)


def test_approval_and_execution_recheck_share_one_elapsed_list():
    reviewed = plan(RESCHEDULE, _reschedule_facts(2120.55), _window())
    assert approval.consented('maintenancePlan', reviewed) == without_elapsed(reviewed)
    assert maintenance_plan.ELAPSED_PLAN_FIELDS == ('hours_at_window',)
    assert maintenance_plan.ELAPSED_APPLICABILITY_FIELDS == ('target_hours',)
    stripped = without_elapsed(reviewed)
    assert 'hours_at_window' not in stripped and 'target_hours' not in stripped['assets'][0]['applicability']
    assert reviewed['hours_at_window'] == 2120.55          # the original plan is not changed


def _b_request(state):
    ctx = scoped.context(state)
    row = next(r for r in ctx['records'] if r['asset'] == 'HYD-02')
    window = dict(id=row['night_window_id'], starts_at=row['night_window_at'], basis='hours_at_next_window', label='이번 예정된 정비 시간')
    return dict(skill='skill:schedule-maintenance-scoped', asset='HYD-02', decision='DEC-B', option='skill:pm-source', by='t',
                params=dict(task='원문 정비', plan=plan(scoped.skill('single'), dict(pm_context=ctx), window)))


def test_memory_scoped_schedule_runs_when_approved_a_minute_after_the_decision(monkeypatch):
    # E5: hours_at_next_window fell 1958.99 -> 1958.98 during the minute; window, counter, package and parts did not change
    state = EnterpriseState()
    req = _b_request(state)
    real_now = data._now
    monkeypatch.setattr(data, '_now', lambda: real_now() + timedelta(seconds=60))
    assert state.execute(req)['ref'].startswith('WO-')


def test_memory_scoped_schedule_still_refuses_changed_counter_or_window():
    state = EnterpriseState()
    req = _b_request(state)
    approved = req['params']['plan']
    ctx = scoped.context(state)
    changed = deepcopy(approved); changed['assets'][0]['expected_counter']['pm_since_h'] += 1
    with pytest.raises(ValueError, match='변경되었습니다'):
        recheck(changed, ctx)
    moved = deepcopy(approved); moved['window']['starts_at'] = '2000-01-01T00:00:00+00:00'
    with pytest.raises(ValueError):
        recheck(moved, ctx)


# ---------------------------------------------------------------- 2: dmn-mcp registration envelopes

class KG(FakeKG):
    def t1_causes(self, pattern, asset):
        return [{"causeId": "cause:fouling", "cause": "오염", "prior": 0.6, "failureModeId": "fm:cool", "failureMode": "냉각"}]
    def dmn(self): return deepcopy(DMN)
    def inputs(self): return []
    def skills(self, ids): return [deepcopy(s) for s in SKILLS.values()]
    def tradeoffs(self, ids): return deepcopy(TRADE)
    def precedents(self, fm): return []
    def suppliers(self): return {}
    def roles(self): return [{'id': 'role:x', 'name': 'x', 'level': 1, 'deptName': 'd'}]


@pytest.fixture
def cooler(monkeypatch):
    monkeypatch.setattr(forecasting, 'candidates', lambda kg, asset, skills: ({}, None))
    monkeypatch.setattr(decide, 'gather_facts', lambda inputs, asset, known, tsdb, strict=False:
                        (dict(known, plc_state='RUN', plc_mode='REMOTE_AUTO', fan100_hours=0), []))
    return dmn.DmnTools(kg=KG(), tsdb=FakeTSDB())


def _submit(tool):
    return dmn.enveloped(lambda: tool.submit_decision('HYD-01', 'COOLER_DEGRADATION', 'cause:fouling', 'fm:cool', 'INC-1'))()


def _refuse(monkeypatch, exc):
    def submit(payload):
        raise exc
    monkeypatch.setattr(decide, 'submit', submit)


def _refused(code, reason):
    exc = decide.SubmitRefused(f'process 가 판단 등록을 거절했습니다 (HTTP {code}): {reason}')
    exc.status = code
    return exc


def test_submit_decision_refused_by_process_is_an_error_with_the_process_reason(cooler, monkeypatch):
    reason = '판단을 생산할 작업의 소유권/판본이 일치하지 않습니다'
    _refuse(monkeypatch, _refused(409, reason))
    out = _submit(cooler)
    assert out['result'] == 'error' and out['error_kind'] == 'INVALID', out
    assert 'HTTP 409' in out['message'] and reason in out['message']
    assert 'document' not in out and 'EVAL-' not in out['message']
    assert cooler.registry.all()[0]['error_code'] == 'SUBMIT_REFUSED'


def test_submit_decision_process_5xx_or_unreachable_is_unknown_error(cooler, monkeypatch):
    _refuse(monkeypatch, _refused(502, 'bad gateway'))
    out = _submit(cooler)
    assert out['result'] == 'error' and out['error_kind'] == 'UNKNOWN' and 'bad gateway' in out['message']
    _refuse(monkeypatch, OSError('connection refused'))
    out = _submit(cooler)
    assert out['result'] == 'error' and out['error_kind'] == 'UNKNOWN'
    assert 'connection refused' in out['message'] and 'process' in out['message']


def test_submit_decision_success_returns_the_stored_dec_id(cooler, monkeypatch):
    seen = []
    monkeypatch.setattr(decide, 'submit', lambda payload: seen.append(payload) or {'id': payload['id']})
    out = _submit(cooler)
    assert out['result'] == 'ok' and out['document']['status'] == 'SUBMITTED'
    assert out['document']['id'] == seen[0]['id'] and out['document']['id'].startswith('DEC-')


def test_submit_decision_with_zero_candidates_is_not_a_success(cooler, monkeypatch):
    monkeypatch.setattr(KG, 'skills', lambda self, ids: [])
    posted = []
    monkeypatch.setattr(decide, 'submit', lambda payload: posted.append(payload) or {'id': payload['id']})
    out = _submit(cooler)
    assert out['result'] == 'error' and '후보가 0개' in out['message'] and posted == []


def test_evaluate_cards_states_zero_candidates_and_raises_engine_errors(cooler, monkeypatch):
    run = lambda: dmn.enveloped(lambda: cooler.evaluate_cards('HYD-01', 'COOLER_DEGRADATION', 'cause:fouling', 'fm:cool'))()
    out = run()
    # no forecasts in this fixture: every card has an unknown EXCLUDE condition (forecast_ts1) — stated, not hidden
    assert out['result'] == 'ok' and out['document']['outcome'] == 'no_feasible_option' and out['document']['id'].startswith('EVAL-')
    assert '모두 규정상 제외' in out['document']['notice'] and '저장되지 않은' in out['document']['notice']
    monkeypatch.setattr(KG, 'skills', lambda self, ids: [])
    out = run()
    assert out['result'] == 'ok' and out['document']['outcome'] == 'no_candidates' and '후보 0개' in out['document']['notice']
    def broken(self):
        raise RuntimeError('graph unavailable')
    monkeypatch.setattr(KG, 'dmn', broken)
    out = run()
    assert out['result'] == 'error' and out['error_kind'] == 'UNKNOWN' and 'graph unavailable' in out['message']


@pytest.fixture
def purchase_tool(monkeypatch):
    from agentsvc.tools import mcp_ent
    k = runtime_skill()
    k.update(sopId='SOP-PUR-11', name='공급사 발주')
    rules = [R('dec:action-candidates', 'rule:purchase', 'SELECT', [T('pattern', '==', 'SPARE_BELOW_MIN')], [k['skillId']])]

    class PKG:
        def dmn(self): return deepcopy(rules)
        def inputs(self): return []
        def skills(self, ids): return [deepcopy(k)]
        def tradeoffs(self, ids): return []
        def precedents(self, fm): return []
        def suppliers(self): return {}
        def roles(self): return [{'id': 'role:purchasing', 'name': '구매', 'level': 1, 'deptName': '구매'}]

    facts = dict(pattern='SPARE_BELOW_MIN', spare_gap=-1, need_qty=2, need_by_days=6, spare_part_no='P-KIT',
                 spare_quotes={'sup:b': dict(price=2, lead_d=1, fail_rate=.01, avl=True)})
    monkeypatch.setattr(decide, 'gather_facts', lambda inputs, asset, known, tsdb: (dict(deepcopy(facts), **known), []))
    monkeypatch.setattr(mcp_ent, 'fetch', lambda path, asset: {'records': [dict(part_no='P-KIT', below_reorder_point=True)]})
    tool = dmn.DmnTools(kg=PKG(), tsdb=object())
    monkeypatch.setattr(tool, '_graph', lambda query, **params: [dict(id='part:kit', name='씰 키트', partNo='P-KIT')])
    return tool


def test_submit_purchase_refusal_keeps_the_process_reason(purchase_tool, monkeypatch):
    reason = '이 사건은 조치 카드 접수 대상이 아닙니다'
    _refuse(monkeypatch, _refused(409, reason))
    out = dmn.enveloped(purchase_tool.submit_purchase)('HYD-03', 'P-KIT', 'INC-C')
    assert out['result'] == 'error' and out['error_kind'] == 'INVALID' and reason in out['message'], out
    monkeypatch.setattr(decide, 'submit', lambda payload: {'id': payload['id']})
    out = dmn.enveloped(purchase_tool.submit_purchase)('HYD-03', 'P-KIT', 'INC-C')
    assert out['result'] == 'ok' and out['document']['status'] == 'SUBMITTED' and out['document']['id'].startswith('DEC-')


# ---------------------------------------------------------------- 3: one unresolved supplier policy card

def _core_skill(sid, policy):
    s = runtime_skill()
    s.update(skillId=sid, sopId=sid, name=sid, supplier_policy=policy, parts=['part:cooler-core'], supplierParts=[],
             # it/neo4j/v2/instances.cypher: 쿨러 코어 SUPPLIED_BY 는 sup:a · sup:b 뿐
             partSuppliers=[dict(part='part:cooler-core', supplier='sup:a'), dict(part='part:cooler-core', supplier='sup:b')])
    s['actions'][0]['value'] = None
    return s


def _core_case():
    quotes = {q['supplier']: {k: q[k] for k in ('price', 'lead_d', 'fail_rate', 'avl', 'name')} for q in data.quote_rows('P-CLR-CORE')}
    skills = {sid: _core_skill(sid, p) for sid, p in (('SOP-PUR-11', 'oem'), ('SOP-PUR-12', 'lowest_approved'), ('SOP-PUR-13', 'fastest_quote'))}
    rules = [R('dec:action-candidates', 'rule:purchase', 'SELECT', [T('pattern', '==', 'SPARE_BELOW_MIN')], list(skills)),
             R('dec:compliance', 'rule:avl', 'EXCLUDE', [T('supplier_avl', '==', False)])]
    facts = dict(pattern='SPARE_BELOW_MIN', purchase_part='part:cooler-core', spare_part_no='P-CLR-CORE',
                 spare_quotes=quotes, need_qty=1, need_by_days=10, spare_gap=-1)
    return quotes, skills, rules, facts


def test_cooler_core_unrelated_fastest_supplier_excludes_only_that_card():
    quotes, skills, rules, facts = _core_case()
    assert min(quotes, key=lambda s: quotes[s]['lead_d']) == 'sup:c'
    result = cards.evaluate(rules, skills, facts, {}, [], [], {}, evaluation_mode='execution')
    by_id = {o['id']: o for o in result['options']}
    assert set(by_id) == {'SOP-PUR-11', 'SOP-PUR-12', 'SOP-PUR-13'}
    fastest = by_id['SOP-PUR-13']
    assert fastest['feasible'] is False and fastest['violations'][0]['rule'] == 'execution:supplier-policy'
    assert 'sup:c' in fastest['violations'][0]['annotation'] and 'SUPPLIED_BY' in fastest['violations'][0]['annotation']
    # never silently another supplier, no invented cost
    assert fastest['resolvedSupplier'] is None and fastest['actions'][0]['value'] is None
    assert 'economicComparison' not in fastest and fastest['score'] is None
    assert fastest['rank'] == 3
    assert by_id['SOP-PUR-11']['resolvedSupplier']['id'] == 'sup:b' and by_id['SOP-PUR-12']['resolvedSupplier']['id'] == 'sup:a'
    assert result['recommended'] in ('SOP-PUR-11', 'SOP-PUR-12')
    assert 'SOP-PUR-13' in result['explanation']


def test_cooler_core_decision_is_submitted_with_the_unresolved_card_excluded(monkeypatch):
    quotes, skills, rules, facts = _core_case()

    class PKG:
        def dmn(self): return deepcopy(rules)
        def inputs(self): return []
        def skills(self, ids): return [deepcopy(s) for s in skills.values()]
        def tradeoffs(self, ids): return []
        def precedents(self, fm): return []
        def suppliers(self): return {}
        def roles(self): return [{'id': 'role:purchasing', 'name': '구매', 'level': 1, 'deptName': '구매'}]

    monkeypatch.setattr(decide, 'gather_facts', lambda inputs, asset, known, tsdb: (dict(deepcopy(facts), **known), []))
    posted = []
    monkeypatch.setattr(decide, 'submit', lambda payload: posted.append(payload) or {'id': payload['id']})
    part = dict(id='part:cooler-core', name='쿨러 코어', partNo='P-CLR-CORE')
    rec = decide.decide(PKG(), decide.DecisionRegistry(), None, 'HYD-01', 'SPARE_BELOW_MIN',
                        dict(id=None, name=None, failureModeId=None, failureMode=None), origin={'kind': 'alert'},
                        do_submit=True, purchase_part=part)
    assert rec['status'] == 'SUBMITTED', rec.get('error')
    assert [o['id'] for o in posted[0]['options']][-1] == 'SOP-PUR-13'
    assert posted[0]['options'][-1]['feasible'] is False and posted[0]['recommended'] != 'SOP-PUR-13'


def test_invalid_supplier_policy_contract_still_fails_the_whole_evaluation():
    _, skills, rules, facts = _core_case()
    skills['SOP-PUR-13']['actions'][0]['value'] = 'sup:a'        # a dynamic policy with a fixed supplier is a model error
    with pytest.raises(ValueError, match='공급사 미확정 PR_CREATE'):
        cards.evaluate(rules, skills, facts, {}, [], [], {}, evaluation_mode='execution')


# ---------------------------------------------------------------- P14: Korean refusal words

def test_forecast_consent_refusals_name_fields_in_korean():
    old = dict(model_id='m', model_revision='r1', scope='s', binding={}, horizon_s=900, parameters={}, actions=[], assumptions=[],
               review_policy={}, source_t='2026-10-23T00:00:00+00:00', inputs=dict(ts1=50, fan_pct=60, cooler_health=.5),
               values=dict(ts1=50, ts1_peak=52, vs1=.6, vs1_peak=.6))
    new = deepcopy(old); new['model_revision'] = 'r2'; new['inputs']['fan_pct'] = 100; new['inputs']['ts1'] = 51
    reasons = forecasting.consent_changes(old, new, time_scale=20)
    assert reasons == ['예측 모델 판본 변경: 새 카드 검토가 필요합니다', '예측 입력 팬 속도 변경: 새 카드 검토가 필요합니다']
    worse = deepcopy(old); worse['values']['vs1_peak'] = 1.0
    assert forecasting.consent_changes(old, worse, time_scale=20) == ['예측 최고 진동 악화 또는 미확인: 새 카드 검토가 필요합니다']
    for key in ('model_id', 'model_revision', 'scope', 'binding', 'horizon_s', 'parameters', 'actions', 'assumptions', 'review_policy'):
        changed = deepcopy(old); changed[key] = 'x'
        text = ' '.join(forecasting.consent_changes(old, changed, time_scale=20))
        assert key not in text, text


def _guardrail_rejects(monkeypatch):
    from agentsvc import guardrail
    posted = []
    monkeypatch.setattr(decide, 'submit', lambda payload: posted.append(payload) or {'id': payload['id']})
    monkeypatch.setattr(guardrail, 'check_cards', lambda result: ['권고 카드 X에 승인 역할이 없다'])
    return posted


def test_guardrail_rejection_is_not_a_registered_purchase(purchase_tool, monkeypatch):
    posted = _guardrail_rejects(monkeypatch)
    out = dmn.enveloped(purchase_tool.submit_purchase)('HYD-03', 'P-KIT', 'INC-C')
    assert out['result'] == 'error' and '가드레일' in out['message'] and '승인 역할이 없다' in out['message'], out
    assert posted == []
    out = dmn.enveloped(purchase_tool.evaluate_purchase)('HYD-03', 'P-KIT')
    assert out['result'] == 'ok' and out['document']['outcome'] == 'guardrail_rejected'


def test_guardrail_rejection_is_not_a_registered_decision(cooler, monkeypatch):
    posted = _guardrail_rejects(monkeypatch)
    out = _submit(cooler)
    assert out['result'] == 'error' and '가드레일' in out['message'] and '승인 역할이 없다' in out['message'], out
    assert posted == []
