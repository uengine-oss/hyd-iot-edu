"""A4 (U6) — 판단 채점: 정답표는 화면 · API 로 적는 데이터(내장 정답 0, 처음엔 빈 상태)이고, 정답과 다르게 판단하면 점수가 떨어지며,
두 실행의 전후 비교(점수 · 지식 그래프 변화)가 계산된다. 이 파일의 정답표는 시험용 가짜 정답표다 — 제품 코드에는 없다."""
import io
import re
import urllib.error
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import eval_api, judgment_eval as je

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------- 시험용 가짜 정답표 (화면에서 적었다고 치는 값)
FAKE_GOLDEN = [
    {'id': 'cooler-auto', 'title': '쿨러 핀 오염 · 원격 자동', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION',
     'facts': {'plc_mode': 'REMOTE_AUTO', 'plc_state': 'RUN', 'fan100_hours': 0},
     'expected': {'cause': 'cause:cooler-fin-fouling', 'failure_mode': 'fm:cooling-loss'},
     'allowed_top': ['skill:fan-max-derate', 'skill:derate-night-clean'],
     'forbidden': [{'skill': 'skill:fan-max', 'expect': 'not_recommended', 'rule': 'rule:ts1-warn'}],
     'required_evidence': ['evd:ce-low', 'rule:cand-cooler', 'HM-7.3']},
    {'id': 'pump-standby-ready', 'title': '펌프 씰 마모 · 예비 가용', 'asset': 'HYD-02', 'pattern': 'PUMP_LEAKAGE',
     'facts': {'plc_mode': 'REMOTE_AUTO', 'plc_state': 'RUN', 'standby_ready': True},
     'expected': {'cause': 'cause:pump-seal-wear', 'failure_mode': 'fm:volumetric-loss'},
     'allowed_top': ['skill:switch-standby-pump'],
     'forbidden': [{'skill': 'skill:raise-pressure', 'expect': 'excluded', 'rule': 'rule:no-pressure-raise'}],
     'required_evidence': ['evd:ps1-low', 'rule:no-pressure-raise', 'HM-5.4']},
    {'id': 'pump-standby-busy', 'title': '펌프 씰 마모 · 예비 정비 중', 'asset': 'HYD-02', 'pattern': 'PUMP_LEAKAGE',
     'facts': {'plc_mode': 'REMOTE_AUTO', 'plc_state': 'RUN', 'standby_ready': False},
     'expected': {'cause': 'cause:pump-seal-wear', 'failure_mode': 'fm:volumetric-loss'},
     'allowed_top': ['skill:derate-70', 'skill:wo-pump-seal'],
     'forbidden': [{'skill': 'skill:switch-standby-pump', 'expect': 'excluded', 'rule': 'rule:standby'},
                   {'skill': 'skill:raise-pressure', 'expect': 'excluded', 'rule': 'rule:no-pressure-raise'}],
     'required_evidence': ['evd:ps1-low', 'rule:standby', 'rule:no-pressure-raise', 'HM-5.2']},
    {'id': 'fan-local', 'title': '팬 베어링 마모 · 현장 제어', 'asset': 'HYD-03', 'pattern': 'FAN_VIBRATION',
     'facts': {'plc_mode': 'LOCAL', 'plc_state': 'RUN'},
     'expected': {'cause': 'cause:fan-bearing-wear', 'failure_mode': 'fm:bearing-degradation'},
     'allowed_top': ['skill:wo-fan-bearing'],
     'forbidden': [{'skill': 'skill:fan-slow-derate', 'expect': 'excluded', 'rule': 'rule:auto-mode'},
                   {'skill': 'skill:fan-slow', 'expect': 'excluded', 'rule': 'rule:auto-mode'},
                   {'skill': 'skill:planned-stop', 'expect': 'excluded', 'rule': 'rule:auto-mode'}],
     'required_evidence': ['evd:vs1-trend', 'rule:cand-fan']},
]
ITEMS = {it['id']: je.validate_item(it) for it in FAKE_GOLDEN}
COOLER, PUMP_BUSY, FAN_LOCAL = ITEMS['cooler-auto'], ITEMS['pump-standby-busy'], ITEMS['fan-local']


def option(sid, rank, feasible=True, violations=(), selected=('rule:cand-cooler',), sources=('HM-7.3',)):
    return {'id': sid, 'sopId': 'SOP-X', 'rank': rank, 'feasible': feasible, 'score': 3.0 - rank,
            'violations': [{'rule': r, 'sources': ['HM-3.2']} for r in violations],
            'selectedBy': [{'rule': r, 'sources': list(sources)} for r in selected], 'penalties': [], 'warnings': [], 'steps': []}


