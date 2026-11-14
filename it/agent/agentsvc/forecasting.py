"""Read-only candidate forecast using fresh, explicitly modelled plant status."""
from datetime import datetime, timezone
import math
import time
from urllib.parse import quote

from copy import deepcopy
from hydcommon.forecast import predict, number, MODEL_ID, MODEL_REVISION, MODEL_SCOPE
from . import decide


# A129: `max_adverse_change` is the budget at the reviewed instant. The plant keeps evolving between the human's review
# and the command (TS1 rises while the card is read), and at TIME_SCALE=20 a few wall-clock seconds are minutes of
# simulated time, so the budget grows with the *simulated* time elapsed between the two forecasts' source timestamps
# (`max_adverse_rate_per_sim_min`, bounded by the lumped model's heating rate: ≤ 1.2 ℃/sim-min for the teaching cooler
# case, vibration 0.004/℃), up to `max_budget_sim_s` of simulated time.
# 검토한 카드의 신선도(`max_review_age_wall_s`)는 벽시계다(결정 2026-10-30, #2) — 사람이 카드를 읽고 고르는 시간에 배속을 곱하지 않는다.
# 전에는 1800 시뮬레이션 초 = 20배속 90초라, 학생이 카드를 1분 남짓 읽으면 승인이 「오래된 예측」으로 거절됐다. 그 사이 설비 변화는
# 위의 악화 허용폭 검사(시뮬레이션 시간 기준)가 지킨다.
REVIEW_POLICY = {'version': 'simulator-consent-v3',
                 'max_adverse_change': {'ts1': 0.5, 'ts1_peak': 2.0, 'vs1': 0.05, 'vs1_peak': 0.05},
                 'max_adverse_rate_per_sim_min': {'ts1': 1.0, 'ts1_peak': 1.5, 'vs1': 0.006, 'vs1_peak': 0.006},
                 'max_budget_sim_s': 1800,
                 'max_review_age_wall_s': 1800}


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
    """Simulated seconds per wall-clock second of the running stack — process GET /api/time-scale (compose 의 TIME_SCALE 한 곳이
    plant-sim · detector · process 에 들어가고, agent · dmn-mcp 는 process 에서 읽는다 — CLAUDE.md 4절). process 에 닿지 못하거나 값이 틀리면
    그 까닭으로 실패한다. 예전의 「닿지 못하면 이 서비스의 TIME_SCALE 환경 변수」 길은 compose 가 agent · dmn-mcp 에 그 값을 주지 않아
    닿지 않는 폴백이었다(지움). 2026-10-23 audit: 1× 로 조용히 계산되던 예측 허용폭."""
    try:
        published = decide._get_json(f'{decide.PROCESS_URL}/api/time-scale').get('time_scale')
    except Exception as exc:  # noqa: BLE001 — 닿지 못한 까닭을 그대로
        raise ValueError(f'설비 시간 배속을 process 에서 읽지 못했습니다({type(exc).__name__}: {str(exc)[:160]}) — process 가 켜져 있는지 확인하세요') from exc
    scale = _scale(published)
    if scale is None:
        raise ValueError(f'process 가 알려 준 설비 시간 배속(time_scale={published!r})이 올바르지 않습니다')
    return scale


def _elapsed_wall_s(old, current):
    """Wall-clock seconds between the reviewed and the current forecast's plant timestamps; None when either is unknown."""
    try:
        stamps = [datetime.fromisoformat(str(c.get('source_t') or '').replace('Z', '+00:00')) for c in (old, current)]
    except ValueError:
        return None
    if any(s.tzinfo is None for s in stamps):
        return None
    return max(0.0, (stamps[1] - stamps[0]).total_seconds())


