"""B5 What-if 관점 중요도 바꿔 보기(시험 실행): BSC 관점(이름 · 지표 소속은 시드 온톨로지에서) 비중을 바꾸면 카드 점수의 성과 지표 득실이
그 비중으로 다시 계산되고 1순위가 바뀔 수 있다. 1순위가 뒤집히는 비중은 기존 경계값 찾기로 찾고 그 값에서 다시 계산해 확인한다.
원본 묶음 · 정책은 그대로, 같은 입력은 같은 결과, 잘못된 비중은 사유."""
import copy

import pytest
from fastapi.testclient import TestClient

from agentsvc import whatif
from test_kpi import measure_rows
from test_whatif import api, bundle, ent, mf  # noqa: F401 — 같은 묶음 · 업무 DB 계약(fixture)


def persp_rows():
    """t3_perspectives.cypher 가 돌려줄 행: 시드 instances.cypher 의 관점 · 목표 · 지표를 그대로 읽어 만든다(이름을 손으로 적지 않음)."""
    out = {}
    for m in measure_rows():
        r = out.setdefault(m['perspective'], {'id': m['perspective'], 'name': m['perspectiveName'], 'ord': m['perspectiveOrder'], 'measures': []})
        r['measures'].append(m['id'])
    return sorted(out.values(), key=lambda r: -r['ord'])


def pb():
    b = bundle()
    b['perspectives'] = whatif.load_perspectives(persp_rows())
    return b


def by_id(ev):
    return {c['id']: c for c in ev['cards']}


def test_perspectives_come_from_the_ontology_and_show_which_ones_this_decision_uses():
    v = whatif.perspective_view(pb())
    assert v['available'] and [p['name'] for p in v['perspectives']] == ['재무', '고객', '내부 프로세스', '학습과 성장']
    used = {p['name']: p for p in v['perspectives'] if p['inUse']}
    assert set(used) == {'내부 프로세스'} and set(used['내부 프로세스']['measures']) == {'전력 사용량', '생산량', '설비 가동률'}
    assert not whatif.perspective_view(bundle())['available']                                 # 그래프에서 못 읽으면 꺼짐 + 사유
    assert '없습니다' in whatif.load_perspectives([])['error']


def test_perspective_weight_rescales_the_bsc_part_and_can_flip_the_first_place(mf):
    b = pb()
    base = whatif.evaluate(b, mf)
    internal = next(p['id'] for p in whatif.perspective_view(b)['perspectives'] if p['inUse'])
    twice = whatif.evaluate(b, mf, None, whatif.check_policy(b['dmn'], {'perspectives': {internal: 2.0}}, whatif.perspective_view(b)))
    for cid, c in by_id(base).items():
        if not c['feasible']:
            continue
        g0 = {x['perspective']: x for x in c['bscByPerspective']}
        g2 = {x['perspective']: x for x in by_id(twice)[cid]['bscByPerspective']}
        assert g2[internal]['loss'] == pytest.approx(2 * g0[internal]['loss']) and g2[internal]['gain'] == pytest.approx(2 * g0[internal]['gain'])
        assert by_id(twice)[cid]['scoreParts']['bsc'] == pytest.approx(2 * c['scoreParts']['bsc'], abs=0.02)
    # 이 판단의 득실에 없는 관점(재무)은 바꿔도 그대로
    fin = whatif.evaluate(b, mf, None, {'weights': {}, 'penalties': {}, 'perspectives': {'persp:financial': 5.0}})
    assert [(c['id'], c['score']) for c in fin['cards']] == [(c['id'], c['score']) for c in base['cards']]
    flipped = whatif.evaluate(b, mf, None, {'weights': {}, 'penalties': {}, 'perspectives': {internal: 5.0}})
    assert flipped['top']['decision'] != base['top']['decision']