def cooler_decision(recommended='skill:fan-max-derate', cause='cause:cooler-fin-fouling', fm='fm:cooling-loss', ce_passed=True, status='EVALUATED', plc_mode='REMOTE_AUTO'):
    """agent /api/agent/decide 응답 모양."""
    return {'id': 'DEC-1', 'status': status, 'asset': 'HYD-01', 'origin': {'kind': 'manual'},
            'facts': {'cause': cause, 'failure_mode': fm, 'plc_mode': plc_mode},
            'causes': [{'id': cause, 'name': '쿨러 핀 오염', 'score': 0.6, 'failureModeId': fm,
                        'evidence': [{'id': 'evd:ce-low', 'passed': ce_passed}, {'id': 'evd:fan-normal', 'passed': True}]},
                       {'id': 'cause:high-ambient', 'score': 0.0, 'evidence': [{'id': 'evd:ambient-high', 'passed': False}]}],
            'result': {'recommended': recommended, 'rankRule': {'rule': 'rule:rank-value', 'sources': ['ks:strategy-map']},
                       'options': [option('skill:fan-max-derate', 1), option('skill:derate-night-clean', 2), option('skill:fan-max', 3), option('skill:wo-cooler-clean', 4)],
                       'trace': [{'rule': 'rule:cand-cooler', 'fired': True}]}}


# ---------------------------------------------------------------- 내장 정답 0
def test_no_built_in_answer_key_in_product_code():
    assert not (ROOT / 'it/process/procsvc/judgment_golden.json').exists()
    ids = re.compile(r"['\"](?:cause|fm|skill|evd|rule):[a-z]")
    for rel in ('it/process/procsvc/judgment_eval.py', 'it/process/procsvc/eval_api.py', 'it/portal/www/evaluation.js', 'scripts/evaluate_judgment.py'):
        text = (ROOT / rel).read_text(encoding='utf-8')
        assert not ids.search(text), f'{rel} 에 온톨로지 id 가 박혀 있다(정답은 데이터로만)'
    sql = (ROOT / 'it/supabase/migrations/20261008000030_judgment_eval_runs.sql').read_text(encoding='utf-8').lower()
    assert 'insert into' not in sql, '정답표 시드 금지'


def test_fake_golden_used_by_these_tests_cites_repository_ontology_names():
    """시험 정답표가 저장소에 없는 이름이면 시험이 실제 판단 모양과 어긋난다 — 가짜여도 이름은 진짜로."""
    text = '\n'.join(p.read_text(encoding='utf-8') for p in (ROOT / 'it/neo4j/v2').glob('*.cypher'))
    missing = sorted(i for i in {i for it in ITEMS.values() for i in je.referenced_ids(it)} if i not in text)
    assert not missing, missing


@pytest.mark.parametrize('break_it, word', [
    (lambda d: d.update(id='Bad Id'), 'id'),
    (lambda d: d.update(title=' '), 'title'),
    (lambda d: d.update(expected={'cause': 'x', 'failure_mode': 'fm:a'}), 'expected'),
    (lambda d: d.update(allowed_top=[]), 'allowed_top'),
    (lambda d: d['forbidden'].append({'skill': 'skill:fan-max-derate', 'expect': 'excluded'}), 'allowed_top 에도'),
    (lambda d: d['forbidden'].append({'skill': 'skill:z', 'expect': 'banned'}), 'forbidden'),
    (lambda d: d['forbidden'].append({'skill': 'skill:fan-max', 'expect': 'excluded'}), '두 번'),
    (lambda d: d.update(required_evidence=[]), 'required_evidence'),
    (lambda d: d.update(facts=[1]), 'facts'),
])
def test_broken_item_is_refused_with_the_field_name(break_it, word):
    doc = deepcopy(FAKE_GOLDEN[0])
    break_it(doc)
    with pytest.raises(ValueError) as caught:
        je.validate_item(doc)
    assert word in str(caught.value)


def test_item_hash_tracks_only_scored_fields():
    a = je.validate_item(FAKE_GOLDEN[0])
    assert je.item_hash(a) == je.item_hash(dict(a, title='다른 제목', note='메모'))
    assert je.item_hash(a) != je.item_hash(dict(a, allowed_top=['skill:fan-max-derate']))


# ---------------------------------------------------------------- 채점: 일부러 틀리면 점수가 떨어진다
def test_correct_judgement_scores_100_and_each_deviation_lowers_it():
    full = je.score_judgement(COOLER, je.normalize_decision(cooler_decision()))
    assert full['score'] == 100 and all(c['ok'] for c in full['checks'].values()) and full['facts_mismatch'] == []
    wrong_cause = je.score_judgement(COOLER, je.normalize_decision(cooler_decision(cause='cause:high-ambient')))
    assert wrong_cause['score'] == 70 and not wrong_cause['checks']['cause']['ok'] and wrong_cause['checks']['cause']['want'] == 'cause:cooler-fin-fouling'
    wrong_top = je.score_judgement(COOLER, je.normalize_decision(cooler_decision(recommended='skill:wo-cooler-clean')))
    assert wrong_top['score'] == 70 and not wrong_top['checks']['top']['ok']
    forbidden_top = je.score_judgement(COOLER, je.normalize_decision(cooler_decision(recommended='skill:fan-max')))
    assert forbidden_top['score'] == 50 and not forbidden_top['checks']['forbidden']['ok'] and forbidden_top['checks']['forbidden']['detail'][0]['got'] == '1위 추천됨'
    no_evidence = je.score_judgement(COOLER, je.normalize_decision(cooler_decision(ce_passed=False)))
    assert no_evidence['score'] < 100 and 'evd:ce-low' in no_evidence['checks']['evidence']['missing']


