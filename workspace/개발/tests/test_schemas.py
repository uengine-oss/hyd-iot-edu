"""명령 · 설비 기록의 계약(common/hydcommon/schemas.py) — 수집 · 감지 · 적재 · 관문이 같은 함수로 거른다(G3b-1 · 2 · 3 · 22 · 28 · 30).

규칙: 계약 밖 기록은 RecordError(칸 이름)로 거절하고 예외 종류가 섞이지 않는다(AttributeError · KeyError 없음). 명령은 매개변수까지
SCHEMA 에서 거른다(관문 쓰기 변환이 KeyError 로 기록 없이 사라지던 것). 승인 지문은 키 없이 계산하지 않는다.
"""
import pytest

from hydcommon import schemas

T = '2026-10-30T05:00:00.000Z'


@pytest.mark.parametrize('body, out_v', [
    ({'t': T, 'v': 48.2, 'q': 'good'}, 48.2),
    ({'t': '2026-10-30T14:00:00+09:00', 'v': 0}, 0.0),                     # 시간대 오프셋 · q 생략(good) · 0
])
def test_태그_기록은_알려진_설비_태그와_시간대_있는_시각_유한한_수만_받는다(body, out_v):
    r = schemas.tag_record('HYD-01', 'TS1', body)
    assert (r['asset'], r['name'], r['v'], r['t']) == ('HYD-01', 'TS1', out_v, body['t'])


@pytest.mark.parametrize('asset, name, body, field', [
    ('HYD-09', 'TS1', {'t': T, 'v': 1}, 'asset'),                     # 없는 설비
    ('HYD-01', 'XX9', {'t': T, 'v': 1}, 'tag'),                       # 없는 태그
    ('HYD-01', 'TS1', {'t': 1730000000, 'v': 1}, 't'),                # 숫자 시각(G3b-2 의 독 레코드)
    ('HYD-01', 'TS1', {'t': '2026-10-30T05:00:00', 'v': 1}, 't'),     # 시간대 없음
    ('HYD-01', 'TS1', {'t': 'yesterday', 'v': 1}, 't'),
    ('HYD-01', 'TS1', {'t': T, 'v': '48'}, 'v'),                      # 글자 값
    ('HYD-01', 'TS1', {'t': T, 'v': float('nan')}, 'v'),
    ('HYD-01', 'TS1', {'t': T, 'v': True}, 'v'),                      # bool 은 수가 아니다
    ('HYD-01', 'TS1', {'t': T, 'v': 1, 'q': 5}, 'q'),
    ('HYD-01', 'TS1', [1, 2], 'object'),
    ('HYD-01', 'TS1', {'_raw': 'x'}, 'object'),                       # kafka.decode_value 가 만든 깨진 글
])
def test_계약_밖_태그_기록은_그_칸을_말하며_거절한다(asset, name, body, field):
    with pytest.raises(schemas.RecordError) as caught:
        schemas.tag_record(asset, name, body)
    assert field in str(caught.value)


@pytest.mark.parametrize('body, ok', [
    ({'t0': T, 'hz': 10, 'v': [1.0] * 10}, True),
    ({'t0': T, 'hz': 10, 'v': [1.0]}, True),                          # 한 점도 파형이다
    ({'t0': T, 'hz': 10, 'v': []}, False),                            # 빈 파형
    ({'t0': T, 'hz': 10, 'v': [1.0] * 11}, False),                    # hz 보다 많은 점
    ({'t0': T, 'hz': 10, 'v': ['x']}, False),                         # G3b-3: 파형 값 하나로 감지가 멈췄다
    ({'t0': T, 'hz': 0, 'v': [1.0]}, False),
    ({'t0': T, 'hz': 2000, 'v': [1.0]}, False),
    ({'t0': T, 'hz': 10, 'v': 5}, False),
])
def test_파형_기록은_점_수와_값을_본다(body, ok):
    if ok:
        assert schemas.wave_record('HYD-02', 'PS1', body)['v'] == [float(x) for x in body['v']]
    else:
        with pytest.raises(schemas.RecordError):
            schemas.wave_record('HYD-02', 'PS1', body)


STATUS = {'t': T, 'mode': 'REMOTE_AUTO', 'state': 'RUN', 'trip': None, 'cmdId': None, 'result': None, 'reason': None, 'source': None}


@pytest.mark.parametrize('change, ok', [
    ({}, True),
    ({'asset': 'HYD-01'}, True),                                      # 실린 설비가 토픽과 같으면 됨
    ({'asset': 'HYD-02'}, False),                                     # G3b-28: 다른 설비 이름을 실은 상태
    ({'mode': 'AUTO'}, False),
    ({'state': 'RUNNING'}, False),
    ({'trip': ['OVERTEMP']}, False),                                  # G3b-3: 목록 trip 사유로 감지기가 멈췄다
    ({'cmdId': 5}, False),
    ({'t': None}, False),
])
def test_상태_기록의_설비는_토픽의_것이고_모드_상태_글칸을_본다(change, ok):
    body = dict(STATUS, **change)
    if ok:
        assert schemas.status_record('HYD-01', body)['asset'] == 'HYD-01'
    else:
        with pytest.raises(schemas.RecordError):
            schemas.status_record('HYD-01', body)


