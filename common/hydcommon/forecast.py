"""Explicit counterfactual model for the HYD teaching simulator, not a real PLC.

The model is hydcommon.plant_model — the same constants and equations plant-sim steps every simulated second — solved here
in closed form for constant inputs. No pattern or SOP identity selects an answer. Each prediction applies the supplied
actions to the supplied current state. The real plant's interlocks remain authoritative; these are open-loop values.
"""
from .words import particle
from copy import deepcopy
from datetime import datetime
import math

from . import plant_model as m

MODEL_ID = 'hydraulic-lumped-simulator-v1'
MODEL_REVISION = '1.1'          # 1.1: a stopped or tripped unit cools naturally only (no oil flow through the cooler)
MODEL_SCOPE = '교육용 HYD 시뮬레이터 — 입력을 고정한 열린 루프 기준 예측'
PARAMETERS = {'heat': m.K_HEAT, 'leak_heat': m.K_LEAK, 'base_cooling': m.K_BASE,
              'fan_cooling': m.K_COOL, 'heat_capacity': m.C,
              'pressure_base': m.PS_BASE, 'pressure_load': m.PS_LOAD, 'pressure_leak': m.LEAK_PS1_DROP}


#: 예측 입력 · 설정 칸의 학생 말(오류 문장 — 판단 카드 제외 사유 · 승인 미리 보기로 학생에게 보인다, G1-10)
LABELS = {'ts1': '유온', 't_amb': '주변 온도', 'fan_pct': '팬 속도', 'load_pct': '펌프 부하', 'cooler_health': '쿨러 상태',
          'leak': '누유 정도', 'bearing_wear': '베어링 마모', 'horizon_s': '예측 시간(초)'}


def number(value, name, low, high):
    label = f'{LABELS.get(name, name)}({name})'
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'예측할 수 없습니다: {label} 값이 숫자가 아닙니다 — 설비 보고에서 이 값이 빠졌거나 글자로 왔습니다')
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'예측할 수 없습니다: {label} 값 {value}{particle(value, "이")} 예측 모델이 다루는 범위 {low:g}~{high:g} 밖입니다')
    return float(value)