def test_changing_the_answer_key_changes_the_score_of_the_same_judgement():
    """같은 판단이라도 정답표를 바꾸면 점수가 바뀐다 — 점수는 코드가 아니라 정답표(데이터)에서 나온다."""
    judged = je.normalize_decision(cooler_decision())
    strict = je.validate_item(dict(FAKE_GOLDEN[0], allowed_top=['skill:derate-night-clean']))
    assert je.score_judgement(COOLER, judged)['score'] == 100 and je.score_judgement(strict, judged)['score'] == 70


def test_withheld_or_failed_judgement_scores_zero_not_partial():
    for judged in (je.withheld('근거 조회가 불완전하여 보류'), je.withheld('에이전트 오류', status='ERROR'),
                   je.normalize_decision(cooler_decision(status='REJECTED_BY_GUARDRAIL'))):
        r = je.score_judgement(COOLER, judged)
        assert r['score'] == 0 and not any(c['ok'] for c in r['checks'].values())


def test_facts_used_that_differ_from_the_answer_key_assumption_are_reported():
    r = je.score_judgement(COOLER, je.normalize_decision(cooler_decision(plc_mode='REMOTE_MANUAL')))
    assert r['facts_mismatch'] == [{'key': 'plc_mode', 'want': 'REMOTE_AUTO', 'got': 'REMOTE_MANUAL'}]


def test_forbidden_must_be_excluded_by_rule_not_merely_ranked_low():
    d = {'id': 'DEC-2', 'status': 'EVALUATED', 'facts': {'cause': 'cause:fan-bearing-wear', 'failure_mode': 'fm:bearing-degradation'},
         'causes': [{'id': 'cause:fan-bearing-wear', 'failureModeId': 'fm:bearing-degradation', 'evidence': [{'id': 'evd:vs1-trend', 'passed': True}]}],
         'result': {'recommended': 'skill:wo-fan-bearing', 'options': [
             option('skill:wo-fan-bearing', 1, selected=('rule:cand-fan',), sources=('HM-8.1',)),
             option('skill:planned-stop', 2, selected=('rule:cand-fan',), sources=('HM-8.1',)),
             option('skill:fan-slow-derate', 3, feasible=False, violations=('rule:auto-mode',)),
             option('skill:fan-slow', 4, feasible=False, violations=('rule:auto-mode',))]}}
    r = je.score_judgement(FAN_LOCAL, je.normalize_decision(d))
    detail = {x['skill']: x for x in r['checks']['forbidden']['detail']}
    assert detail['skill:fan-slow-derate']['ok'] and detail['skill:fan-slow']['ok'] and not detail['skill:planned-stop']['ok']
    assert detail['skill:planned-stop']['got'] == '실행 가능 · 2위' and r['checks']['forbidden']['ratio'] == pytest.approx(2 / 3, abs=0.001)
    assert r['score'] == pytest.approx(100 - 20 / 3, abs=0.1)
    fixed = deepcopy(d)
    fixed['result']['options'][1].update(feasible=False, violations=[{'rule': 'rule:auto-mode', 'sources': ['HM-3.2']}])
    assert je.score_judgement(FAN_LOCAL, je.normalize_decision(fixed))['score'] == 100


def test_pump_busy_accepts_either_allowed_top_and_requires_both_exclusions():
    def pump(rec, standby_feasible):
        return {'id': 'DEC-3', 'status': 'EVALUATED', 'facts': {'cause': 'cause:pump-seal-wear', 'failure_mode': 'fm:volumetric-loss'},
                'causes': [{'id': 'cause:pump-seal-wear', 'failureModeId': 'fm:volumetric-loss', 'evidence': [{'id': 'evd:ps1-low', 'passed': True}]}],
                'result': {'recommended': rec, 'options': [
                    option('skill:derate-70', 1, selected=('rule:cand-pump',), sources=('HM-5.2',)),
                    option('skill:wo-pump-seal', 2, selected=('rule:cand-pump',), sources=('HM-5.2',)),
                    option('skill:switch-standby-pump', 3, feasible=standby_feasible, violations=() if standby_feasible else ('rule:standby',)),
                    option('skill:raise-pressure', 4, feasible=False, violations=('rule:no-pressure-raise',))]}}
    for rec in ('skill:derate-70', 'skill:wo-pump-seal'):
        assert je.score_judgement(PUMP_BUSY, je.normalize_decision(pump(rec, False)))['score'] == 100
    leaky = je.score_judgement(PUMP_BUSY, je.normalize_decision(pump('skill:derate-70', True)))
    assert leaky['score'] == 85 and 'rule:standby' in leaky['checks']['evidence']['missing'] and not leaky['checks']['forbidden']['ok']


def test_evaluate_run_record_is_normalized_from_card_and_evaluation():
    d = cooler_decision()
    run = {'id': 'RUN-0007', 'status': 'EVALUATED', 'card': {'causes': d['causes'], 'citations': ['HM-7.3', 'rule:cand-cooler']},
           'evaluation': {'id': 'DEC-7', 'recommended': 'skill:fan-max-derate', 'options': d['result']['options'], 'rankRule': d['result']['rankRule'],
                          'facts': {'plc_mode': 'REMOTE_AUTO'}}}
    j = je.normalize_evaluation(run)
    assert j['status'] == 'EVALUATED' and j['run_id'] == 'RUN-0007' and je.score_judgement(COOLER, j)['score'] == 100
    for bad, status in (({'status': 'WITHHELD', 'error': '근거 부족'}, 'WITHHELD'), ({'status': 'REJECTED_BY_GUARDRAIL', 'error': '인용 누락'}, 'REJECTED_BY_GUARDRAIL'),
                        ({'status': 'FAILED', 'error': 'boom'}, 'ERROR')):
        w = je.normalize_evaluation(bad)
        assert w['status'] == status and je.score_judgement(COOLER, w)['score'] == 0 and bad['error'] in w['reason']


