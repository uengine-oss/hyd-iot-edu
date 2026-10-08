"""A8 (U11) KPI 실적 · 역추적: 알려진 기록으로 손계산과 일치, 원천 없는 지표는 계산 불가 사유, 원천을 일부러 깨뜨리면 0이 아니라 사유.

지표 · 목표 · 영향 관계는 시드 온톨로지(it/neo4j/v2/instances.cypher)를 그대로 읽어 가짜 그래프를 만든다 — 손으로 고친 지표표가 아니다.
기간: now = 2026-10-08 12:00Z, '24h' → [10-07 12:00Z, 10-08 12:00Z). 배속 20.
"""
import ast
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from procsvc import kpi

ROOT = Path(__file__).resolve().parents[1]
CYPHER = (ROOT / 'it' / 'neo4j' / 'v2' / 'instances.cypher').read_text(encoding='utf-8')
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


def T(text):
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


def unwind(marker):
    """marker 줄 다음의 첫 `UNWIND [ … ] AS r` 리터럴을 파이썬 값으로."""
    lines = CYPHER.splitlines()
    i = next(n for n, l in enumerate(lines) if marker in l)
    i = next(n for n in range(i, len(lines)) if lines[n].lstrip().startswith('UNWIND ['))
    body = []
    for l in lines[i:]:
        body.append(re.sub(r'//[^\n]*$', '', l))
        if '] AS r' in l:
            break
    text = '\n'.join(body).strip()[len('UNWIND '):]
    text = text[:text.rindex(' AS r')]
    return ast.literal_eval(text.replace('null', 'None').replace('true', 'True').replace('false', 'False'))


PERSP = {r[0]: r for r in unwind('1. 가치 계층 (BSC)')}
OBJ = {r[0]: r for r in unwind("MERGE (n:Perspective {id: r[0]})")}
ORG = {r[0]: r[1] for r in unwind("MERGE (a)-[:SUPPORTS]->(b);")}
SUPPORTS = unwind("MERGE (n:Objective {id: r[0]})")
MEASURES = unwind('// BSC 성과 지표: [')
INFL = unwind('// 상충 관계 (성과 지표 → 성과 지표)') + unwind('// 물리 영향 (상태 변수 → 상태 변수 → Measure)')
SV = {r[0]: r for r in unwind('// [state variable id, name')}
AFFECTS = unwind('// 스킬이 움직이는 것 (스킬 → 상태 변수 · Measure)')
SKILL_NAMES = {r[0]: r[1] for r in unwind('// [id, name, sopId, kind, description, approver, executor')}
# 이상 패턴 → (TESTS → InputData → REPRESENTS) 상태 변수: instances.cypher 의 TESTS · InputData 표에서 옮김
PATTERNS = [('pattern:cooler-degradation', 'COOLER_DEGRADATION', '쿨러 성능 저하', ['sv:ts1', 'sv:ce']),
            ('pattern:pump-leakage', 'PUMP_LEAKAGE', '펌프 누설', ['sv:ps1', 'sv:fs1', 'sv:load']),
            ('pattern:fan-vibration', 'FAN_VIBRATION', '팬 진동', ['sv:vs1'])]
CAUSES = [('cause:cooler-fin-fouling', '쿨러 핀 오염', 'sv:fouling'), ('cause:pump-seal-wear', '펌프 축 씰 마모', 'sv:leak'),
          ('cause:fan-bearing-wear', '팬 베어링 마모', 'sv:bearing-wear')]


def measure_rows():
    rows = []
    for mid, name, _al, unit, direction, obj, owner, formula, target, freq, role in MEASURES:
        p = OBJ[obj][2]
        rows.append(dict(id=mid, name=name, unit=unit, direction=direction, target=target, formula=formula, frequency=freq,
                         kpiRole=role, warn=5 if mid == 'msr:safety-margin' else None, crit=0 if mid == 'msr:safety-margin' else None,
                         objective=obj, objectiveName=OBJ[obj][1], objectiveDescription=OBJ[obj][3], perspective=p,
                         perspectiveName=PERSP[p][1], perspectiveOrder=PERSP[p][2], owner=ORG.get(owner)))
    return rows


