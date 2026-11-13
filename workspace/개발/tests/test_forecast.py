"""승인 카드의 예측(common/hydcommon/forecast.py) — 지금 설비 상태에 카드의 조치를 적용했을 때 일정 시간 뒤 값과 PLC 인터록을 계산한다.

규칙(모듈 머리말 · 시뮬레이터 PLC 와 같은 계약):
- 입력은 시뮬레이터 원격 측정 그대로다. 모델 · 상태 · 조치를 모르거나 값이 없으면 실패한다(건강한 상태 · 표로 대신하지 않는다).
- 트립(TRIP) 중인 설비에 명령을 내리려면 RESET 이 있어야 하고, RESET 은 유온이 55 ℃ 아래일 때만 된다.
- 작업지시 · 구매 요청 · 정비 일정 변경(업무 조치)은 설비를 바로 고치지 않는다 — 예측 값이 조치 없음과 같다.
- 예측 구간에 트립 선(유온 > 65 · 압력 < 130 · 진동 ≥ 2.0)을 넘으면 그 인터록을 미리 알린다. 운전 중이 아니면 인터록이 없다.
식 자체가 시뮬레이터 적분과 같은지는 test_plant_model.py 가 본다.
"""
import copy
import math

import pytest

from hydcommon import forecast, plant_model as m


def snap(**change):
    s = {'forecast_model': forecast.MODEL_ID, 'disturbance_ramps': [], 'asset': 'HYD-01', 't': '2026-10-30T05:00:00Z',
         'state': 'RUN', 'pump': 'A', 'ts1': 50.0, 't_amb': 25.0, 'fan_pct': 60.0, 'load_pct': 90.0, 'cooler_health': 1.0,
         'leak': 0.0, 'bearing_wear': 0.0}
    s.update(change)
    return s


def cmd(code, value=None):
    return {'kind': 'command', 'code': code, 'value': value}


def test_정상_운전점의_예측은_보정한_평형과_압력_유량을_낸다():
    out = forecast.predict(snap(ts1=48.0), [], 3600)
    v = out['values']
    assert v['ts1'] == pytest.approx(48.0, abs=0.6) and v['ps1'] == pytest.approx(182) and v['fs1'] == pytest.approx(9.0)
    assert out['predicted_interlocks'] == [] and out['model_revision'] == forecast.MODEL_REVISION
    assert out['inputs']['state'] == 'RUN' and out['operating']['fan_pct'] == 60.0 and out['source_t'] == '2026-10-30T05:00:00Z'


@pytest.mark.parametrize('change, word', [
    ({'forecast_model': 'other-model'}, '예측 모델 이름이 없거나'),
    ({'forecast_model': None}, '예측 모델 이름이 없거나'),
    ({'disturbance_ramps': None}, '바뀌는 중인 외란'),
    ({'disturbance_ramps': [{'var': 'cooler_health'}]}, '바뀌는 중인 외란'),
    ({'asset': ''}, '설비 이름'),
    ({'asset': None}, '설비 이름'),
    ({'t': '2026-10-30T05:00:00'}, '시간대가 없습니다'),
    ({'state': 'IDLE'}, '펌프 선택(A · B)이 모델이 아는 값이 아닙니다'),
    ({'pump': 'C'}, '펌프 선택(A · B)이 모델이 아는 값이 아닙니다'),
    ({'ts1': None}, '(ts1) 값이 숫자가 아닙니다'),
    ({'ts1': True}, '(ts1) 값이 숫자가 아닙니다'),
    ({'ts1': '50'}, '(ts1) 값이 숫자가 아닙니다'),
    ({'ts1': math.nan}, '(ts1) 값'),
    ({'ts1': 151.0}, '(ts1) 값'),
    ({'load_pct': 59.0}, '(load_pct) 값'),           # PLC 부하 쓰기 범위 60..100
    ({'fan_pct': 100.5}, '(fan_pct) 값'),
    ({'cooler_health': 1.01}, '(cooler_health) 값'),
    ({'leak': -0.01}, '(leak) 값'),
    ({'bearing_wear': None}, '(bearing_wear) 값이 숫자가 아닙니다'),
], ids=['다른 모델', '모델 없음', '외란 목록 없음', '변하는 외란', '설비 빈 이름', '설비 없음', '시각 시간대 없음', '모르는 상태', '모르는 펌프',
        '유온 없음', '유온 참거짓', '유온 글', '유온 NaN', '유온 범위 밖', '부하 60 미만', '팬 100 초과', '쿨러 건강 1 초과', '누설 음수', '마모 없음'])
