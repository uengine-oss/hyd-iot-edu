"""2026-10-23 판단 엔진 검수의 하 항목(.evidence/audit2/agent.md 5 · 7 · 8 · 9)과 수정 보고의 남긴 것(쿨러 코어 → sup:c)을 고친 뒤의 올바른 동작.

5: 판단 id 는 서비스(agent · mcp)와 48비트 난수를 담아 재시작 · 서비스가 달라도 겹치지 않는다. process 가 같은 id 의 옛 판단을
   돌려주면(duplicate) 새 판단은 저장되지 않은 것이므로 등록 거절로 올린다.
7: 예측 동의 허용치의 배율은 process 가 모든 모드에서 내는 /api/definition 의 time_scale(기본 20)이다. 모르면 1배로 두지 않는다.
8: 팬 베어링처럼 두 원문 절차가 같은 공급사 · 같은 수량 · 같은 총비용으로 묶이면 카드마다 같은 발주 카드를 밝힌다.
9: 팬 100 % 연속 운전 시간(HM-8.5 · 8.8 '24시간')은 설비 시간이다 — 20배속이면 실제 72분이 24시간.
쿨러 코어: 그래프 시드의 SUPPLIED_BY 가 ERP 견적(SCM 등록, PR-7.3)과 같아 SOP-PUR-13 이 sup:c 를 골라 AVL 규정으로 지는 대안이 된다.
"""
import json
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentsvc import cards, decide, forecasting
from agentsvc.tools import mcp_tsdb
from entsim import data
from procsvc import scm_sync

from test_cards import R, T, run
from test_purchase_scope_model import runtime_skill

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- 5: decision ids

def test_decision_ids_name_their_service_and_do_not_repeat_across_restarts():
    # every restart starts seq at 1 again and the process decision book survives restarts: 3,000 first ids of fresh
    # registries (a long course of same-day restarts, both services) must all differ. 4 hex digits collided within ~300.
    first = [decide.DecisionRegistry(service).new_id('DEC') for service in ('agent', 'mcp') for _ in range(1500)]
    assert len(set(first)) == len(first)
    agent, mcp = first[0], first[-1]
    assert agent.startswith('DEC-') and '-agent-001-' in agent and '-mcp-001-' in mcp
    assert re.fullmatch(r'DEC-\d{4}-agent-001-[0-9a-f]{12}', agent)
    with pytest.raises(ValueError, match='서비스'):
        decide.DecisionRegistry('other')


def test_the_two_services_mint_ids_with_their_own_name():
    from agentsvc import main
    from dmn_mcp.tools import DmnTools
    assert main.decisions.service == 'agent'
    assert DmnTools(kg=object(), tsdb=object()).registry.service == 'mcp'


class _Reply:
    def __init__(self, body): self.body = json.dumps(body).encode()
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self): return self.body


def test_a_decision_the_process_book_already_had_is_not_a_success(monkeypatch):
    """The process book keeps the first decision under an id; a second POST with the same id (legacy, no process_scope) gets
    the *old* decision back with duplicate=true and the new cards are not stored (procsvc main._store_decision)."""
    from procsvc import main
    book = {}
    monkeypatch.setattr(main, 'book', book)
    monkeypatch.setattr(main, '_audit', lambda *a, **k: None)
    monkeypatch.setattr(main.instance_mode, 'bridge_legacy_agent', lambda d: None)

    def urlopen(req, timeout=None):            # the real process code answers the agent's POST
        return _Reply(main._store_decision(json.loads(req.data)))
    monkeypatch.setattr(decide.urllib.request, 'urlopen', urlopen)
    first = dict(id='DEC-1023-001-ab12', asset='HYD-01', origin={'kind': 'manual'}, options=[{'id': 'skill:fan'}])
    assert decide.submit(first) == {'id': first['id'], 'state': 'PENDING_APPROVAL'}
    other = dict(first, options=[{'id': 'skill:mix'}])                    # another judgment that drew the same id
    with pytest.raises(decide.SubmitRefused, match='새로 저장하지 않았습니다') as refused:
        decide.submit(other)
    assert refused.value.status == 409
    assert book[first['id']]['options'] == [{'id': 'skill:fan'}]            # the book still has the first one only