def test_the_boundary_weight_really_flips_the_first_place(mf):
    b = pb()
    base = whatif.evaluate(b, mf)['top']['decision']
    found = [x for x in whatif.find_boundaries(b, mf) if x['variable'].startswith('v:')]
    assert found, '관점 중요도 경계값이 있어야 한다'
    for x in found:
        assert x['label'].startswith("관점 '") and x['unit'] == '배' and x['policy']['perspectives']
        top = whatif.evaluate(b, mf, None, x['policy'])['top']['decision']
        assert top == x['topAfter'] != base
        before = dict(x['policy'], perspectives={k: v - (v - x['base']) * 0.02 for k, v in x['policy']['perspectives'].items()})
        assert whatif.evaluate(b, mf, None, before)['top']['decision'] == base                    # 경계 바로 앞은 원래 1순위


def test_original_bundle_and_policy_stay_and_same_input_same_result(mf):
    b = pb()
    before, tradeoffs, dmn = whatif.original_fingerprint(b, mf), copy.deepcopy(b['tradeoffs']), copy.deepcopy(b['dmn'])
    pol = {'weights': {}, 'penalties': {}, 'perspectives': {'persp:internal': 3.7}}
    r1, r2 = whatif.evaluate(b, mf, None, pol), whatif.evaluate(b, mf, None, pol)
    assert r1 == r2
    whatif.find_boundaries(b, mf)
    assert whatif.original_fingerprint(b, mf) == before and b['tradeoffs'] == tradeoffs and b['dmn'] == dmn
    assert whatif.evaluate(b, mf)['top'] == whatif.evaluate(pb(), mf)['top']                 # 원래대로


def test_bad_perspective_weights_are_refused_with_reasons():
    b = pb()
    pv = whatif.perspective_view(b)
    with pytest.raises(ValueError, match='없는 관점'):
        whatif.check_policy(b['dmn'], {'perspectives': {'persp:none': 1}}, pv)
    with pytest.raises(ValueError, match='0 ~ 10배'):
        whatif.check_policy(b['dmn'], {'perspectives': {'persp:internal': -1}}, pv)
    with pytest.raises(ValueError, match='0 ~ 10배'):
        whatif.check_policy(b['dmn'], {'perspectives': {'persp:internal': 'x'}}, pv)
    with pytest.raises(ValueError, match='바꿀 수 없습니다'):
        whatif.check_policy(b['dmn'], {'perspectives': {'persp:internal': 2}}, whatif.perspective_view(bundle()))


def test_api_reads_perspectives_from_the_graph_and_runs_the_trial(api, monkeypatch):
    from agentsvc import main
    client, calls, entclient = api

    class KG:
        def perspectives(self):
            return persp_rows()
    monkeypatch.setattr(main, 'kg', KG())
    monkeypatch.setattr(main, '_kg', lambda: main.kg)
    base = client.post('/api/agent/whatif', json={'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'}).json()
    assert base['perspectives']['available'] and any(p['inUse'] for p in base['perspectives']['perspectives'])
    sid = base['id']
    t = client.post(f'/api/agent/whatif/{sid}/try', json={'policy': {'perspectives': {'persp:internal': 5}}}).json()
    assert t['top']['decision'] != base['top']['decision'] and '바뀌었습니다' in t['summary'] and t['original']['unchanged']
    assert client.post(f'/api/agent/whatif/{sid}/try', json={}).json()['top'] == base['top']
    assert client.post(f'/api/agent/whatif/{sid}/try', json={'policy': {'perspectives': {'persp:x': 1}}}).status_code == 400
    bnd = client.post(f'/api/agent/whatif/{sid}/boundaries', json={}).json()['boundaries']
    assert any(x['variable'] == 'v:persp:internal' for x in bnd)
    assert entclient.get('/api/transactions').json() == []


def test_without_the_graph_the_perspective_trial_says_why(api):
    client, _, _ = api                                                                         # main.kg = object() → 관점 못 읽음
    base = client.post('/api/agent/whatif', json={'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'}).json()
    assert base['perspectives']['available'] is False and '읽지 못했습니다' in base['perspectives']['reason']
    r = client.post(f"/api/agent/whatif/{base['id']}/try", json={'policy': {'perspectives': {'persp:internal': 2}}})
    assert r.status_code == 400 and '바꿀 수 없습니다' in r.json()['detail']