def node(i):
    if i.startswith('msr:'):
        return {'id': i, 'name': next(m[1] for m in MEASURES if m[0] == i), 'kind': 'measure'}
    return {'id': i, 'name': SV[i][1], 'kind': 'state'}


def paths_to(target, depth=4):
    edges = [(a, b, s, st) for a, b, s, st, *_ in INFL if a[:3] in ('msr', 'sv:') and b[:3] in ('msr', 'sv:')]
    out, frontier = [], [[target]]
    for _ in range(depth):
        nxt = []
        for p in frontier:
            for a, b, s, st in edges:
                if b == p[0] and a not in p:
                    q = [a] + p
                    nxt.append(q)
                    rels = [next({'sign': e[2], 'strength': e[3], 'condition': None, 'note': None} for e in edges if e[0] == x and e[1] == y)
                            for x, y in zip(q, q[1:])]
                    out.append({'nodes': [node(n) for n in q], 'rels': rels})
        frontier = nxt
    return out


class Fake:
    """원천 셋을 이름으로 흉내 낸다. broken: 실패시킬 (원천) 또는 (원천, 이름)."""

    def __init__(self, ts=None, biz=None, broken=()):
        self.data = {'ts': ts or {}, 'biz': biz or {}}
        self.broken = set(broken)
        self.calls = []

    def _get(self, kind, name, params):
        self.calls.append((kind, name, params))
        if kind in self.broken or (kind, name) in self.broken:
            raise RuntimeError('connection refused')
        v = self.data[kind].get(name, [])
        return v(params) if callable(v) else v

    def ts(self, name, sql, params):
        return self._get('ts', name, params)

    def biz(self, name, sql, params):
        return self._get('biz', name, params)

    def graph(self, name, cypher, params):
        if 'graph' in self.broken:
            raise kpi.SourceError('지식 그래프 조회 실패 (measures): ServiceUnavailable')
        if name == 'measures':
            return measure_rows()
        if name == 'supports':
            return [{'source': a, 'target': b} for a, b in SUPPORTS]
        if name == 'limit':
            assert params['id'] == 'msr:safety-margin'
            return [{'id': 'sv:ts1', 'name': SV['sv:ts1'][1], 'limit': SV['sv:ts1'][6], 'unit': SV['sv:ts1'][3], 'tag': 'TS1'}]
        if name.startswith('paths:'):
            return paths_to(params['id'])
        if name.startswith('patterns:'):
            return [{'id': i, 'code': c, 'name': n, 'via': [v for v in via if v in params['ids']]}
                    for i, c, n, via in PATTERNS if set(via) & set(params['ids'])]
        if name == 'skill_names':
            return [{'id': k, 'name': SKILL_NAMES[k]} for k in params['ids'] if k in SKILL_NAMES]
        if name == 'pattern_names':
            return [{'code': c, 'name': n} for _i, c, n, _v in PATTERNS] + [{'code': 'OVERHEAT_TRIP', 'name': '과열 정지'}]
        if name.startswith('causes:'):
            return [{'id': i, 'name': n, 'via': [v]} for i, n, v in CAUSES if v in params['ids']]
        if name.startswith('skills:'):
            return [{'id': s, 'name': SKILL_NAMES.get(s, s), 'sopId': None, 'target': t, 'sign': sign, 'note': note}
                    for s, t, sign, _d, _u, note in AFFECTS if t in params['ids']]
        if name.startswith('objectives:'):
            o = next(m for m in measure_rows() if m['id'] == params['id'])['objective']
            return [{'id': o, 'name': OBJ[o][1], 'supports': [{'id': b, 'name': OBJ[b][1], 'perspective': PERSP[OBJ[b][2]][1]}
                                                              for a, b in SUPPORTS if a == o]}]
        raise AssertionError(name)


def var(**kw):
    return [{'key': k, 'name': k, 'value': v} for k, v in kw.items()]