def test_a_reply_for_another_id_is_not_a_success(monkeypatch):
    monkeypatch.setattr(decide.urllib.request, 'urlopen', lambda req, timeout=None: _Reply({'id': 'DEC-other', 'state': 'PENDING_APPROVAL'}))
    with pytest.raises(decide.SubmitRefused):
        decide.submit({'id': 'DEC-mine', 'options': [{}]})
    monkeypatch.setattr(decide.urllib.request, 'urlopen', lambda req, timeout=None: _Reply({'id': 'DEC-mine', 'state': 'PENDING_APPROVAL'}))
    assert decide.submit({'id': 'DEC-mine', 'options': [{}]})['id'] == 'DEC-mine'


# ---------------------------------------------------------------- 7: the stack's time scale in every process mode

def test_legacy_process_publishes_its_time_scale_and_the_consent_budget_uses_it(monkeypatch):
    from procsvc import main
    published = main.get_definition()['time_scale']                          # legacy endpoint, no instance runtime needed
    assert published == main.TIME_SCALE and published > 1
    monkeypatch.delenv('TIME_SCALE', raising=False)                          # the agent container has no TIME_SCALE (compose.yaml)
    answers = {'/api/process/mode': {'mode': 'legacy', 'time_scale': None},  # legacy: no instance runtime
               '/api/definition': {'time_scale': published}}
    monkeypatch.setattr(decide, '_get_json', lambda url: answers[url[len(decide.PROCESS_URL):]])
    assert forecasting.stack_time_scale() == published
    # A129 budget: 15 wall seconds at 20× are 5 simulated minutes in which TS1 may rise 1.5 ℃ (1.0 ℃/sim-min budget)
    old = dict(model_id='m', model_revision='r', scope='s', binding={}, horizon_s=900, parameters={}, actions=[], assumptions=[],
               review_policy={}, source_t='2026-10-23T00:00:00+00:00', inputs=dict(ts1=56),
               values=dict(ts1=56.0, ts1_peak=57.0, vs1=.6, vs1_peak=.6))
    later = deepcopy(old)
    later['source_t'] = '2026-10-23T00:00:15+00:00'
    later['values'].update(ts1=57.5, ts1_peak=60.0)
    assert forecasting.consent_changes(old, later) == []                      # was refused at 1× (time_scale None → env → 1)


def test_unreadable_time_scale_is_an_error_not_one(monkeypatch):
    monkeypatch.delenv('TIME_SCALE', raising=False)
    monkeypatch.setattr(decide, '_get_json', lambda url: {'time_scale': None})
    with pytest.raises(ValueError, match='배율'):
        forecasting.stack_time_scale()


# ---------------------------------------------------------------- 9: fan 100 % continuous run in plant hours

T0 = datetime(2026, 10, 23, 3, 0, tzinfo=timezone.utc)


class _Cur:
    def __init__(self, row): self.row = row
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, params=None): pass
    def fetchone(self): return self.row


def _db(monkeypatch, wall_minutes):
    db = mcp_tsdb.TimeSeriesDB()
    row = (100.0, T0, T0 - timedelta(minutes=wall_minutes))

    class C:
        def __enter__(s): return s
        def __exit__(s, *a): return False
        def cursor(s): return _Cur(row)
    monkeypatch.setattr(db, '_conn', lambda: C())
    return db


def test_fan_run_is_measured_in_plant_hours(monkeypatch):
    # HM-8.8: 24 h of 100 % fan is the fan's running life — at 20× the plant lives it in 72 wall minutes
    assert _db(monkeypatch, 72).fan100_hours('HYD-01', time_scale=20) == 24.0
    assert _db(monkeypatch, 75).fan100_hours('HYD-01', time_scale=20) == 25.0
    with pytest.raises(ValueError):
        _db(monkeypatch, 75).fan100_hours('HYD-01', time_scale=0)