# ---------------------------------------------------------------- 반복 · 흔들림 · 결정론
def test_aggregate_reports_stability_and_identical_runs():
    runs = [je.normalize_decision(cooler_decision()), je.normalize_decision(cooler_decision()), je.normalize_decision(cooler_decision(recommended='skill:fan-max'))]
    agg = je.aggregate(COOLER, runs, deterministic=True)
    assert agg['repeats'] == 3 and agg['stability'] == pytest.approx(2 / 3, abs=0.001) and agg['identical'] is False
    assert agg['score'] == pytest.approx((100 + 100 + 50) / 3, abs=0.1) and agg['min'] == 50 and agg['max'] == 100
    assert agg['modal_outcome'] == 'cause:cooler-fin-fouling → skill:fan-max-derate' and len(agg['outcomes']) == 2
    same = je.aggregate(COOLER, [je.normalize_decision(cooler_decision())] * 3, deterministic=True)
    assert same['identical'] is True and same['stability'] == 1 and same['score'] == 100
    with pytest.raises(ValueError):
        je.aggregate(COOLER, [])


# ---------------------------------------------------------------- 전후 비교 · 지식 상태
def _snap(rels, nodes):
    return je.knowledge_state([{'nodes': len(nodes), 'rels': len(rels)}], [dict(zip('atb', r.split('|'))) for r in rels],
                              [{'id': k, 'labels': ['X'], 'props': {'v': v}} for k, v in nodes.items()])


def _run(results, knowledge=None, by='강사'):
    return je.new_run(path='decide', by=by, repeats=1, knowledge=knowledge or {'fingerprint': 'A'}, results=results)


def test_compare_two_runs_shows_item_deltas_and_what_changed_in_the_graph():
    k_before = _snap(['cause:cooler-fin-fouling|EVIDENCED_BY|evd:ce-low', 'skill:fan-max|ADDRESSES|fm:cooling-loss'], {'evd:ce-low': 1, 'rule:ts1-warn': 1})
    k_after = _snap(['skill:fan-max|ADDRESSES|fm:cooling-loss'], {'evd:ce-low': 1, 'rule:ts1-warn': 2})
    before = _run([je.aggregate(COOLER, [je.normalize_decision(cooler_decision())]), je.aggregate(PUMP_BUSY, [je.withheld('보류')])], k_before)
    after = _run([je.aggregate(COOLER, [je.normalize_decision(cooler_decision(recommended='skill:fan-max', ce_passed=False))]),
                  je.aggregate(PUMP_BUSY, [je.withheld('보류')]), je.aggregate(FAN_LOCAL, [je.withheld('보류')])], k_after)
    cmp = je.compare(before, after)
    rows = {r['item']: r for r in cmp['rows']}
    c = rows['cooler-auto']
    assert c['before'] == 100 and c['verdict'] == 'regressed' and c['delta'] < 0 and c['evidence_lost'] == ['evd:ce-low']
    assert [x['check'] for x in c['changed']] == ['top', 'forbidden', 'evidence'] and c['golden_changed'] is False
    assert rows['pump-standby-busy']['verdict'] == 'same' and cmp['only_after'] == ['fan-local'] and cmp['only_before'] == []
    assert cmp['regressed'] == 1 and cmp['improved'] == 0 and cmp['same'] == 1
    assert cmp['delta'] == pytest.approx((c['after'] + 0) / 2 - (100 + 0) / 2, abs=0.1)
    kd = cmp['knowledge']
    assert cmp['knowledge_changed'] is True and kd['removed_rels'] == [{'from': 'cause:cooler-fin-fouling', 'type': 'EVIDENCED_BY', 'to': 'evd:ce-low'}]
    assert kd['added_rels'] == [] and kd['changed_nodes'] == ['rule:ts1-warn'] and kd['counts']['removed_rels'] == 1
    assert 'snapshot' not in cmp['before']['knowledge']
    back = je.compare(after, before)
    assert back['rows'][0]['verdict'] == 'improved' and back['knowledge']['added_rels'][0]['type'] == 'EVIDENCED_BY'


def test_compare_flags_items_whose_answer_key_changed_between_runs():
    a = _run([je.aggregate(COOLER, [je.normalize_decision(cooler_decision())])])
    strict = je.validate_item(dict(FAKE_GOLDEN[0], allowed_top=['skill:derate-night-clean']))
    b = _run([je.aggregate(strict, [je.normalize_decision(cooler_decision())])])
    cmp = je.compare(a, b)
    assert cmp['golden_changed'] == ['cooler-auto'] and cmp['rows'][0]['delta'] == -30 and cmp['knowledge_changed'] is False