# ---------------------------------------------------------------- 알려진 기록 (손계산 기준)
TS = {
    'tag_minutes': [{'asset': 'HYD-01', 'minutes': 1440}, {'asset': 'HYD-02', 'minutes': 1440}, {'asset': 'HYD-03', 'minutes': 720}],
    'trips': [
        {'alert_id': 'ALT-HYD01-TRIP-001', 'asset': 'HYD-01', 'pattern': 'OVERHEAT_TRIP', 'raised_at': T('2026-10-08T02:00:00'), 'cleared_at': T('2026-10-08T02:30:00')},
        {'alert_id': 'ALT-HYD01-TRIP-000', 'asset': 'HYD-01', 'pattern': 'LOW_PRESSURE_TRIP', 'raised_at': T('2026-10-07T11:50:00'), 'cleared_at': T('2026-10-07T12:10:00')},
        {'alert_id': 'ALT-HYD03-TRIP-001', 'asset': 'HYD-03', 'pattern': 'HIGH_VIBRATION_TRIP', 'raised_at': T('2026-10-08T07:00:00'), 'cleared_at': None},
    ],
    'tag_peak:TS1': [{'asset': 'HYD-01', 'at': T('2026-10-08T02:01:00'), 'peak': 66.2, 'n': 1440},
                     {'asset': 'HYD-02', 'at': T('2026-10-08T05:00:00'), 'peak': 52.0, 'n': 1440},
                     {'asset': 'HYD-03', 'at': T('2026-10-08T06:00:00'), 'peak': 49.5, 'n': 720}],
    'tag_avg:EPS1': [{'asset': 'HYD-01', 'mean': 2.9, 'n': 1440}, {'asset': 'HYD-02', 'mean': 3.0, 'n': 1440}, {'asset': 'HYD-03', 'mean': 2.5, 'n': 720}],
}
BIZ = {
    'energy_rate': [{'site': '창원 1공장', 'energy_rate': 0.015}],
    'work_orders': [
        {'id': 'WO-1', 'asset': 'HYD-01', 'task': 'SOP-COOL-04 쿨러 핀 세척 → 작업지시 SOP-COOL-04', 'option_id': 'skill:wo-cooler-clean',
         'decision_id': 'D1', 'created_at': T('2026-10-08T03:00:00'), 'clean_cost': 40},
        {'id': 'WO-2', 'asset': 'HYD-02', 'task': 'SOP-PMP-04 펌프 축 씰 교체 → 작업지시 SOP-PMP-04', 'option_id': 'skill:wo-pump-seal',
         'decision_id': 'D2', 'created_at': T('2026-10-08T05:30:00'), 'clean_cost': 40}],
    'purchases': [
        {'id': 'PR-1', 'part': '펌프 축 씰 교체', 'supplier': 'sup:b', 'supplier_name': 'B-OEM (순정)', 'asset': 'HYD-02', 'decision_id': 'D2',
         'created_at': T('2026-10-08T05:30:00'), 'price': 260, 'quality_score': 0.97, 'quote_part': '쿨러 코어'},
        {'id': 'PR-2', 'part': '쿨러 코어', 'supplier': 'sup:a', 'supplier_name': 'A정밀 (저가)', 'asset': 'HYD-01', 'decision_id': 'D3',
         'created_at': T('2026-10-08T06:00:00'), 'price': 180, 'quality_score': 0.78, 'quote_part': '쿨러 코어'}],
    'inventory': [{'asset': 'HYD-01', 'fg_item': 'FG-AUTO-7', 'fg_stock': 900}, {'asset': 'HYD-02', 'fg_item': 'FG-IND-3', 'fg_stock': 100},
                  {'asset': 'HYD-03', 'fg_item': 'FG-AUTO-9', 'fg_stock': 200}],
    'instances': [
        {'proc_inst_id': 'anomaly_response.i1', 'proc_def_id': 'anomaly_response', 'status': 'COMPLETED', 'start_date': datetime(2026, 10, 8, 2, 0, 5),
         'end_date': datetime(2026, 10, 8, 2, 40), 'end_event': 'ev:closed',
         'variables_data': var(asset='HYD-01', alert_id='ALT-HYD01-TRIP-001', pattern='OVERHEAT_TRIP', chosen_skill='skill:reset-after-cool')},
        {'proc_inst_id': 'anomaly_response.i2', 'proc_def_id': 'anomaly_response', 'status': 'COMPLETED', 'start_date': datetime(2026, 10, 8, 1, 40),
         'end_date': datetime(2026, 10, 8, 2, 20), 'end_event': 'ev:closed',
         'variables_data': var(asset='HYD-01', alert_id='ALT-HYD01-COOL-1', pattern='COOLER_DEGRADATION', cause='cause:cooler-fin-fouling',
                               chosen_skill='skill:fan-max')},
        {'proc_inst_id': 'anomaly_response.i3', 'proc_def_id': 'anomaly_response', 'status': 'RUNNING', 'start_date': datetime(2026, 10, 8, 5, 0),
         'end_date': None, 'end_event': None, 'variables_data': var(asset='HYD-02', alert_id='ALT-HYD02-PUMP-1', pattern='PUMP_LEAKAGE')},
        {'proc_inst_id': 'anomaly_response.i4', 'proc_def_id': 'anomaly_response', 'status': 'COMPLETED', 'start_date': datetime(2026, 10, 8, 6, 50),
         'end_date': datetime(2026, 10, 8, 7, 30), 'end_event': 'ev:closed',
         'variables_data': var(asset='HYD-03', alert_id='ALT-HYD03-FAN-1', pattern='FAN_VIBRATION', chosen_skill='skill:planned-stop')},
    ],
}