def binding(kg, asset):
    row = kg.forecast_model(asset)
    if (row.get('asset'), row.get('model_id'), row.get('model_revision'), row.get('scope')) != (
            asset, MODEL_ID, MODEL_REVISION, MODEL_SCOPE):
        raise ValueError(f'지식 그래프에 {asset}의 설비 예측 모델 연결이 없거나 이 엔진의 모델({MODEL_ID} {MODEL_REVISION})과 다릅니다')
    number(row.get('horizon_s'), 'bound horizon_s', 0.001, 86400)
    return row


#: 설비 상태가 낡았거나 아직 없을 때 새 값을 다시 읽는 간격과 한도(벽시계 초 — 설비는 상태를 벽시계 1초마다 낸다. 배속과 무관하다).
#: 한도는 승인 검사를 부르는 process 의 기다림(current_approval 20초)과 재생 워커의 쓰기 도구 기다림(60초) 안에 든다.
SOURCE_REREAD_EVERY_S = 1.0
SOURCE_REREAD_FOR_S = 8.0
SOURCE_NAME = '설비 상태'
SOURCE_SYSTEM = '설비 상태 수집'


def _read_source(asset):
    """process 가 들고 있는 설비 최신 상태 한 번 읽기 → (상태, 나이 초). 아직 쓸 수 없는 까닭(곧 풀릴 수 있는 것: 닿지 못함 · 아직 없음 ·
    낡음)은 (None, 까닭 문장). 응답 자체가 틀린 것(다른 설비 · 시각 없음 · 앞선 시각)은 다시 읽어도 같으므로 바로 FactUnavailable."""
    from urllib.error import HTTPError

    def broken(reason):
        return decide.FactUnavailable('plant_status', SOURCE_NAME, SOURCE_SYSTEM, reason)
    try:
        snapshot = decide._get_json(f'{decide.PROCESS_URL}/api/plant/{quote(asset, safe="")}/status')
    except HTTPError as exc:
        if exc.code == 404:
            return None, f'{asset}의 설비 상태가 아직 들어오지 않았습니다'
        return None, f'설비 상태를 읽지 못했습니다(응답 {exc.code})'
    except OSError:
        return None, '설비 상태를 들고 있는 처리 서비스에 닿지 못했습니다'
    if not isinstance(snapshot, dict) or snapshot.get('asset') != asset:
        raise broken(f'설비 상태 응답이 {asset}의 것이 아닙니다')
    try:
        stamp = datetime.fromisoformat(str(snapshot.get('t') or '').replace('Z', '+00:00'))
    except ValueError:
        raise broken('설비 상태에 읽을 수 있는 관측 시각이 없습니다') from None
    if stamp.tzinfo is None:
        raise broken('설비 상태 관측 시각에 시간대가 없습니다')
    age = (datetime.now(timezone.utc) - stamp).total_seconds()
    if age < -2:
        raise broken(f'설비 상태의 관측 시각이 지금보다 {-age:.0f}초 앞서 있습니다')
    if age > decide.MAX_APPROVAL_FACT_AGE_S:
        return None, (f'설비 상태가 {age:.0f}초 전 값에서 새로 들어오지 않았습니다'
                      f'(예측에는 {decide.MAX_APPROVAL_FACT_AGE_S:g}초 이내 값만 씁니다)')
    return snapshot, age


def source(asset):
    """예측에 쓸 설비 상태(지금 값)와 그 출처. 낡았거나 아직 없으면 SOURCE_REREAD_FOR_S 동안 다시 읽고, 그래도 없으면 FactUnavailable 로
    멈춘다 — 낡은 값으로 예측하지 않고, 「예측을 확인할 수 없음」을 조치 안의 제외 사유로 굳히지도 않는다. 수집이 잠깐 밀린 한 번이 그 판단의
    모든 안을 제외로 저장해 값이 돌아온 뒤에도 승인할 수 없게 됐다(2026-11-14 01:01 처리 건). 문턱(MAX_APPROVAL_FACT_AGE_S)은 그대로다."""
    deadline = time.monotonic() + SOURCE_REREAD_FOR_S
    while True:
        snapshot, found = _read_source(asset)
        if snapshot is not None:
            return snapshot, {'source':'process plant.status', 'kind':'explicit simulator model state',
                              'asset':asset, 'observed_at':snapshot['t'], 'age_seconds':found}
        if time.monotonic() + SOURCE_REREAD_EVERY_S > deadline:
            raise decide.FactUnavailable('plant_status', SOURCE_NAME, SOURCE_SYSTEM,
                                         f'{found}. {SOURCE_REREAD_FOR_S:g}초 동안 다시 읽어도 같았습니다 — 잠시 뒤 다시 시도하세요')
        time.sleep(SOURCE_REREAD_EVERY_S)