ALERT = {'alertId': 'ALT-hyd01-0001-ab12', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'name': '쿨러 성능 저하',
         'severity': 'HIGH', 'state': 'RAISE', 't': T, 'evidence': {}}


@pytest.mark.parametrize('change, ok', [
    ({}, True), ({'name': None}, True), ({'state': 'CLEAR'}, True),
    ({'state': 'CLEARED'}, False),                                    # G3b-23: RAISE 가 아니면 모두 CLEAR 로 적던 것
    ({'severity': 'WARNING'}, False), ({'alertId': ''}, False), ({'evidence': []}, False), ({'name': ''}, False),
])
def test_경보_기록은_상태_심각도_이름_칸을_본다(change, ok):
    body = dict(ALERT, **change)
    if ok:
        assert schemas.alert_record(body) == body
    else:
        with pytest.raises(schemas.RecordError):
            schemas.alert_record(body)


@pytest.mark.parametrize('body, ok', [
    ({'t': T, 'asset': 'HYD-01', 'sensor': 'TS1', 'mean': 1, 'rms': None, 'slope': 0.1, 'score': None}, True),
    ({'t': T, 'asset': 'HYD-01', 'sensor': 'TS1', 'mean': float('inf')}, False),
    ({'t': T, 'asset': 'HYD-01', 'sensor': 'NOPE', 'mean': 1}, False),
])
def test_특징_기록의_수는_유한하거나_비어_있다(body, ok):
    if ok:
        assert schemas.feat_record(body)['mean'] == 1.0
    else:
        with pytest.raises(schemas.RecordError):
            schemas.feat_record(body)


@pytest.mark.parametrize('body, ok', [
    ({'t': T, 'actor': 'process', 'event': 'X', 'detail': {}, 'incident': None}, True),
    ({'t': T, 'actor': '', 'event': 'X'}, False), ({'t': T, 'actor': 'a', 'event': 'X', 'detail': 'x'}, False),
    ({'t': T, 'actor': 'a', 'event': 'X', 'incident': 3}, False), ({'actor': 'a', 'event': 'X'}, False),
])
def test_감사_기록은_주체_사건_시각을_본다(body, ok):
    if ok:
        assert schemas.audit_record(body)['actor'] == 'process'
    else:
        with pytest.raises(schemas.RecordError):
            schemas.audit_record(body)


CMD = {'cmdId': 'CMD-1', 'asset': 'HYD-01', 'incident': 'INC-1', 'source': 'HITL', 'approvedBy': 'user:kim-op',
       'expiresAt': T, 'approvalId': 'APR-1', 'actions': [{'code': 'FAN_SET', 'fan_pct': 100}]}


@pytest.mark.parametrize('change, problem', [
    ({}, None),
    ({'actions': [{'code': 'RESET'}, {'code': 'PUMP_SELECT', 'pump': 'B'}]}, None),
    ({'actions': [{'code': 'FAN_SET'}]}, 'needs parameter fan_pct'),           # G3b-22: 관문이 KeyError 로 삼켰다
    ({'actions': [{'code': 'FAN_SET', 'fan_pct': 'abc'}]}, 'finite number'),
    ({'actions': [{'code': 'PUMP_SELECT', 'pump': 'C'}]}, 'pump must be'),
    ({'actions': [{'code': 'LOAD_SET', 'load_pct': True}]}, 'finite number'),
    ({'asset': 'HYD-7'}, 'asset must be'),
    ({'cmdId': ''}, 'cmdId'),
    ({'expiresAt': 5}, 'expiresAt'),
    ({'actions': []}, 'non-empty'),
    ({'source': 'FUXA'}, 'source must be HITL'),
])
def test_명령_형식_검사는_매개변수까지_본다(change, problem):
    errs = schemas.validate_action_cmd(dict(CMD, **change))
    assert (errs == []) if problem is None else any(problem in e for e in errs), errs


def test_옛_조치_이름은_허용되지_않는다():
    assert schemas.ACTION_WHITELIST == {'FAN_SET', 'LOAD_SET', 'RESET', 'PUMP_SELECT', 'STOP'}


def test_쓰기_변환은_조치를_PLC_자원과_값으로_바꾼다():
    writes = schemas.actions_to_writes([{'code': 'PUMP_SELECT', 'pump': 'B'}, {'code': 'RESET'}, {'code': 'LOAD_SET', 'load_pct': 80}])
    assert writes == [{'res': 'PumpSelect', 'v': 1}, {'res': 'Reset', 'v': 1}, {'res': 'LoadSP', 'v': 80}]


def test_승인_지문은_키와_승인한_칸으로_바뀌고_키가_없으면_계산하지_않는다():
    base = schemas.cmd_fingerprint(CMD, 'k1')
    assert base == schemas.cmd_fingerprint(dict(CMD), 'k1')
    assert base != schemas.cmd_fingerprint(CMD, 'k2')
    assert base != schemas.cmd_fingerprint(dict(CMD, actions=[{'code': 'FAN_SET', 'fan_pct': 99}]), 'k1')
    with pytest.raises(ValueError, match='CMD_FINGERPRINT_KEY'):
        schemas.fingerprint_key({})
    assert schemas.approval_ledger_record(CMD, 'k1')['fingerprint'] == base