def flat(rep):
    return {m['id']: m for p in rep['perspectives'] for o in p['objectives'] for m in o['measures']}


def run(ts=TS, biz=BIZ, broken=(), period='24h'):
    return kpi.report(Fake(ts, biz, broken), period, now=NOW, time_scale=20, tenant='hyd')


# ---------------------------------------------------------------- 계산 정의 표
def test_every_seed_measure_has_a_definition_or_a_reason():
    ids = {m[0] for m in MEASURES}
    assert len(ids) == 21
    defs = kpi.definitions(Fake())
    assert {d['id'] for d in defs} == ids
    for d in defs:
        x = d['definition']
        if x['kind'] == 'calc':
            assert x['formula'] and x['sources'] and all(s['table'] and s['columns'] for s in x['sources'])
        elif x['kind'] == 'formula':
            assert x['terms']
        else:
            assert x['kind'] == 'unavailable' and re.search('[가-힣]', x['reason']), d
    calc = {d['id'] for d in defs if d['definition']['kind'] == 'calc'}
    assert calc == {'msr:availability', 'msr:mtbf', 'msr:safety-margin', 'msr:energy-use', 'msr:energy-cost', 'msr:maint-cost',
                    'msr:part-cost', 'msr:part-price', 'msr:part-quality', 'msr:inventory', 'msr:precedent'}
    assert {d['id'] for d in defs if d['definition']['kind'] == 'formula'} == {'msr:op-profit', 'msr:cost'}


def test_formula_string_from_the_graph_is_parsed_kpi_prefix_means_the_same_measure():
    assert kpi.formula_terms('msr:revenue - kpi:cost') == [(1, 'msr:revenue'), (-1, 'msr:cost')]
    assert [t for _, t in kpi.formula_terms('msr:maint-cost + kpi:energy-cost + kpi:penalty')] == ['msr:maint-cost', 'msr:energy-cost', 'msr:penalty']
    with pytest.raises(ValueError):
        kpi.formula_terms('msr:revenue * 2')


