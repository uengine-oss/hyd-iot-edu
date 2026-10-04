"""Read-only candidate forecast using fresh, explicitly modelled plant status."""
from datetime import datetime, timezone
from urllib.parse import quote

from copy import deepcopy
from hydcommon.forecast import predict, number, MODEL_ID, MODEL_REVISION, MODEL_SCOPE
from . import decide


REVIEW_POLICY = {'version': 'simulator-consent-v1',
                 'max_adverse_change': {'ts1': 0.5, 'ts1_peak': 2.0, 'vs1': 0.05, 'vs1_peak': 0.05}}


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


def consent_changes(old, current):
    """Ignore clock drift, not model/input/action changes or worsening safety.

    Budgets are conservative teaching review policy, not model accuracy claims.
    Interlocks and DMN exclusions are checked independently with no tolerance.
    """
    if not old or not current or old.get('error') or current.get('error'):
        return ['검토한 현재 모델 예측이 없거나 예측을 확인할 수 없습니다']
    reasons = []
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
    for key, tolerance in REVIEW_POLICY['max_adverse_change'].items():
        a, b = old.get('values', {}).get(key), current.get('values', {}).get(key)
        if a is None or b is None or b > a + tolerance:
            reasons.append(f'예측 {key} 악화 또는 미확인: 새 카드 검토가 필요합니다')
    return reasons
