"""Read-only candidate forecast using fresh, explicitly modelled plant status."""
from datetime import datetime, timezone
import math
import os
from urllib.parse import quote

from copy import deepcopy
from hydcommon.forecast import predict, number, MODEL_ID, MODEL_REVISION, MODEL_SCOPE
from . import decide


# A129: `max_adverse_change` is the budget at the reviewed instant. The plant keeps evolving between the human's review
# and the command (TS1 rises while the card is read), and at TIME_SCALE=20 a few wall-clock seconds are minutes of
# simulated time, so the budget grows with the *simulated* time elapsed between the two forecasts' source timestamps
# (`max_adverse_rate_per_sim_min`, bounded by the lumped model's heating rate: ≤ 1.2 ℃/sim-min for the teaching cooler
# case, vibration 0.004/℃). Past `max_review_age_sim_s` the reviewed forecast is stale whatever the values did.
REVIEW_POLICY = {'version': 'simulator-consent-v2',
                 'max_adverse_change': {'ts1': 0.5, 'ts1_peak': 2.0, 'vs1': 0.05, 'vs1_peak': 0.05},
                 'max_adverse_rate_per_sim_min': {'ts1': 1.0, 'ts1_peak': 1.5, 'vs1': 0.006, 'vs1_peak': 0.006},
                 'max_review_age_sim_s': 1800}


def stack_time_scale():
    """Simulated seconds per wall-clock second: the process service publishes the stack's TIME_SCALE; env, then 1."""
    try:
        published = decide._get_json(f'{decide.PROCESS_URL}/api/process/mode').get('time_scale')
    except Exception:  # noqa: BLE001 — unreachable process: fall back to the environment, never block the check
        published = None
    for candidate in (published, os.getenv('TIME_SCALE')):
        try:
            scale = float(candidate)
        except (TypeError, ValueError):
            continue
        if math.isfinite(scale) and scale > 0:
            return scale
    return 1.0


def _elapsed_sim_s(old, current, time_scale):
    """Simulated seconds between the reviewed and the current forecast's plant timestamps; None when either is unknown."""
    try:
        stamps = [datetime.fromisoformat(str(c.get('source_t') or '').replace('Z', '+00:00')) for c in (old, current)]
    except ValueError:
        return None
    if any(s.tzinfo is None for s in stamps):
        return None
    return max(0.0, (stamps[1] - stamps[0]).total_seconds()) * time_scale


def binding(kg, asset):
    row = kg.forecast_model(asset)
    if (row.get('asset'), row.get('model_id'), row.get('model_revision'), row.get('scope')) != (
            asset, MODEL_ID, MODEL_REVISION, MODEL_SCOPE):
        raise ValueError('missing, incompatible or out-of-scope asset forecast model binding')
    number(row.get('horizon_s'), 'bound horizon_s', 0.001, 86400)
    return row


