"""B5 KPI 목표값 바꿔 보기(시험 실행): 시험 목표로 달성/미달 · 달성률 · 역추적이 다시 판정되고, 원본 목표(지식 그래프)는 그대로,
같은 입력은 같은 결과, 잘못된 목표는 사유. 지표 · 목표 · 실적은 test_kpi 의 시드 온톨로지 가짜 그래프와 알려진 기록을 그대로 쓴다."""
import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import kpi
from test_kpi import BIZ, NOW, TS, Fake, flat, measure_rows


def run(targets=None, fake=None):
    return kpi.report(fake or Fake(TS, BIZ), '24h', now=NOW, time_scale=20, tenant='hyd', targets=targets)


def test_lower_target_turns_a_missed_measure_into_met_and_back():
    base = flat(run())
    a = base['msr:availability']
    assert (a['value'], a['target'], a['status']) == (90.56, 95, 'missed')
    rep = run({'msr:availability': 90})
    m = flat(rep)['msr:availability']
    assert (m['value'], m['target'], m['status'], m['rate']) == (90.56, 90.0, 'met', 100.6)    # 실적은 같고 판정만
    assert m['original'] == {'target': 95, 'met': False, 'rate': 95.3, 'status': 'missed'} and m['trialTarget'] == 90.0
    assert m['perAssetMet'] == {'HYD-01': True, 'HYD-02': True, 'HYD-03': False}
    ch = rep['trial']['changed']
    assert [c['id'] for c in ch] == ['msr:availability'] and ch[0]['before']['status'] == 'missed' and ch[0]['after']['status'] == 'met'
    assert rep['summary']['missed'] == base_summary()['missed'] - 1 and rep['summaryOriginal'] == base_summary()
    assert rep['trial']['targets'] == [{'id': 'msr:availability', 'name': '설비 가동률', 'unit': '%', 'original': 95, 'trial': 90.0}]
    assert '그대로' in rep['trial']['note']
    assert flat(run())['msr:availability']['status'] == 'missed'                                # 원래대로 = 시험 목표 없이


def base_summary():
    return run()['summary']


def test_a_target_on_a_measure_without_one_and_a_down_measure():
    m = flat(run({'msr:energy-use': 150, 'msr:inventory': 1500}))
    e = m['msr:energy-use']                                   # DOWN 지표: 실적 201.6 > 목표 150 → 미달
    assert (e['status'], e['rate'], e['original']['status']) == ('missed', 74.4, 'no_target')
    assert m['msr:inventory']['status'] == 'met'               # 1200 ≤ 1500


def test_unavailable_measures_stay_unavailable_with_their_reason():
    m = flat(run({'msr:revenue': 1000}))['msr:revenue']
    assert m['status'] == 'unavailable' and m['reason'] and m['original']['status'] == 'unavailable'


def test_trace_uses_the_trial_target():
    t = kpi.trace(Fake(TS, BIZ), 'msr:availability', '24h', now=NOW, time_scale=20, tenant='hyd', targets={'msr:availability': 50})
    assert t['measure']['status'] == 'met' and t['measure']['original']['status'] == 'missed'
    assert all(a['met'] is not False for a in t['assets'])                                     # HYD-03 58.33 ≥ 50
    t0 = kpi.trace(Fake(TS, BIZ), 'msr:availability', '24h', now=NOW, time_scale=20, tenant='hyd')
    assert any(a['met'] is False for a in t0['assets']) and 'original' not in t0['measure']


def test_original_targets_are_never_written_and_same_input_same_result():
    rows = measure_rows()
    snapshot = copy.deepcopy(rows)

    class Frozen(Fake):
        def graph(self, name, cypher, params):
            if name == 'measures':
                return rows                       # 같은 객체를 돌려줘 사본 없이 고치면 드러나게
            return super().graph(name, cypher, params)
    fake = Frozen(TS, BIZ)
    r1 = run({'msr:availability': 90, 'msr:mtbf': 500}, fake)
    r2 = run({'msr:availability': 90, 'msr:mtbf': 500}, fake)
    assert rows == snapshot and r1 == r2
    assert flat(run(None, fake))['msr:availability']['target'] == 95
    assert not any(k[0] != 'graph' and 'insert' in str(k).lower() for k in fake.calls)


@pytest.mark.parametrize('targets,msg', [({'msr:none': 1}, '없는 성과 지표'), ({'msr:availability': 'abc'}, '숫자'),
                                         ({'msr:availability': float('nan')}, '숫자'), ({'msr:availability': True}, '숫자'),
                                         (['msr:availability'], '모양')])
def test_bad_trial_targets_are_refused_with_a_reason(targets, msg):
    with pytest.raises(ValueError, match=msg):
        run(targets)


def test_try_routes(monkeypatch):
    app = FastAPI()
    monkeypatch.setattr(kpi, 'PgSources', lambda *a, **k: _Closable(TS, BIZ))
    kpi.register(app, ts_dsn='x', biz_dsn='y', driver_factory=None, time_scale=20, tenant='hyd')
    c = TestClient(app)
    r = c.post('/api/kpi/try', json={'period': 'all', 'targets': {'msr:availability': 10}})
    assert r.status_code == 200 and flat(r.json())['msr:availability']['status'] == 'met'
    assert c.post('/api/kpi/try', json={'targets': {'msr:x': 1}}).status_code == 400
    t = c.post('/api/kpi/try/trace', json={'measure': 'msr:availability', 'period': 'all', 'targets': {'msr:availability': 10}})
    assert t.status_code == 200 and t.json()['measure']['trialTarget'] == 10
    assert c.post('/api/kpi/try/trace', json={}).status_code == 400
    assert flat(c.get('/api/kpi?period=all').json())['msr:availability']['target'] == 95


class _Closable(Fake):
    def close(self):
        pass