# ---------------------------------------------------------------- 손계산과 일치
def test_report_matches_hand_calculation():
    rep = run()
    m = flat(rep)
    assert rep['window']['label'] == '최근 24시간' and rep['window']['start'].startswith('2026-10-07T12:00')
    # 가동률: 트립 HYD-01 30분 + 기간 앞에서 잘린 10분, HYD-03 07:00~12:00 300분 (해제 기록 없음)
    #   (1400 + 1440 + 420) / (1440 + 1440 + 720) = 3260 / 3600 = 90.56 %, 목표 95 → 미달, 달성률 90.56/95 = 95.3 %
    a = m['msr:availability']
    assert (a['value'], a['status'], a['rate']) == (90.56, 'missed', 95.3)
    assert a['perAsset'] == {'HYD-01': 97.22, 'HYD-02': 100.0, 'HYD-03': 58.33}
    assert a['perAssetMet'] == {'HYD-01': True, 'HYD-02': True, 'HYD-03': False}
    assert {(r['table'], r['rows']) for r in a['rows']} == {('tag_1m', 3600), ('alerts', 3)}
    # MTBF: 운전 (1400 + 1440 + 420) / 60 × 20 = 1086.67 h, 기간 안에 시작한 트립 2건 → 543.3 h, 목표 2000 → 미달
    b = m['msr:mtbf']
    assert (b['value'], b['status']) == (543.3, 'missed')
    assert b['perAsset'] == {'HYD-01': 466.7, 'HYD-02': None, 'HYD-03': 140.0}
    # 인터록 여유: 65 − 66.2 = −1.2 (최솟값), 목표 10 → 미달, 달성률 0
    c = m['msr:safety-margin']
    assert (c['value'], c['status'], c['rate']) == (-1.2, 'missed', 0.0)
    assert c['perAsset'] == {'HYD-01': -1.2, 'HYD-02': 13.0, 'HYD-03': 15.5}
    # 전력: (2.9 + 3.0 + 2.5) × 24 = 201.6 kWh/일, 에너지비 201.6 × 30 × 0.015 = 90.72 만원/월 (목표 없음)
    assert (m['msr:energy-use']['value'], m['msr:energy-use']['status']) == (201.6, 'no_target')
    assert m['msr:energy-cost']['value'] == 90.72
    assert m['msr:inventory']['value'] == 1200
    # 선례: 고른 조치가 있는 처리 건 i1 · i2 · i4
    assert (m['msr:precedent']['value'], m['msr:precedent']['perAsset']) == (3, {'HYD-01': 2, 'HYD-03': 1})
    assert rep['summary']['missed'] == 3 and rep['summary']['total'] == 21


def test_bsc_grouping_and_leading_lagging():
    rep = run()
    assert [p['name'] for p in rep['perspectives']] == ['재무', '고객', '내부 프로세스', '학습과 성장']
    internal = next(p for p in rep['perspectives'] if p['name'] == '내부 프로세스')
    avail = next(o for o in internal['objectives'] if o['id'] == 'obj:availability')
    assert {s['name'] for s in avail['supports']} == {'납기 신뢰'}
    assert all(x['kpiRole'] == 'leading' for x in avail['measures'])
    # 목표 안에서는 후행(결과) 지표가 먼저, 선행(동인) 지표가 뒤 — 원가 절감에는 둘 다 있다
    cost = next(o for o in rep['perspectives'][0]['objectives'] if o['id'] == 'obj:cost')
    roles = [x['kpiRole'] for x in cost['measures']]
    assert roles == sorted(roles, key=lambda r: r != 'lagging') and {'lagging', 'leading'} == set(roles)


def test_partial_costs_are_not_passed_off_as_complete():
    m = flat(run())
    mc = m['msr:maint-cost']
    assert (mc['value'], mc['status'], mc['rate']) == (40.0, 'partial', None)
    assert '2건 중 1건' in mc['reason'] and '펌프 축 씰 교체' in mc['reason']
    pc = m['msr:part-cost']
    assert (pc['value'], pc['status']) == (180.0, 'partial') and '펌프 축 씰 교체(B-OEM (순정))' in pc['reason']
    assert (m['msr:part-price']['value'], m['msr:part-quality']['value']) == (180.0, 0.78)
    # 세척 작업지시만 있으면 완전한 실적
    only = dict(BIZ, work_orders=BIZ['work_orders'][:1])
    assert (flat(run(biz=only))['msr:maint-cost']['value'], flat(run(biz=only))['msr:maint-cost']['status']) == (40.0, 'no_target')


def test_measures_without_a_source_say_why_and_composites_name_the_missing_terms():
    m = flat(run())
    for mid in ('msr:revenue', 'msr:otd', 'msr:penalty', 'msr:quality-claim', 'msr:brand', 'msr:throughput', 'msr:oil-life', 'msr:inventory-cost'):
        assert m[mid]['status'] == 'unavailable' and m[mid]['value'] is None and m[mid]['reason'], mid
    assert 'production_orders' in m['msr:otd']['reason']
    cost = m['msr:cost']
    assert cost['status'] == 'unavailable'
    assert all(x in cost['reason'] for x in ('보전비(부분 실적)', '재고 보관비(계산 불가)', '지체상금(계산 불가)'))
    assert '매출(계산 불가)' in m['msr:op-profit']['reason'] and '총비용(계산 불가)' in m['msr:op-profit']['reason']
    assert m['msr:op-profit']['reason'].startswith('식(매출 − 총비용)의 구성 지표를 계산할 수 없습니다')
    assert sorted(d['고른 조치'] for d in m['msr:precedent']['detail']) == sorted(
        SKILL_NAMES[k] for k in ('skill:fan-max', 'skill:planned-stop', 'skill:reset-after-cool'))