def test_identical_graph_has_identical_fingerprint_and_no_invented_change_time():
    s1 = _snap(['a|R|b'], {'a': 1, 'b': 1})
    s2 = _snap(['a|R|b'], {'b': 1, 'a': 1})
    assert s1['fingerprint'] == s2['fingerprint'] and s1['last_change'] is None and '기록' in s1['last_change_note']
    assert je.knowledge_diff(s1, s2)['changed'] is False
    s3 = je.knowledge_state([{'nodes': 1, 'rels': 0, 'manual_at': '2026-10-08T01:00:00+00:00', 'edit_at': '2026-10-08T02:00:00+00:00'}])
    assert s3['last_change'] == '2026-10-08T02:00:00+00:00' and s3['fingerprint'] is None
    assert je.knowledge_diff(s1, s3)['comparable'] is False
    with pytest.raises(ValueError):
        je.knowledge_state([])


def test_run_record_requires_an_author_and_summarizes():
    rec = _run([je.aggregate(COOLER, [je.normalize_decision(cooler_decision())])])
    assert rec['id'].startswith('EVAL-') and rec['summary'] == {'items': 1, 'score': 100, 'perfect': 1, 'withheld': 0, 'unstable': 0,
                                                                  'cause_hits': 1, 'top_ok': 1, 'forbidden_ok': 1, 'evidence_ok': 1}
    with pytest.raises(ValueError):
        _run([je.aggregate(COOLER, [je.withheld('x')])], by='  ')
    with pytest.raises(ValueError):
        je.new_run(path='llm', by='a', repeats=1, knowledge={}, results=[])


# ---------------------------------------------------------------- 실제 워커 경로
def _pump_instance(pid='anomaly.1', standby=False, did='DEC-9'):
    inst = {'proc_inst_id': pid, 'proc_inst_name': 'HYD-02 펌프', 'status': 'COMPLETED', 'start_date': '2026-10-08T00:00:00Z',
            'variables_data': [{'key': 'asset', 'value': 'HYD-02'}, {'key': 'pattern', 'value': 'PUMP_LEAKAGE'}, {'key': 'cause', 'value': 'cause:pump-seal-wear'},
                               {'key': 'failure_mode', 'value': 'fm:volumetric-loss'}, {'key': 'decision_id', 'value': did}, {'key': 'chosen_skill', 'value': 'skill:derate-70'},
                               {'key': 'guide_card', 'value': {'citations': ['cause:pump-seal-wear', 'evd:ps1-low'],
                                                               'causes': [{'id': 'cause:pump-seal-wear', 'evidence': [{'id': 'evd:ps1-low', 'passed': True}]}]}}]}
    decision = {'id': did, 'asset': 'HYD-02', 'origin': {'kind': 'alert', 'pattern': 'PUMP_LEAKAGE', 'incident': 'INC-1'},
                'facts': {'plc_mode': 'REMOTE_AUTO', 'plc_state': 'RUN', 'standby_ready': standby, 'order_due_h': 6},
                'recommended': 'skill:derate-70', 'options': [
                    option('skill:derate-70', 1, selected=('rule:cand-pump',), sources=('HM-5.2',)),
                    option('skill:switch-standby-pump', 2, feasible=False, violations=('rule:standby',)),
                    option('skill:raise-pressure', 3, feasible=False, violations=('rule:no-pressure-raise',))]}
    return inst, decision


def test_worker_instance_is_matched_and_scored_from_the_real_worker_output():
    inst, decision = _pump_instance()
    cand = je.instance_candidate(inst, {'DEC-9': decision}.get)
    assert cand['facts'] == {'plc_mode': 'REMOTE_AUTO', 'plc_state': 'RUN', 'standby_ready': False} and cand['decision_found']
    golden = list(ITEMS.values())
    assert je.match_item(golden, cand)['id'] == 'pump-standby-busy'
    judged = je.worker_judgement(cand, decision)                 # guide_card 는 워커 task 출력(변수)에서 온다
    assert judged['status'] == 'EVALUATED' and je.score_judgement(PUMP_BUSY, judged)['score'] == 100
    assert je.score_judgement(PUMP_BUSY, je.worker_judgement(cand, None))['score'] == 0
    assert je.instance_candidate({'proc_inst_id': 'x', 'variables_data': []}, {}.get) is None
    with pytest.raises(ValueError, match='2개'):
        je.match_item(golden, dict(cand, facts={}))
    with pytest.raises(ValueError, match='없습니다'):
        je.match_item(golden, dict(cand, asset='HYD-09'))
    with pytest.raises(ValueError, match='없습니다'):
        je.match_item([], cand)                                  # 빈 정답표 — 채점할 기준이 없다


# ---------------------------------------------------------------- HTTP
KNOWN_IDS = {i for it in ITEMS.values() for i in je.referenced_ids(it)}