def test_judgment_reads_the_fan_run_with_the_stack_time_scale_and_the_24h_penalty_follows(monkeypatch):
    monkeypatch.setattr(decide, '_get_json', lambda url: {'time_scale': 20.0})
    db = _db(monkeypatch, 75)
    item = dict(variable='fan100_hours', name='팬 100 % 연속 운전 시간', source='sys:historian', sourceName='Historian', sourceKind='System')
    facts, prov = decide.gather_facts([item], 'HYD-01', {}, db)
    assert facts['fan100_hours'] == 25.0 and prov[0]['time_scale'] == 20.0 and '배율 20' in prov[0]['how']
    # test_cards' rule:fan24 (fan100_hours > 24, PENALTY 20) on the fan cards: 75 wall minutes at 20× cross it
    assert all(o['penalties'][0]['rule'] == 'rule:fan24' for o in run(facts)['options'])
    assert not any(o['penalties'] for o in run({'fan100_hours': _db(monkeypatch, 75).fan100_hours('HYD-01', time_scale=1)})['options'])


def test_unknown_time_scale_leaves_the_fan_run_unknown_with_its_reason(monkeypatch):
    monkeypatch.delenv('TIME_SCALE', raising=False)
    monkeypatch.setattr(decide, '_get_json', lambda url: (_ for _ in ()).throw(OSError('offline')))
    item = dict(variable='fan100_hours', name='팬 100 % 연속 운전 시간', source='sys:historian', sourceName='Historian', sourceKind='System')
    facts, prov = decide.gather_facts([item], 'HYD-01', {}, _db(monkeypatch, 75))
    assert facts['fan100_hours'] is None and '배율' in prov[0]['error']


# ---------------------------------------------------------------- seed SUPPLIED_BY = ERP quotes (cooler core → sup:c)

def _seed_supplied_by():
    text = (ROOT / 'it/neo4j/v2/instances.cypher').read_text(encoding='utf-8')
    block = re.search(r"UNWIND (\[\['part:pump-seal','sup:a'.*?\]\]) AS r\s*MATCH \(p:Part \{id: r\[0\]\}\), \(s:Supplier", text, re.S)
    assert block, 'SUPPLIED_BY seed block not found'
    rows = json.loads(block[1].replace("'", '"'))
    parts = dict(re.findall(r"\['(part:[a-z-]+)','[^']+','(P-[A-Z-]+)','comp:", text))
    return [dict(part=parts[p], partId=p, supplier=s, price=price, failRate=fail, leadDays=lead) for p, s, price, fail, lead in rows]


def test_seed_supplied_by_is_the_erp_quote_set_of_every_seeded_part():
    """PR-7.3: supplier facts follow the SCM registry; process scm_sync makes the graph follow ent — the seed must already be
    what one sync would leave (the graph lacked cooler core → sup:c until the first sync, and always on the memory backend)."""
    seed = _seed_supplied_by()
    erp = [dict(id=q['supplier'], name=q['name'], avl=q['avl'], part_no=part, price=q['price'], fail_rate=q['fail_rate'], lead_d=q['lead_d'])
           for part in ('P-PMP-SEAL', 'P-FAN-BRG', 'P-CLR-CORE') for q in data.quote_rows(part)]
    graph_suppliers = [dict(id=r['id'], name=r['name'], avl=r['avl']) for r in erp]
    plan = scm_sync.plan(erp, graph_suppliers, seed, {r['part'] for r in seed})
    assert plan['set_quotes'] == [] and plan['delete_quotes'] == [] and plan['graph_only'] == [], plan
    assert {(r['part'], r['supplier']) for r in seed} == {(r['part_no'], r['id']) for r in erp}