def test_composite_is_computed_from_its_terms_when_they_all_exist(monkeypatch):
    monkeypatch.setitem(kpi.DEFINITIONS, 'msr:inventory-cost', dict(kpi.DEFINITIONS['msr:inventory'], fn=lambda f, w, c: kpi.Calc(10.0)))
    monkeypatch.setitem(kpi.DEFINITIONS, 'msr:penalty', dict(kpi.DEFINITIONS['msr:inventory'], fn=lambda f, w, c: kpi.Calc(0.0)))
    m = flat(run(biz=dict(BIZ, work_orders=BIZ['work_orders'][:1], purchases=BIZ['purchases'][1:])))
    # 40 (보전) + 90.72 (에너지) + 180 (부품) + 10 + 0 = 320.72
    assert (m['msr:cost']['value'], m['msr:cost']['status']) == (320.72, 'no_target')
    assert [(d['sign'], d['measure']) for d in m['msr:cost']['detail']][0] == (1, 'msr:maint-cost')


# ---------------------------------------------------------------- 일부러 깨뜨리기
def test_broken_timeseries_gives_a_reason_not_zero_and_other_sources_still_count():
    m = flat(run(broken={'ts'}))
    for mid in ('msr:availability', 'msr:mtbf', 'msr:safety-margin', 'msr:energy-use', 'msr:energy-cost'):
        assert m[mid]['status'] == 'error' and m[mid]['value'] is None, mid
        assert m[mid]['reason'].startswith('시계열 DB 조회 실패') and 'connection refused' in m[mid]['reason']
    assert m['msr:inventory']['value'] == 1200 and m['msr:precedent']['value'] == 3


def test_broken_process_records_only_fail_the_measure_that_reads_them():
    m = flat(run(broken={('biz', 'instances')}))
    assert m['msr:precedent']['status'] == 'error' and m['msr:precedent']['value'] is None
    assert m['msr:inventory']['status'] == 'no_target'


def test_graph_down_is_a_readable_failure_of_the_whole_report():
    with pytest.raises(kpi.SourceError, match='지표 목록 · 목표값은 지식 그래프에 있습니다'):
        run(broken={'graph'})


def test_empty_records_are_no_data_with_reason_not_a_fake_number():
    m = flat(run(ts={}, biz={}))
    assert m['msr:availability']['status'] == 'no_data' and 'tag_1m' in m['msr:availability']['reason']
    assert m['msr:inventory']['status'] == 'no_data'
    assert m['msr:part-price']['status'] == 'no_data' and m['msr:part-price']['reason'] == '기간 안 구매요청이 없습니다'
    # 기록은 있는데 고장이 없으면 MTBF 를 나눌 수 없다 — 운전 시간을 사유에 적는다
    calm = dict(TS, trips=[])
    b = flat(run(ts=calm))['msr:mtbf']
    assert b['status'] == 'no_data' and '1200 h' in b['reason']
    assert flat(run(ts=calm))['msr:availability']['value'] == 100.0


def test_period_filters_reach_every_source():
    fake = Fake(TS, BIZ)
    kpi.report(fake, '1h', now=NOW)
    ts_params = [p for k, n, p in fake.calls if k == 'ts']
    assert ts_params and all(p['t0'] == T('2026-10-08T11:00:00') and p['t1'] == NOW for p in ts_params)
    inst = next(p for k, n, p in fake.calls if n == 'instances')
    assert inst['t0'] == datetime(2026, 10, 8, 11, 0) and inst['t0'].tzinfo is None and inst['tenant'] == 'hyd'
    with pytest.raises(ValueError, match='기간은'):
        kpi.window('2d', NOW)
    w = kpi.window(now=NOW, start='2026-10-08T00:00:00Z', end='2026-10-08T06:00:00Z')
    assert (w.period, w.start, w.end) == ('custom', T('2026-10-08T00:00:00'), T('2026-10-08T06:00:00'))
    with pytest.raises(ValueError, match='늦어야'):
        kpi.window(now=NOW, start='2026-10-08T06:00:00Z', end='2026-10-08T00:00:00Z')
    assert kpi.window('all', NOW).view()['start'] is None


