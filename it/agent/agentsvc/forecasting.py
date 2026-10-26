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


# Names the approval refusal shows a person (2026-10-23 audit P14: '예측 model_revision 변경', '예측 입력 fan_pct 변경').
# Same words as the portal (plainWords.js · enterprise.js inputLabels).
CONTEXT_LABELS = {'model_id': '예측 모델', 'model_revision': '예측 모델 판본', 'scope': '예측 모델 적용 범위',
                  'binding': '설비와 예측 모델의 연결', 'horizon_s': '예측 구간', 'parameters': '예측 모델 계수',
                  'actions': '예측한 조치', 'assumptions': '예측 가정', 'review_policy': '예측 검토 허용 기준'}
INPUT_LABELS = {'ts1': '유온', 't_amb': '주변 온도', 'fan_pct': '팬 속도', 'load_pct': '펌프 부하', 'cooler_health': '쿨러 상태',
                'leak': '누설 비율', 'bearing_wear': '베어링 마모', 'state': '설비 상태', 'pump': '운전 펌프'}
VALUE_LABELS = {'ts1': '예측 유온', 'ts1_peak': '예측 최고 유온', 'vs1': '예측 진동', 'vs1_peak': '예측 최고 진동'}


def requires_plant_consent(actions):
    """Business requests do not authorize immediate plant changes (forecast.predict contract)."""
    return any(a.get('kind') == 'command' for a in actions or [])


def _scale(candidate):
    try:
        scale = float(candidate)
    except (TypeError, ValueError):
        return None
    return scale if math.isfinite(scale) and scale > 0 else None


def stack_time_scale():
    """Simulated seconds per wall-clock second of the running stack.

    The process service publishes its TIME_SCALE on GET /api/definition in every mode. 2026-10-23 audit: this used to read
    /api/process/mode, whose time_scale exists only with the instance runtime — in legacy mode it was null, the agent and
    dmn-mcp containers have no TIME_SCALE (compose.yaml), and the forecast consent budget was computed at 1× on a 20×
    stack. The agent's own TIME_SCALE is used only when the process cannot be reached; with neither the time scale is
    unknown and the check fails with that reason (never a silent 1×)."""
    try:
        published = decide._get_json(f'{decide.PROCESS_URL}/api/definition').get('time_scale')
    except Exception as exc:  # noqa: BLE001 — unreachable process: the explicit environment value may stand in
        reached, published = exc, None
    else:
        scale = _scale(published)
        if scale is None:
            raise ValueError(f'process 가 알려 준 설비 시간 배율(time_scale={published!r})이 올바르지 않습니다')
        return scale
    scale = _scale(os.getenv('TIME_SCALE'))
    if scale is None:
        raise ValueError(f'설비 시간 배율(TIME_SCALE)을 확인할 수 없습니다: process 에 연결하지 못했고({reached}) 환경 변수도 없습니다')
    return scale


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


def consent_changes(old, current, time_scale=None, consented_at=None):
    """Ignore clock drift, not model/input/action changes or worsening safety.

    Budgets are conservative teaching review policy, not model accuracy claims.
    Interlocks and DMN exclusions are checked independently with no tolerance.
    `time_scale` (simulated s per wall s) defaults to the running stack's value.
    """
    if not old or not current or old.get('error') or current.get('error'):
        return ['검토한 현재 모델 예측이 없거나 예측을 확인할 수 없습니다']
    reasons = []
    scale = stack_time_scale() if time_scale is None else float(time_scale)
    elapsed = _elapsed_sim_s(old, current, scale)
    age = elapsed
    if consented_at and elapsed is not None:
        # 예측 나이는 사람이 동의한 시각까지만 잰다 — 승인 뒤 전달까지의 몇 초가 승인을 뒤집지 않는다(지금보다 늦은 동의 시각은 지금으로).
        # 아래 악화 허용폭은 전달 시각까지의 경과(elapsed)로 그대로 잰다
        at_consent = _elapsed_sim_s(old, {'source_t': consented_at}, scale)
        if at_consent is not None:
            age = min(elapsed, at_consent)
    max_age = REVIEW_POLICY['max_review_age_sim_s']
    if age is not None and age > max_age:
        reasons.append(f'검토한 예측이 시뮬레이션 {age / 60:.0f}분 전 상태입니다: 새 카드 검토가 필요합니다')
    minutes = min(elapsed or 0.0, max_age) / 60
    for key in ('model_id', 'model_revision', 'scope', 'binding', 'horizon_s', 'parameters',
                'actions', 'assumptions', 'review_policy'):
        if old.get(key) != current.get(key):
            reasons.append(f'{CONTEXT_LABELS.get(key, "예측 조건")} 변경: 새 카드 검토가 필요합니다')
    # TS1 evolves with time. Disturbances, ambient conditions and operating
    # settings may not change behind the reviewed counterfactual.
    for key in set(old.get('inputs', {})) | set(current.get('inputs', {})):
        if key != 'ts1' and old['inputs'].get(key) != current['inputs'].get(key):
            reasons.append(f'예측 입력 {INPUT_LABELS.get(key, "조건")} 변경: 새 카드 검토가 필요합니다')
    if current.get('predicted_interlocks'):
        reasons.append('예측 구간에서 PLC 인터록이 예상됩니다')
    rates = REVIEW_POLICY['max_adverse_rate_per_sim_min']
    for key, tolerance in REVIEW_POLICY['max_adverse_change'].items():
        a, b = old.get('values', {}).get(key), current.get('values', {}).get(key)
        if a is None or b is None or b > a + tolerance + rates.get(key, 0.0) * minutes:
            reasons.append(f'{VALUE_LABELS.get(key, "예측값")} 악화 또는 미확인: 새 카드 검토가 필요합니다')
    return reasons