def test_모델_상태_입력값이_계약_밖이면_대신하지_않고_실패한다(change, word):
    with pytest.raises(ValueError) as caught:
        forecast.predict(snap(**change), [], 600)
    assert word in str(caught.value)


@pytest.mark.parametrize('horizon', [0, -1, 86401, True, None, math.inf], ids=['0', '음수', '하루 넘음', '참거짓', '없음', '무한'])
def test_예측_구간은_0보다_크고_하루_이하여야_한다(horizon):
    with pytest.raises(ValueError, match='horizon_s'):
        forecast.predict(snap(), [], horizon)


@pytest.mark.parametrize('horizon', [0.001, 86400], ids=['가장 짧음', '하루'])
def test_예측_구간_경계값은_받는다(horizon):
    assert forecast.predict(snap(), [], horizon)['horizon_s'] == horizon


@pytest.mark.parametrize('actions, word', [
    ('FAN_SET', '조치 목록이 목록 꼴이 아닙니다'),
    (['FAN_SET'], '조치 하나가 객체 꼴이 아닙니다'),
    ([cmd('FAN_SET', 101)], '(fan_pct) 값'),
    ([cmd('FAN_SET', None)], '(fan_pct) 값이 숫자가 아닙니다'),
    ([cmd('LOAD_SET', 50)], '(load_pct) 값'),
    ([cmd('PUMP_SELECT', 'C')], '펌프 선택은 A 또는 B 만'),
    ([cmd('VALVE_OPEN', 1)], '설비 명령 VALVE_OPEN 는 예측 모델이 아는 명령이 아닙니다'),
    ([{'kind': 'transaction', 'code': 'EMAIL_SEND'}], '업무 조치 EMAIL_SEND 는'),
    ([{'kind': 'work_order', 'code': 'WO_RESCHEDULE'}], '등록된 업무 거래 종류가 아닙니다'),
], ids=['목록 아님', '조치가 글', '팬 101', '팬 값 없음', '부하 50', '펌프 C', '모르는 명령', '모르는 업무 조치', '일정 변경 종류 틀림'])
def test_모르는_조치나_범위_밖_설정은_거절한다(actions, word):
    with pytest.raises(ValueError) as caught:
        forecast.predict(snap(), actions, 600)
    assert word in str(caught.value)


@pytest.mark.parametrize('actions', [
    [{'kind': 'work_order', 'code': 'WO_CREATE'}],
    [{'kind': 'transaction', 'code': 'PR_CREATE', 'value': 'sup:b'}],
    [{'kind': 'transaction', 'code': 'WO_RESCHEDULE', 'target': 'sys:cmms'}],
], ids=['작업지시', '구매 요청', '정비 일정 변경'])
def test_업무_조치는_설비를_바로_고치지_않아_예측이_조치_없음과_같다(actions):
    degraded = snap(cooler_health=0.43, ts1=58.0)
    base, out = forecast.predict(degraded, [], 1800), forecast.predict(degraded, actions, 1800)
    assert out['values'] == base['values'] and out['operating'] == base['operating']
    assert out['predicted_interlocks'] == base['predicted_interlocks'] == ['OVERTEMP']
    assert out['actions'] == actions and out['actions'] is not actions


def test_트립_중_명령에는_RESET_이_있어야_한다():
    tripped = snap(state='TRIP', ts1=50.0)
    with pytest.raises(ValueError, match=r'복귀\(RESET\)가 있어야'):
        forecast.predict(tripped, [cmd('FAN_SET', 100)], 600)
    out = forecast.predict(tripped, [cmd('RESET'), cmd('FAN_SET', 100)], 600)
    assert out['operating']['state'] == 'RUN' and out['operating']['fan_pct'] == 100.0