def predict(snapshot, actions, horizon_s):
    """Predict nominal values with every disturbance held at its observed value.

    Input fields are explicit simulator telemetry. Unknown model/state/action
    or missing inputs fail; there is no healthy-state or static-table fallback.
    """
    if snapshot.get('forecast_model') != MODEL_ID:
        raise ValueError('예측할 수 없습니다: 설비 보고의 예측 모델 이름이 없거나 이 시뮬레이터 모델이 아닙니다')
    if snapshot.get('disturbance_ramps') != []:
        raise ValueError('예측할 수 없습니다: 지금 바뀌는 중인 외란(주입 · 열화 진행)이 있어 입력을 고정한 예측이 맞지 않습니다')
    if not isinstance(snapshot.get('asset'), str) or not snapshot['asset']:
        raise ValueError('예측할 수 없습니다: 어느 설비의 보고인지(설비 이름)가 없습니다')
    observed = datetime.fromisoformat(str(snapshot.get('t') or '').replace('Z', '+00:00'))
    if observed.tzinfo is None:
        raise ValueError('예측할 수 없습니다: 설비 보고 시각에 시간대가 없습니다')
    if snapshot.get('state') not in ('RUN', 'STOP', 'TRIP') or snapshot.get('pump') not in ('A', 'B'):
        raise ValueError('예측할 수 없습니다: 설비 상태(RUN · STOP · TRIP)나 펌프 선택(A · B)이 모델이 아는 값이 아닙니다')
    horizon = number(horizon_s, 'horizon_s', 0.001, 86400)
    fields = {'ts1': (-20, 150), 't_amb': (-20, 60), 'fan_pct': (0, 100),
              'load_pct': (m.LOAD_MIN_PCT, 100), 'cooler_health': (0, 1), 'leak': (0, 1), 'bearing_wear': (0, 1)}
    inputs = {k: number(snapshot.get(k), k, *bounds) for k, bounds in fields.items()}
    operating = dict(inputs, state=snapshot['state'], pump=snapshot['pump'])
    if not isinstance(actions, list):
        raise ValueError('예측할 수 없습니다: 조치 목록이 목록 꼴이 아닙니다')
    commands = []
    for action in actions:
        if not isinstance(action, dict):
            raise ValueError('예측할 수 없습니다: 조치 하나가 객체 꼴이 아닙니다')
        code = action.get('code')
        if action.get('kind') != 'command':
            if code not in ('WO_CREATE', 'PR_CREATE', 'WO_RESCHEDULE'):
                raise ValueError(f'예측할 수 없습니다: 업무 조치 {code} 는 예측 모델이 아는 조치(정비 요청 · 구매 요청 · 정비 일정 변경)가 아닙니다')
            if code == 'WO_RESCHEDULE' and action.get('kind') != 'transaction':
                raise ValueError('예측할 수 없습니다: 정비 일정 변경(WO_RESCHEDULE)이 등록된 업무 거래 종류가 아닙니다')
            # Creating a request or moving an existing maintenance order's
            # schedule does not repair the asset or change its current controls.
            continue
        commands.append(action)
    if operating['state'] == 'TRIP' and commands and not any(a['code'] == 'RESET' for a in commands):
        raise ValueError('예측할 수 없습니다: 설비가 정지(TRIP) 상태라 설비 명령 전에 복귀(RESET)가 있어야 합니다')
    for action in commands:
        code, value = action.get('code'), action.get('value')
        if code == 'FAN_SET':
            operating['fan_pct'] = number(value, 'fan_pct', 0, 100)
        elif code == 'LOAD_SET':
            operating['load_pct'] = number(value, 'load_pct', m.LOAD_MIN_PCT, 100)
        elif code == 'PUMP_SELECT':
            if value not in ('A', 'B'):
                raise ValueError('예측할 수 없습니다: 펌프 선택은 A 또는 B 만 됩니다')
            operating['pump'] = value
        elif code == 'STOP':
            operating['state'] = 'STOP'
        elif code == 'RESET':
            if inputs['ts1'] >= m.RESET_TS1:
                raise ValueError(f'예측할 수 없습니다: 복귀(RESET)는 지금 유온이 {m.RESET_TS1:g} ℃ 아래일 때만 됩니다')
            operating['state'] = 'RUN'
        else:
            raise ValueError(f'예측할 수 없습니다: 설비 명령 {code} 는 예측 모델이 아는 명령이 아닙니다')
    running = operating['state'] == 'RUN'
    load = operating['load_pct'] if running else 0.0
    leak = m.effective_leak(operating['leak'], operating['pump'])
    cooling = m.cooling_coef(operating['fan_pct'], operating['cooler_health'], running)
    steady = operating['t_amb'] + m.heat(load, leak) / cooling
    endpoint = steady + (inputs['ts1'] - steady) * math.exp(-cooling * horizon / m.C)
    peak = max(inputs['ts1'], endpoint)
    pressure = m.pressure(load, leak)
    flow = m.flow(load, leak, running)
    fan = operating['fan_pct'] if running else 0.0
    vibration = lambda temperature: m.vibration(temperature, operating['bearing_wear'], fan)
    peak_vibration = vibration(peak)
    interlocks = []
    if running:
        if peak > m.TRIP_TS1:
            interlocks.append('OVERTEMP')
        if pressure < m.TRIP_PS1:
            interlocks.append('LOW_PRESSURE')
        if peak_vibration >= m.TRIP_VS1:
            interlocks.append('HIGH_VIBRATION')
    return {'model_id': MODEL_ID, 'model_revision': MODEL_REVISION,
            'scope': MODEL_SCOPE,
            'asset': snapshot['asset'], 'source_t': snapshot['t'], 'horizon_s': horizon,
            'inputs': dict(inputs, state=snapshot['state'], pump=snapshot['pump']),
            'actions': deepcopy(actions), 'operating': operating, 'parameters': deepcopy(PARAMETERS),
            'values': {'ts1': endpoint, 'ts1_steady': steady, 'ts1_peak': peak,
                       'ps1': pressure, 'fs1': flow, 'vs1': vibration(endpoint), 'vs1_peak': peak_vibration},
            'predicted_interlocks': interlocks,
            'assumptions': ['observed disturbances and ambient temperature remain constant',
                            'sensor noise is not predicted',
                            'actual interlocks can interrupt this counterfactual trajectory',
                            'maintenance and purchase requests have no immediate physical repair effect']}