def test_achievement_directions():
    assert kpi.achievement(98, 98, 'UP') == (True, 100.0)
    assert kpi.achievement(-3, 10, 'UP') == (False, 0.0)
    assert kpi.achievement(0, 0, 'DOWN') == (True, 100.0)
    assert kpi.achievement(2, 0, 'DOWN') == (False, 0.0)
    assert kpi.achievement(50, 40, 'DOWN') == (False, 80.0)
    assert kpi.achievement(5, None, 'UP') == (None, None)


# ---------------------------------------------------------------- 역추적
def test_trace_of_missed_availability_finds_cause_work_action_and_equipment():
    tr = kpi.trace(Fake(TS, BIZ), 'msr:availability', '24h', now=NOW, time_scale=20)
    assert tr['measure']['status'] == 'missed'
    ids = [i['id'] for i in tr['instances']]
    # 지표를 많이 깎은 기록 먼저: i4 (HYD-03 트립 300분 동안 열림) → i1 (HYD-01 트립 30분의 경보 당사자)
    # → i2 (같은 30분 동안 열림 + 쿨러 패턴 + 핀 오염 원인) → i3 (펌프 누설 패턴이 토출 압력 → 가동률 경로만)
    assert ids == ['anomaly_response.i4', 'anomaly_response.i1', 'anomaly_response.i2', 'anomaly_response.i3']
    i4 = tr['instances'][0]
    assert i4['link'] == '#/instances/anomaly_response.i4'
    assert any('계획 정지 + 베어링 교체' in r and '나쁜 경로: 설비 가동률' in r and '좋은 경로: 팬 베어링 마모도 → 팬 진동 → 설비 가동률' in r
               for r in i4['reasons'])
    i1 = next(i for i in tr['instances'] if i['id'] == 'anomaly_response.i1')
    assert i1['reasons'][0].startswith('이 처리 건의 경보가 지표를 깎은 기록: HYD-01 보호 정지 30.0분')
    # 냉각 후 리셋은 가동률을 올리는 조치; 계획 정지는 당장 멈추지만(나쁨) 베어링 교체로 진동을 낮춤(좋음);
    # 팬 최대는 유온 → 인터록 여유로는 좋고 팬 진동으로는 나쁨 — 둘 다 경로를 보여 준다
    sk = {s['id']: s for s in tr['skills']}
    assert (sk['skill:planned-stop']['effect'], sk['skill:reset-after-cool']['effect'], sk['skill:fan-max']['effect']) == (0, 1, 0)
    assert sk['skill:fan-max']['harm'] == ['팬 속도 → 팬 진동 → 설비 가동률']
    assert [a['asset'] for a in tr['assets']] == ['HYD-03', 'HYD-01', 'HYD-02'] and tr['assets'][0]['met'] is False
    assert tr['actions'][0]['name'] in ('계획 정지 + 베어링 교체', '냉각 후 리셋', '팬 최대')
    drivers = {d['id']: d for d in tr['drivers']}
    assert drivers['sv:vs1']['effect'] == -1 and drivers['msr:mtbf']['effect'] == 1 and drivers['sv:fan-speed']['effect'] == 0
    assert {p['effect'] for p in drivers['sv:fan-speed']['paths']} == {-1, 1}
    assert drivers['sv:ts1']['path'] == '유온 → 인터록 여유 → 설비 가동률'
    assert tr['objectives'][0]['name'] == '설비 가용성 확보' and tr['objectives'][0]['supports'][0]['name'] == '납기 신뢰'