class FakeTx:
    def __init__(self, g):
        self.g = g

    def run(self, q, **params):
        if q == je.KNOWLEDGE_Q:
            rows = [{'nodes': len(self.g['nodes']), 'rels': len(self.g['rels'])}]
        elif q == je.KNOWLEDGE_RELS_Q:
            rows = [dict(zip('atb', r.split('|'))) for r in self.g['rels']]
        elif q == je.KNOWLEDGE_NODES_Q:
            rows = [{'id': k, 'labels': ['X'], 'props': {'v': v}} for k, v in self.g['nodes'].items()]
        elif 'UNWIND $ids' in q:
            rows = [{'missing': [i for i in params['ids'] if i not in self.g['known']]}]
        else:
            raise AssertionError(q)
        return [type('R', (), {'data': (lambda self, row=row: row)})() for row in rows]


class FakeDriver:
    def __init__(self, g):
        self.g = g

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def session(self):
        return self

    def execute_read(self, fn):
        if self.g.get('down'):
            raise OSError('neo4j down')
        return fn(FakeTx(self.g))


@pytest.fixture
def client():
    app = FastAPI()
    calls = []
    state = {'recommended': 'skill:fan-max-derate'}
    graph = {'rels': ['cause:cooler-fin-fouling|EVIDENCED_BY|evd:ce-low'], 'nodes': {'evd:ce-low': 1}, 'known': set(KNOWN_IDS)}

    def decide(item):
        calls.append(('decide', item['id']))
        if item['pattern'] != 'COOLER_DEGRADATION':
            return je.withheld('판단 보류 (409): 근거 조회가 불완전하여 원인 순위와 조치를 보류합니다.')
        return je.normalize_decision(cooler_decision(recommended=state['recommended']))

    def evaluate(item):
        calls.append(('evaluate', item['id']))
        return je.normalize_decision(cooler_decision(recommended=state['recommended'], plc_mode='REMOTE_MANUAL'))
    audits = []
    eval_api.register(app, driver_factory=lambda: FakeDriver(graph), store_factory=je.MemoryEvalStore, agent_url='http://agent', book={}, incidents={},
                      runtime_factory=lambda: None, audit=lambda *a: audits.append(a), decide_fn=decide, evaluate_fn=evaluate)
    c = TestClient(app)
    c.calls, c.state, c.audits, c.graph = calls, state, audits, graph
    return c


def put_items(client, *ids):
    for i in ids:
        r = client.post('/api/eval/golden/items', json={'item': next(x for x in FAKE_GOLDEN if x['id'] == i), 'by': '강사'})
        assert r.status_code == 201, r.text


def test_answer_key_starts_empty_and_scoring_an_empty_key_is_refused(client):
    g = client.get('/api/eval/golden').json()
    assert g['items'] == [] and g['storage'] == 'memory' and '비어' in g['empty_note'] and set(g['paths']) == {'decide', 'evaluate', 'worker'}
    r = client.post('/api/eval/runs', json={'path': 'decide', 'by': '강사'})
    assert r.status_code == 400 and '비어' in r.json()['detail'] and client.calls == []


def test_answer_key_crud_with_graph_name_check(client):
    put_items(client, 'cooler-auto')
    assert client.post('/api/eval/golden/items', json={'item': FAKE_GOLDEN[0], 'by': '강사'}).status_code == 409
    typo = dict(FAKE_GOLDEN[1], id='pump-typo', required_evidence=['evd:ps1-lw'])
    r = client.post('/api/eval/golden/items', json={'item': typo, 'by': '강사'})
    assert r.status_code == 400 and 'evd:ps1-lw' in r.json()['detail']
    edited = dict(FAKE_GOLDEN[0], allowed_top=['skill:derate-night-clean'])
    r = client.put('/api/eval/golden/items/cooler-auto', json={'item': edited, 'by': '강사'})
    assert r.status_code == 200 and r.json()['allowed_top'] == ['skill:derate-night-clean'] and r.json()['updated_by'] == '강사'
    assert client.put('/api/eval/golden/items/other', json={'item': edited, 'by': '강사'}).status_code == 400
    assert client.put('/api/eval/golden/items/nope', json={'item': dict(edited, id='nope'), 'by': '강사'}).status_code == 404
    assert client.post('/api/eval/golden/items', json={'item': FAKE_GOLDEN[1], 'by': ' '}).status_code == 400
    assert client.delete('/api/eval/golden/items/cooler-auto').status_code == 400               # 누가 지웠는지 필요
    assert client.delete('/api/eval/golden/items/cooler-auto', params={'by': '강사'}).status_code == 200
    assert client.get('/api/eval/golden').json()['items'] == []
    assert [a[2] for a in client.audits] == ['JUDGMENT_GOLDEN_SAVED', 'JUDGMENT_GOLDEN_SAVED', 'JUDGMENT_GOLDEN_DELETED']
    client.graph['down'] = True
    assert client.post('/api/eval/golden/items', json={'item': FAKE_GOLDEN[1], 'by': '강사'}).status_code == 503