#: 작업지시를 지금 시행하는 카드(cards.option_window 즉시)의 예측: 정비하는 동안 설비가 서 있다. 시스템이 PLC 에 정지 명령을 보내는
#: 것이 아니라(정지 · LOTO 는 정비 작업의 첫 단계) 예측 입력에만 쓰는 동작이다 — 카드의 actions(실행 · 승인 대상)에는 넣지 않는다.
WORK_ORDER_STOP = {'code': 'STOP', 'kind': 'command', 'name': '설비 정지(작업지시 즉시 시행)', 'basis': 'immediate_work_order'}


def plant_actions(skill, snapshot, stops_now=False):
    """예측에 넣는 동작: 카드의 원자 조치 + 지금 시행하는 작업지시면 운전 중인 설비의 정지(이미 STOP · TRIP 이면 더하지 않는다)."""
    actions = deepcopy(skill.get('actions') or [])
    if stops_now and snapshot.get('state') == 'RUN' and not any(a.get('code') == 'STOP' for a in actions):
        actions.append(dict(WORK_ORDER_STOP))
    return actions


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


def candidates(kg, asset, skills, stopping=frozenset()):
    """One bound model and one fresh snapshot for all candidates. Never use design constants.
    stopping: 지금 설비를 세우고 작업지시를 시행하는 카드 id(cards.option_window 가 즉시라고 정한 것) — 정지한 설비로 예측한다.
    설비 예측 모델 연결이 지식에 없는 것은 그 지식을 고칠 때까지 그대로인 사실이라 안마다 「예측을 확인할 수 없음」으로 싣는다. 설비 상태를
    받지 못한 것(source 의 FactUnavailable)은 곧 풀릴 수 있는 일이라 싣지 않고 그대로 올린다 — 부른 쪽(판단 · 승인 검사)이 그 까닭으로 멈춘다."""
    forecasts, contexts = {}, {}
    try:
        bound = binding(kg, asset)
    except ValueError as exc:
        return {}, {sid: {'error': str(exc)[:300], 'execution_authorized': False} for sid in skills}
    snapshot, provenance = source(asset)
    for sid, skill in skills.items():
        try:
            result = _predict(bound, snapshot, provenance, plant_actions(skill, snapshot, sid in stopping), bound['horizon_s'])
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
    wall = _elapsed_wall_s(old, current)
    age = wall
    if consented_at and wall is not None:
        # 예측 나이는 사람이 동의한 시각까지만 잰다 — 승인 뒤 전달까지의 몇 초가 승인을 뒤집지 않는다(지금보다 늦은 동의 시각은 지금으로).
        # 아래 악화 허용폭은 전달 시각까지의 경과로 그대로 잰다
        at_consent = _elapsed_wall_s(old, {'source_t': consented_at})
        if at_consent is not None:
            age = min(wall, at_consent)
    max_age = REVIEW_POLICY['max_review_age_wall_s']
    if age is not None and age > max_age:
        reasons.append(f'검토한 카드가 {age / 60:.0f}분 전 예측입니다(검토 뒤 {max_age // 60}분이 지났습니다): 새 카드 검토가 필요합니다')
    minutes = min((wall or 0.0) * scale, REVIEW_POLICY['max_budget_sim_s']) / 60
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