@pytest.mark.parametrize('ts1, ok', [(54.9, True), (m.RESET_TS1, False), (60.0, False)], ids=['55 아래', '딱 55', '60'])
def test_RESET_은_유온이_55도_아래일_때만_된다(ts1, ok):
    tripped = snap(state='TRIP', ts1=ts1)
    if ok:
        assert forecast.predict(tripped, [cmd('RESET')], 600)['operating']['state'] == 'RUN'
    else:
        with pytest.raises(ValueError, match='지금 유온이 55 ℃ 아래일 때만'):
            forecast.predict(tripped, [cmd('RESET')], 600)


def test_트립_중_조치_없는_예측은_명령이_아니라서_받고_자연_냉각만_한다():
    """명령이 없으면 RESET 도 요구하지 않는다 — 멈춘 설비는 팬 냉각 없이 식는다(G3b-17, 판본 1.1). 인터록은 운전 중에만."""
    out = forecast.predict(snap(state='TRIP', ts1=65.5, fan_pct=100.0), [], 600)
    natural = 25 + (65.5 - 25) * math.exp(-m.K_BASE * 600 / m.C)
    assert out['values']['ts1'] == pytest.approx(natural) and out['values']['ts1'] > m.RESET_TS1
    assert (out['values']['fs1'], out['predicted_interlocks']) == (0.0, [])


@pytest.mark.parametrize('change, actions, interlock', [
    ({'cooler_health': 0.43, 'ts1': 58.0}, [], 'OVERTEMP'),                                  # 열화 쿨러 — 평형 ~70 ℃
    ({'leak': 0.5}, [], 'LOW_PRESSURE'),                                                     # 155 + 27 − 65 = 117 bar
    ({'bearing_wear': 0.8}, [cmd('FAN_SET', 100)], 'HIGH_VIBRATION'),                        # 팬 100 → ~2.8 mm/s
], ids=['과열', '저압', '고진동'])
def test_예측_구간에_트립_선을_넘으면_그_인터록을_미리_알린다(change, actions, interlock):
    out = forecast.predict(snap(**change), actions, 3600)
    assert interlock in out['predicted_interlocks']


@pytest.mark.parametrize('change, actions', [
    ({'cooler_health': 0.43, 'ts1': 58.0}, [cmd('FAN_SET', 100), cmd('LOAD_SET', 80)]),     # 완화 — 평형 ~49 ℃
    ({'leak': 0.5}, [cmd('PUMP_SELECT', 'B')]),                                               # 예비 펌프 B 는 새지 않는다
    ({'bearing_wear': 0.8}, [cmd('FAN_SET', 40)]),
    ({'cooler_health': 0.43, 'ts1': 64.0, 'leak': 0.5, 'bearing_wear': 0.9}, [cmd('STOP')]), # 멈추면 인터록 없음
], ids=['완화', '펌프 전환', '팬 낮춤', '정지'])
def test_조치가_원인을_피하면_인터록이_없다(change, actions):
    assert forecast.predict(snap(**change), actions, 3600)['predicted_interlocks'] == []


@pytest.mark.parametrize('ts1, interlocks', [(65.0, []), (65.01, ['OVERTEMP'])], ids=['딱 65', '65 넘음'])
def test_과열은_지금_값을_포함한_예측_최고가_65도를_넘을_때다(ts1, interlocks):
    """PLC 는 TS1 > 65 에서 트립한다. 건강한 쿨러라 앞으로 식더라도 예측 최고(ts1_peak)는 지금 값이다."""
    out = forecast.predict(snap(ts1=ts1), [], 600)
    assert out['values']['ts1'] < ts1 and out['values']['ts1_peak'] == ts1
    assert out['predicted_interlocks'] == interlocks


def test_예측은_받은_입력을_바꾸지_않는다():
    s, actions = snap(), [cmd('FAN_SET', 100)]
    before = copy.deepcopy((s, actions))
    out = forecast.predict(s, actions, 600)
    out['actions'][0]['value'] = 0
    out['parameters']['heat'] = 99
    assert (s, actions) == before and forecast.PARAMETERS['heat'] == m.K_HEAT