def test_http_run_list_get_and_compare_before_after_a_knowledge_change(client):
    put_items(client, 'cooler-auto', 'pump-standby-ready')
    r1 = client.post('/api/eval/runs', json={'path': 'decide', 'by': '강사', 'repeats': 2, 'note': '고치기 전'})
    assert r1.status_code == 201, r1.text
    run1 = r1.json()
    assert run1['summary']['items'] == 2 and run1['repeats'] == 2 and client.calls.count(('decide', 'cooler-auto')) == 2
    assert run1['knowledge']['fingerprint'] and 'snapshot' not in run1['knowledge']
    by_item = {i['item']: i for i in run1['items']}
    assert by_item['cooler-auto']['score'] == 100 and by_item['cooler-auto']['identical'] is True and by_item['cooler-auto']['deterministic'] is True
    assert by_item['pump-standby-ready']['score'] == 0 and by_item['pump-standby-ready']['status'] == 'WITHHELD' and '보류' in by_item['pump-standby-ready']['reason']
    # 지식을 잘못 고친 뒤(E5): 관계 하나를 끊었고, 판단이 금지 조치를 1위로 올렸다
    client.graph['rels'] = []
    client.state['recommended'] = 'skill:fan-max'
    run2 = client.post('/api/eval/runs', json={'path': 'decide', 'by': '강사', 'items': ['cooler-auto', 'pump-standby-ready']}).json()
    assert run2['summary']['score'] == 25
    listed = client.get('/api/eval/runs').json()
    assert [r['id'] for r in listed] == [run2['id'], run1['id']] and 'items' not in listed[0] and 'snapshot' not in listed[0]['knowledge']
    assert client.get('/api/eval/runs/' + run1['id']).json()['items'][0]['item'] == 'cooler-auto'
    cmp = client.get('/api/eval/compare', params={'before': run1['id'], 'after': run2['id']}).json()
    assert cmp['regressed'] == 1 and cmp['same'] == 1 and cmp['delta'] == -25 and cmp['rows'][0]['changed'][0]['check'] == 'top'
    assert cmp['knowledge_changed'] is True and cmp['knowledge']['removed_rels'][0]['to'] == 'evd:ce-low'
    assert client.get('/api/eval/compare', params={'before': run1['id'], 'after': 'EVAL-nope'}).status_code == 404
    assert client.get('/api/eval/runs/EVAL-nope').status_code == 404
    assert client.audits[-1][2] == 'JUDGMENT_EVALUATED'


def test_http_evaluate_path_uses_the_agent_pipeline_and_reports_fact_mismatch(client):
    put_items(client, 'cooler-auto')
    run = client.post('/api/eval/runs', json={'path': 'evaluate', 'by': '강사'}).json()
    item = run['items'][0]
    assert client.calls == [('evaluate', 'cooler-auto')] and item['deterministic'] is False and run['path'] == 'evaluate'
    assert item['facts_mismatch'] == [{'key': 'plc_mode', 'want': 'REMOTE_AUTO', 'got': 'REMOTE_MANUAL'}]


def test_http_rejects_bad_requests_without_running(client):
    put_items(client, 'cooler-auto')
    assert client.post('/api/eval/runs', json={'path': 'decide', 'by': ' '}).status_code == 400
    assert client.post('/api/eval/runs', json={'path': 'llm', 'by': 'a'}).status_code == 400
    assert client.post('/api/eval/runs', json={'path': 'decide', 'by': 'a', 'items': ['no-such-item']}).status_code == 404
    assert client.post('/api/eval/runs', json={'path': 'decide', 'by': 'a', 'repeats': 99}).status_code == 422
    assert client.post('/api/eval/runs', json={'path': 'worker', 'by': 'a', 'instances': [{'instance': 'x'}]}).status_code == 400   # instance 모드 아님
    assert client.get('/api/eval/worker-candidates').status_code == 400
    client.graph['down'] = True
    assert client.post('/api/eval/runs', json={'path': 'decide', 'by': 'a'}).status_code == 503       # 지식 상태 없이 저장하지 않는다
    assert client.calls == [] and client.get('/api/eval/runs').json() == []


def test_http_worker_path_groups_instances_of_the_same_item_as_repeats():
    app = FastAPI()
    i1, d1 = _pump_instance('anomaly.1', did='DEC-1')
    i2, d2 = _pump_instance('anomaly.2', did='DEC-2')
    d2 = dict(d2, recommended='skill:switch-standby-pump')        # 두 번째 워커 판단은 금지 조치를 1위로 — 흔들림
    book = {'DEC-1': d1, 'DEC-2': d2}

    class Repo:
        def list_instances(self, limit, tenant_id):
            return [i1, i2, {'proc_inst_id': 'empty', 'variables_data': []}]

        def get_instance(self, pid):
            return {'anomaly.1': i1, 'anomaly.2': i2}.get(pid)
    rt = type('RT', (), {'repo': Repo(), 'tenant_id': 'hyd'})()
    store = je.MemoryEvalStore()
    graph = {'rels': [], 'nodes': {}, 'known': set(KNOWN_IDS)}
    eval_api.register(app, driver_factory=lambda: FakeDriver(graph), store_factory=lambda: store, agent_url='http://agent', book=book, incidents={},
                      runtime_factory=lambda: rt, audit=lambda *a: None, decide_fn=lambda i: 1 / 0, evaluate_fn=lambda i: 1 / 0)
    c = TestClient(app)
    cands = c.get('/api/eval/worker-candidates').json()
    assert [x['instance'] for x in cands] == ['anomaly.1', 'anomaly.2'] and cands[0]['item'] is None and '정답표' in cands[0]['match_note']
    for it in FAKE_GOLDEN[1:3]:
        assert c.post('/api/eval/golden/items', json={'item': it, 'by': '강사'}).status_code == 201
    assert c.get('/api/eval/worker-candidates').json()[0]['item'] == 'pump-standby-busy'
    run = c.post('/api/eval/runs', json={'path': 'worker', 'by': '강사', 'instances': [{'instance': 'anomaly.1'}, {'instance': 'anomaly.2'}]}).json()
    assert run['summary']['items'] == 1 and run['repeats'] == 2
    r = run['items'][0]
    assert r['item'] == 'pump-standby-busy' and r['repeats'] == 2 and r['stability'] == 0.5 and r['min'] < r['max'] == 100
    assert [x['instance'] for x in r['instances']] == ['anomaly.1', 'anomaly.2']
    assert c.post('/api/eval/runs', json={'path': 'worker', 'by': '강사', 'instances': [{'instance': 'nope'}]}).status_code == 404
    assert c.post('/api/eval/runs', json={'path': 'worker', 'by': '강사', 'instances': [{'instance': 'anomaly.1', 'item': 'nope'}]}).status_code == 404