def test_trace_of_safety_margin_points_at_the_peak_and_unknown_measure_is_keyerror():
    tr = kpi.trace(Fake(TS, BIZ), 'msr:safety-margin', '24h', now=NOW)
    first = tr['instances'][0]
    assert first['asset'] == 'HYD-01' and any('최고 TS1 66.2' in r for r in first['reasons'])
    with pytest.raises(KeyError):
        kpi.trace(Fake(TS, BIZ), 'msr:nope', '24h', now=NOW)


# ---------------------------------------------------------------- HTTP (process 서비스에 붙은 모양)
def test_routes_are_read_only_and_map_failures(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    state = {'broken': ()}

    class Src(Fake):
        def __init__(self, *a, **k):
            super().__init__(TS, BIZ, state['broken'])

        def close(self):
            pass

    monkeypatch.setattr(kpi, 'PgSources', Src)
    app = FastAPI()
    kpi.register(app, ts_dsn='x', biz_dsn='y', driver_factory=None, time_scale=20, tenant='hyd')
    methods = {(r.path, m) for r in app.routes if r.path.startswith('/api/kpi') for m in r.methods}
    assert methods == {('/api/kpi', 'GET'), ('/api/kpi/definitions', 'GET'), ('/api/kpi/trace', 'GET'),
                       ('/api/kpi/try', 'POST'), ('/api/kpi/try/trace', 'POST')}   # B5 목표 바꿔 보기: 시험 계산(쓰기 없음)
    c = TestClient(app)
    assert c.get('/api/kpi?period=7d').json()['summary']['total'] == 21
    assert c.get('/api/kpi?period=2d').status_code == 400
    assert c.get('/api/kpi/trace?measure=msr:nope').status_code == 404
    assert c.get('/api/kpi/trace?measure=msr:availability').json()['instanceTotal'] == 4
    state['broken'] = {'graph'}
    r = c.get('/api/kpi')
    assert r.status_code == 503 and '지식 그래프' in r.json()['detail']


def test_process_service_mounts_the_kpi_routes():
    from procsvc import main
    paths = {r.path for r in main.app.routes}
    assert {'/api/kpi', '/api/kpi/definitions', '/api/kpi/trace'} <= paths


# ---------------------------------------------------------------- 화면 (kpi.js) — node 로 실제 그리기, 영문 id 노출 0
def test_portal_screen_renders_cards_trace_and_shows_no_raw_ids(tmp_path):
    import json
    import shutil
    import subprocess
    node = shutil.which('node')
    if node is None:
        pytest.skip('node 없음')
    rep = run()
    tr = kpi.trace(Fake(TS, BIZ), 'msr:availability', '24h', now=NOW, time_scale=20)
    data = tmp_path / 'data.json'
    data.write_text(json.dumps({'rep': rep, 'tr': tr}, ensure_ascii=False, default=str), encoding='utf-8')
    script = r"""
const vm = require('vm'); const fs = require('fs');
const ctx = { window: {}, console, location: { protocol: 'http:', hostname: 'x' } }; vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
const d = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const el = { innerHTML: '', querySelector: () => null };
ctx.window.hydKpi._render({ el, period: '24h', data: d.rep, trace: { measure: 'msr:availability', title: '설비 가동률', data: d.tr } });
console.log(JSON.stringify(el.innerHTML));
"""
    out = subprocess.run([node, '-e', script, str(ROOT / 'it' / 'portal' / 'www' / 'kpi.js'), str(data)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    html = json.loads(out.stdout)
    text = re.sub(r'<[^>]+>', ' ', html)
    assert html.count('class="card kpi-card') == 21 and html.count('data-kpi-trace=') == 3       # 미달 3장에만 '원인 찾기'
    for word in ('재무', '학습과 성장', '설비 가동률', '달성률 95.3 %', '계산 불가', '원인 처리 건', '처리 건 열기', '지표별 계산 정의 표'):
        assert word in text, word
    assert 'href="#/instances/anomaly_response.i4"' in html
    shown = re.sub(r'<code>[^<]*</code>', ' ', html)                                                     # 원천 표 이름(code)은 근거로 남긴다
    shown = re.sub(r'<[^>]+>', ' ', shown)
    leaks = re.findall(r'\b(?:msr|skill|sv|obj|persp|cause|pattern|asset|dept|anomaly_response)[:.][\w-]+', shown)
    assert leaks == [], leaks