def source(asset):
    source = f'{decide.PROCESS_URL}/api/plant/{quote(asset, safe="")}/status'
    snapshot = decide._get_json(source)
    if snapshot.get('asset') != asset:
        raise ValueError('forecast source asset does not match the request')
    stamp = datetime.fromisoformat(str(snapshot.get('t') or '').replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('forecast source timestamp requires a timezone')
    age = (datetime.now(timezone.utc) - stamp).total_seconds()
    if not -2 <= age <= decide.MAX_APPROVAL_FACT_AGE_S:
        raise ValueError('forecast source is stale or future-dated')
    return snapshot, {'source':'process plant.status', 'kind':'explicit simulator model state',
                      'asset':asset, 'observed_at':snapshot['t'], 'age_seconds':age}


def _predict(bound, snapshot, provenance, actions, horizon_s):
    result = predict(snapshot, actions, horizon_s)
    result['binding'] = deepcopy(bound)
    result['review_policy'] = deepcopy(REVIEW_POLICY)
    result['provenance'] = deepcopy(provenance)
    result['execution_authorized'] = False
    return result


def current(kg, asset, actions, horizon_s):
    bound = binding(kg, asset)
    snapshot, provenance = source(asset)
    return _predict(bound, snapshot, provenance, actions, horizon_s)


def candidates(kg, asset, skills):
    """One bound model and one fresh snapshot for all candidates. Never use design constants."""
    forecasts, contexts = {}, {}
    try:
        bound = binding(kg, asset)
        snapshot, provenance = source(asset)
    except Exception as exc:
        return {}, {sid: {'error': str(exc)[:300], 'execution_authorized': False} for sid in skills}
    for sid, skill in skills.items():
        try:
            result = _predict(bound, snapshot, provenance, skill.get('actions') or [], bound['horizon_s'])
            contexts[sid] = result
            # Stable equilibrium is used for existing DMN thresholds/ranking. The
            # finite-horizon trajectory and its interlocks remain mandatory below.
            specs = [('sv:ts1', 'ts1_steady', '평형 유온', '℃'),
                     ('sv:ps1', 'ps1', '토출 압력', 'bar'),
                     ('sv:fs1', 'fs1', '유량', 'l/min')]
            forecasts[sid] = {variable: {'variableName': name, 'value': round(result['values'][key], 3),
                'unit': unit, 'method': f'{MODEL_ID}@{MODEL_REVISION}; constant inputs',
                'id': f'{MODEL_ID}@{MODEL_REVISION}:{sid}:{variable}'} for variable, key, name, unit in specs}
        except (ValueError, TypeError, KeyError) as exc:
            contexts[sid] = {'error': str(exc)[:300], 'binding': deepcopy(bound), 'execution_authorized': False,
                             'source_snapshot': deepcopy(snapshot), 'provenance': deepcopy(provenance),
                             'actions': deepcopy(skill.get('actions') or [])}
    return forecasts, contexts


def consent_changes(old, current, time_scale=None):
    """Ignore clock drift, not model/input/action changes or worsening safety.

    Budgets are conservative teaching review policy, not model accuracy claims.
    Interlocks and DMN exclusions are checked independently with no tolerance.
    `time_scale` (simulated s per wall s) defaults to the running stack's value.
    """
    if not old or not current or old.get('error') or current.get('error'):
        return ['검토한 현재 모델 예측이 없거나 예측을 확인할 수 없습니다']
    reasons = []
    elapsed = _elapsed_sim_s(old, current, stack_time_scale() if time_scale is None else float(time_scale))
    max_age = REVIEW_POLICY['max_review_age_sim_s']
    if elapsed is not None and elapsed > max_age:
        reasons.append(f'검토한 예측이 시뮬레이션 {elapsed / 60:.0f}분 전 상태입니다: 새 카드 검토가 필요합니다')
    minutes = min(elapsed or 0.0, max_age) / 60
    for key in ('model_id', 'model_revision', 'scope', 'binding', 'horizon_s', 'parameters',
                'actions', 'assumptions', 'review_policy'):
        if old.get(key) != current.get(key):
            reasons.append(f'예측 {key} 변경: 새 카드 검토가 필요합니다')
    # TS1 evolves with time. Disturbances, ambient conditions and operating
    # settings may not change behind the reviewed counterfactual.
    for key in set(old.get('inputs', {})) | set(current.get('inputs', {})):
        if key != 'ts1' and old['inputs'].get(key) != current['inputs'].get(key):
            reasons.append(f'예측 입력 {key} 변경: 새 카드 검토가 필요합니다')
    if current.get('predicted_interlocks'):
        reasons.append('예측 구간에서 PLC 인터록이 예상됩니다')
    rates = REVIEW_POLICY['max_adverse_rate_per_sim_min']
    for key, tolerance in REVIEW_POLICY['max_adverse_change'].items():
        a, b = old.get('values', {}).get(key), current.get('values', {}).get(key)
        if a is None or b is None or b > a + tolerance + rates.get(key, 0.0) * minutes:
            reasons.append(f'예측 {key} 악화 또는 미확인: 새 카드 검토가 필요합니다')
    return reasons