def _purchase_skills(part_id, part_no):
    seed = _seed_supplied_by()
    out = {}
    for sid, policy in (('SOP-PUR-11', 'oem'), ('SOP-PUR-12', 'lowest_approved'), ('SOP-PUR-13', 'fastest_quote')):
        s = runtime_skill()
        s.update(skillId=sid, sopId=sid, name=sid, supplier_policy=policy, parts=[part_id], supplierParts=[],
                 partSuppliers=[dict(part=r['partId'], supplier=r['supplier']) for r in seed if r['partId'] == part_id])
        s['actions'][0]['value'] = None
        out[sid] = s
    quotes = {q['supplier']: {k: q[k] for k in ('price', 'lead_d', 'fail_rate', 'avl', 'name')} for q in data.quote_rows(part_no)}
    rules = [R('dec:action-candidates', 'rule:purchase', 'SELECT', [T('pattern', '==', 'SPARE_BELOW_MIN')], list(out)),
             R('dec:compliance', 'rule:avl', 'EXCLUDE', [T('supplier_avl', '==', False)])]
    facts = dict(pattern='SPARE_BELOW_MIN', purchase_part=part_id, spare_part_no=part_no, spare_quotes=quotes,
                 need_qty=1, need_by_days=data.SPARE_BASE[part_no]['need_by_days'], spare_gap=-1)
    return out, rules, facts


def test_cooler_core_fastest_quote_is_the_non_avl_losing_alternative_with_its_total_cost():
    skills, rules, facts = _purchase_skills('part:cooler-core', 'P-CLR-CORE')
    result = cards.evaluate(rules, skills, facts, {}, [], [], {}, evaluation_mode='execution')
    by_id = {o['id']: o for o in result['options']}
    fastest = by_id['SOP-PUR-13']
    assert fastest['resolvedSupplier']['id'] == 'sup:c' and fastest['actions'][0]['value'] == 'sup:c'
    assert not fastest['feasible'] and [v['rule'] for v in fastest['violations']] == ['rule:avl']   # PR-7.3, not "no supply"
    assert fastest['economicComparison']['total_cost'] == 120 + 0.20 * 250                           # shown as the losing alternative
    assert not fastest.get('supplierUnresolved')
    assert result['recommended'] in ('SOP-PUR-11', 'SOP-PUR-12')


# ---------------------------------------------------------------- 8: fan bearing — two procedures, one order

def test_fan_bearing_cards_that_are_the_same_order_say_so():
    skills, rules, facts = _purchase_skills('part:fan-bearing', 'P-FAN-BRG')
    result = cards.evaluate(rules, skills, facts, {}, [], [], {}, evaluation_mode='execution')
    by_id = {o['id']: o for o in result['options']}
    low, fast, oem = by_id['SOP-PUR-12'], by_id['SOP-PUR-13'], by_id['SOP-PUR-11']
    assert low['actions'] == fast['actions'] and low['actions'][0]['value'] == 'sup:a'
    assert low['economicComparison']['total_cost'] == fast['economicComparison']['total_cost']
    assert low['sameOrderAs'] == [{'id': 'SOP-PUR-13', 'sopId': 'SOP-PUR-13'}]
    assert fast['sameOrderAs'] == [{'id': 'SOP-PUR-12', 'sopId': 'SOP-PUR-12'}]
    assert 'sameOrderAs' not in oem                                             # sup:b is a different order
    # total cost (PR-7.4): sup:a 18 + 0.10 × 250 = 43 > sup:b 28 + 0.03 × 250 = 35.5 — OEM first, then the two same orders
    assert result['recommended'] == 'SOP-PUR-11' and [o['id'] for o in result['options']] == ['SOP-PUR-11', 'SOP-PUR-12', 'SOP-PUR-13']
    assert 'SOP-PUR-12 · SOP-PUR-13은 같은 공급사(sup:a)' in result['explanation']
    assert '총비용 차이가 아니라' in result['explanation']


def test_cards_with_different_orders_have_no_same_order_mark():
    skills, rules, facts = _purchase_skills('part:pump-seal', 'P-PMP-SEAL')
    result = cards.evaluate(rules, skills, facts, {}, [], [], {}, evaluation_mode='execution')
    assert all('sameOrderAs' not in o for o in result['options'])
    assert len({o['actions'][0]['value'] for o in result['options']}) == 3