def test_http_agent_connection_failure_is_503_not_a_zero_score():
    app = FastAPI()

    def decide(item):
        raise ConnectionError('에이전트 서비스에 연결할 수 없습니다: refused')
    store = je.MemoryEvalStore()
    store.golden_put(ITEMS['cooler-auto'], '강사', create=True)
    eval_api.register(app, driver_factory=lambda: FakeDriver({'rels': [], 'nodes': {}, 'known': set()}), store_factory=lambda: store, agent_url='http://agent',
                      book={}, incidents={}, runtime_factory=lambda: None, audit=lambda *a: None, decide_fn=decide)
    c = TestClient(app)
    r = c.post('/api/eval/runs', json={'path': 'decide', 'by': '강사'})
    assert r.status_code == 503 and c.get('/api/eval/runs').json() == []


def _raise_http(code, body):
    def _open(req, timeout):
        raise urllib.error.HTTPError(req.full_url, code, 'x', {}, io.BytesIO(body))
    return _open


def test_http_decide_and_evaluate_map_agent_statuses(monkeypatch):
    decide, evaluate = eval_api.http_decide('http://agent'), eval_api.http_evaluate('http://agent')
    item = {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'facts': {}}
    monkeypatch.setattr(eval_api.urllib.request, 'urlopen', _raise_http(409, '{"detail": {"reason": "근거 보류"}}'.encode()))
    j = decide(item)
    assert j['status'] == 'WITHHELD' and '근거 보류' in j['reason']
    monkeypatch.setattr(eval_api.urllib.request, 'urlopen', _raise_http(500, b'boom'))
    assert decide(item)['status'] == 'ERROR' and evaluate(item)['status'] == 'ERROR'
    monkeypatch.setattr(eval_api.urllib.request, 'urlopen', _raise_http(503, b'{"detail": "knowledge graph not connected yet"}'))
    with pytest.raises(ConnectionError):
        decide(item)
    monkeypatch.setattr(eval_api.urllib.request, 'urlopen', lambda req, timeout: (_ for _ in ()).throw(urllib.error.URLError('refused')))
    with pytest.raises(ConnectionError):
        evaluate(item)
    sent = {}

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def capture(req, timeout):
        import json
        sent.update(json.loads(req.data))
        return Resp(json.dumps({'id': 'RUN-1', 'status': 'WITHHELD', 'error': '데이터 신뢰 불가'}).encode())
    monkeypatch.setattr(eval_api.urllib.request, 'urlopen', capture)
    j = evaluate(item)
    assert sent['alert']['alertId'].startswith('EVAL-') and sent['alert']['state'] == 'RAISE' and j['status'] == 'WITHHELD'


def test_migration_defines_answer_key_and_immutable_run_tables():
    sql = (ROOT / 'it/supabase/migrations/20261008000030_judgment_eval_runs.sql').read_text(encoding='utf-8').lower()
    for col in ('judgment_golden_items', 'item_hash', 'judgment_eval_runs', 'created_by', 'knowledge', "path in ('decide', 'evaluate', 'worker')",
                'grant select, insert on public.judgment_eval_runs'):
        assert col in sql


def test_cli_offline_score_matches_the_portal_scoring_function(tmp_path, capsys):
    """랩업 L18: 내 채점기(CLI score)와 포털 점수가 같은 순수 함수에서 나온다 — 틀린 판단은 CLI 에서도 같은 만큼 떨어진다."""
    import importlib.util
    import json
    spec = importlib.util.spec_from_file_location('evaluate_judgment', ROOT / 'scripts/evaluate_judgment.py')
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    (tmp_path / 'item.json').write_text(json.dumps(FAKE_GOLDEN[0], ensure_ascii=False), encoding='utf-8')
    for rec, want in (('skill:fan-max-derate', 100), ('skill:fan-max', 50)):
        (tmp_path / 'judged.json').write_text(json.dumps(cooler_decision(recommended=rec), ensure_ascii=False), encoding='utf-8')
        assert cli.main(['--json', 'score', str(tmp_path / 'item.json'), str(tmp_path / 'judged.json')]) == 0
        out = json.loads(capsys.readouterr().out)
        assert out['score'] == want == je.score_judgement(COOLER, je.normalize_decision(cooler_decision(recommended=rec)))['score']
