"""Explicit counterfactual model for the HYD teaching simulator, not a real PLC.

Calibration source: ot/plant-sim/plantsim/thermal.py and plc.py. No pattern or
SOP identity selects an answer. Each prediction applies the supplied actions
to the supplied current state and solves the constant-input thermal ODE.
The real plant's interlocks remain authoritative; these are open-loop values.
"""
from copy import deepcopy
from datetime import datetime
import math

MODEL_ID = 'hydraulic-lumped-simulator-v1'
MODEL_REVISION = '1.0'
MODEL_SCOPE = 'HYD teaching simulator; constant-input open-loop nominal prediction'
PARAMETERS = {'heat': 1.0, 'leak_heat': 0.08, 'base_cooling': 0.005,
              'fan_cooling': 0.05036, 'heat_capacity': 20.0,
              'pressure_base': 155.0, 'pressure_load': 0.3, 'pressure_leak': 130.0}


def number(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name}: finite numeric input required')
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name}: outside model domain [{low}, {high}]')
    return float(value)


def predict(snapshot, actions, horizon_s):
    """Predict nominal values with every disturbance held at its observed value.

    Input fields are explicit simulator telemetry. Unknown model/state/action
    or missing inputs fail; there is no healthy-state or static-table fallback.
    """
    if snapshot.get('forecast_model') != MODEL_ID:
        raise ValueError('unsupported or unspecified forecast model')
    if snapshot.get('disturbance_ramps') != []:
        raise ValueError('constant-input forecast requires confirmed stationary disturbances')
    if not isinstance(snapshot.get('asset'), str) or not snapshot['asset']:
        raise ValueError('asset identity required')
    observed = datetime.fromisoformat(str(snapshot.get('t') or '').replace('Z', '+00:00'))
    if observed.tzinfo is None:
        raise ValueError('source timestamp requires a timezone')
    if snapshot.get('state') not in ('RUN', 'STOP', 'TRIP') or snapshot.get('pump') not in ('A', 'B'):
        raise ValueError('unsupported PLC state or pump selection')
    horizon = number(horizon_s, 'horizon_s', 0.001, 86400)
    fields = {'ts1': (-20, 150), 't_amb': (-20, 60), 'fan_pct': (0, 100),
              'load_pct': (60, 100), 'cooler_health': (0, 1), 'leak': (0, 1), 'bearing_wear': (0, 1)}
    inputs = {k: number(snapshot.get(k), k, *bounds) for k, bounds in fields.items()}
    operating = dict(inputs, state=snapshot['state'], pump=snapshot['pump'])
    if not isinstance(actions, list):
        raise ValueError('actions must be a list')
    commands = []
    for action in actions:
        if not isinstance(action, dict):
            raise ValueError('action must be an object')
        code = action.get('code')
        if action.get('kind') != 'command':
            if code not in ('WO_CREATE', 'PR_CREATE'):
                raise ValueError(f'unsupported non-command effect: {code}')
            continue  # creating a request is not a physical repair
        commands.append(action)
    if operating['state'] == 'TRIP' and commands and not any(a['code'] == 'RESET' for a in commands):
        raise ValueError('PLC TRIP requires an explicit eligible RESET')
    for action in commands:
        code, value = action.get('code'), action.get('value')
        if code == 'FAN_SET':
            operating['fan_pct'] = number(value, 'fan_pct', 0, 100)
        elif code == 'LOAD_SET':
            operating['load_pct'] = number(value, 'load_pct', 60, 100)
        elif code == 'PUMP_SELECT':
            if value not in ('A', 'B'):
                raise ValueError('pump selection must be A or B')
            operating['pump'] = value
        elif code == 'STOP':
            operating['state'] = 'STOP'
        elif code == 'RESET':
            if inputs['ts1'] >= 55:
                raise ValueError('RESET requires current TS1 below 55 C')
            operating['state'] = 'RUN'
        else:
            raise ValueError(f'unsupported command effect: {code}')
    p = PARAMETERS
    running = operating['state'] == 'RUN'
    load = operating['load_pct'] if running else 0.0
    leak = operating['leak'] if operating['pump'] == 'A' else 0.0
    heat = (p['heat'] + p['leak_heat'] * leak) * (load / 100) ** 2
    cooling = p['base_cooling'] + p['fan_cooling'] * operating['fan_pct'] / 100 * operating['cooler_health']
    steady = operating['t_amb'] + heat / cooling
    endpoint = steady + (inputs['ts1'] - steady) * math.exp(-cooling * horizon / p['heat_capacity'])
    peak = max(inputs['ts1'], endpoint)
    pressure = p['pressure_base'] + p['pressure_load'] * load - p['pressure_leak'] * leak
    flow = 10 * load / 100 * (1 - leak) if running else 0.0
    fan = operating['fan_pct'] if running else 0.0
    vibration = lambda temperature: 0.55 + 0.004 * max(0, temperature - 48) + operating['bearing_wear'] * (fan / 60) ** 2
    peak_vibration = vibration(peak)
    interlocks = []
    if running:
        if peak > 65:
            interlocks.append('OVERTEMP')
        if pressure < 130:
            interlocks.append('LOW_PRESSURE')
        if peak_vibration >= 2:
            interlocks.append('HIGH_VIBRATION')
    return {'model_id': MODEL_ID, 'model_revision': MODEL_REVISION,
            'scope': MODEL_SCOPE,
            'asset': snapshot['asset'], 'source_t': snapshot['t'], 'horizon_s': horizon,
            'inputs': dict(inputs, state=snapshot['state'], pump=snapshot['pump']),
            'actions': deepcopy(actions), 'operating': operating, 'parameters': deepcopy(p),
            'values': {'ts1': endpoint, 'ts1_steady': steady, 'ts1_peak': peak,
                       'ps1': pressure, 'fs1': flow, 'vs1': vibration(endpoint), 'vs1_peak': peak_vibration},
            'predicted_interlocks': interlocks,
            'assumptions': ['observed disturbances and ambient temperature remain constant',
                            'sensor noise is not predicted',
                            'actual interlocks can interrupt this counterfactual trajectory',
                            'maintenance and purchase requests have no immediate physical repair effect']}
