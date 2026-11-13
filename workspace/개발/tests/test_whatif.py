"""손익 · What-if(it/agent/agentsvc/whatif.py) — 시드 업무 값(MES · ERP · CMMS · QMS · EMS)으로 냉각 카드 넷의 손익이 상식에 맞는가.

값은 seed.sql · 마이그레이션의 수업 데이터 그대로(HYD-01: 납기까지 5.98 h · 잔량 1500 ea · 300 ea/h · 시간당 50만원 · 위약금 120만원/h ·
고장 비용 · MTBF, 쿨러 핀 세척 표준 작업 3 h · 40만원). 정비 시점은 카드가 싣는다(cards.option_window)."""
import pytest

from agentsvc import cards, whatif

READ_AT = '2026-10-30T06:10:00Z'
NIGHT = {'id': 'MW-HYD-01-N', 'starts_at': '2026-10-30T15:09:00+00:00', 'name': '이번 예정된 정비 시간'}      # 8.98 h 뒤
VALUES = {'mes.due_in_h': 5.98, 'mes.remaining_qty': 1500, 'mes.rate_per_h': 300, 'mes.hour_value': 50, 'erp.penalty_per_h': 120,
          'erp.failure_cost': 800, 'cmms.mtbf_h': 1260, 'qms.auto_qty': 800, 'qms.auto_claim': 3000, 'qms.auto_defect_p': 0.15,
          'ems.fan_boost_kw': 4, 'ems.energy_rate': 0.02}
MF = {'read_at': READ_AT,
      'values': {k: {'value': v, 'system': k.split('.')[0].upper(), 'path': '/x', 'field': k.split('.')[1], 'label': whatif.FIELD_LABELS[k],
                     'unit': whatif.UNITS[k], 'as_of': None} for k, v in VALUES.items()},
      'tasks': {'SOP-COOL-14': {'sop': 'SOP-COOL-14', 'name': '쿨러 핀 세척', 'stop_h': 3.0, 'labor_cost': 40.0, 'part_no': None, 'part_qty': 0,
                                'table': 'maintenance_profiles', 'path': '/cmms/tasks'}},
      'parts': {}}
WO = {'code': 'WO_CREATE', 'kind': 'transaction', 'value': 'SOP-COOL-14'}
CARDS = {
    'SOP-COOL-11': {'id': '11', 'actions': [{'code': 'FAN_SET', 'kind': 'command', 'value': 100}], 'relation': 'MITIGATED_BY',
                    'forecast': [{'variable': 'sv:ts1', 'value': 49.8}]},
    'SOP-COOL-12': {'id': '12', 'actions': [{'code': 'FAN_SET', 'kind': 'command', 'value': 100}, {'code': 'LOAD_SET', 'kind': 'command', 'value': 80}],
                    'relation': 'MITIGATED_BY', 'forecast': [{'variable': 'sv:ts1', 'value': 44.6}]},
    'SOP-COOL-13': {'id': '13', 'actions': [{'code': 'LOAD_SET', 'kind': 'command', 'value': 70}, WO], 'relation': 'MITIGATED_BY',
                    'forecast': [{'variable': 'sv:ts1', 'value': 47.7}], 'window': dict(NIGHT, basis='hours_at_next_window')},
    'SOP-COOL-14': {'id': '14', 'actions': [WO], 'relation': 'REMEDIED_BY', 'forecast': [{'variable': 'sv:ts1', 'value': 28.0}],
                    'window': dict(cards.IMMEDIATE)},
}


def money(sop):
    out = whatif.card_money(CARDS[sop], MF)
    assert out['complete'], out['missing']
    return {i['key']: i['value_won'] for i in out['items']}, out['total_won']


def test_야간_창의_작업지시는_납기_전_정지_지연으로_세지_않고_그때까지의_고장_위험을_센다():
    """G1-06: 「부하 70 %와 야간 핀 세척」의 작업지시 정지 3 h 를 납기(5.98 h) 전 손실 · 지연으로 셌다 — 야간 창은 8.98 h 뒤다."""
    items, _ = money('SOP-COOL-13')
    assert items['production'] == -round(50 * 5.98 * (1 - 70 / 90) * 10_000)          # 감산만(정지 없음)
    late = 1500 / (300 * 70 / 90) - 5.98
    assert items['delay'] == -round(120 * late * 10_000)
    assert items['failure'] == -round(800 * 5.98 / 1260 * 10_000)                         # 근본 조치는 창에서 — 그 전까지 위험이 남는다


def test_지금_정지하고_세척하면_그_정지가_납기_전에_있어_생산과_지연을_잃고_고장_위험은_없다():
    items, _ = money('SOP-COOL-14')
    assert items['production'] == -3 * 50 * 10_000
    assert items['delay'] == -round(120 * ((3 + 1500 / 300) - 5.98) * 10_000)
    assert items['failure'] == 0 and items['quality'] == 0


def test_납기가_급할_때_손익_순서는_완화가_앞서고_지금_세우는_세척이_가장_크게_잃는다():
    totals = {sop: money(sop)[1] for sop in CARDS}
    assert totals['SOP-COOL-11'] > totals['SOP-COOL-12'] > totals['SOP-COOL-13'] > totals['SOP-COOL-14']


def test_작업지시의_시점을_모르면_손익을_지어내지_않고_미확인으로_둔다():
    unknown = dict(CARDS['SOP-COOL-13'], window=None)
    out = whatif.card_money(unknown, MF)
    assert not out['complete'] and {'생산 감소', '납기 지연 위약금'} <= set(out['missing'])


def test_표준_작업이_없는_작업지시는_그_작업이_납기_뒤면_생산은_계산하고_작업비만_미확인이다():
    mf = dict(MF, tasks={})
    out = whatif.card_money(CARDS['SOP-COOL-13'], mf)
    assert out['missing'] == ['정비 작업비']


@pytest.mark.parametrize('values, ok', [({'due_h': 3}, True), ({'due_h': -1}, False), ({'week_hours': 169}, False), ({'nope': 1}, False),
                                        ({'claim': 'x'}, False)], ids=['범위 안', '음수 시간', '범위 위', '모르는 값', '숫자 아님'])
def test_시험값은_정한_이름_범위_숫자만_받는다(values, ok):
    if ok:
        assert whatif.check_trial(values) == values
    else:
        with pytest.raises(ValueError):
            whatif.check_trial(values)


def test_시험값_한도는_한_곳에서_검사하고_화면도_그_값을_받는다():
    """W3-26: 화면이 「가중치는 −10 ~ 10배」 같은 숫자 사본을 들었다 — 한도는 whatif.LIMITS 하나, 시작 응답이 싣는다."""
    lo, hi = whatif.LIMITS['weights']
    dmn = [{'decision': 'dec:rank-actions', 'rule': 'r', 'rankingPolicy': {'version': 1, 'inputs': {}, 'components': {'bsc': '0'}, 'tieBreak': 'lower_approver'}}]
    assert whatif.check_policy(dmn, {'weights': {'bsc': hi}})['weights'] == {'bsc': hi}
    with pytest.raises(ValueError) as e:
        whatif.check_policy(dmn, {'weights': {'bsc': hi + 1}})
    assert f'{lo:g} ~ {hi:g}' in str(e.value)
    with pytest.raises(ValueError):
        whatif.weeks({'_opts': {}}, MF, 'x', weeks_n=whatif.LIMITS['weeks'][1] + 1)
