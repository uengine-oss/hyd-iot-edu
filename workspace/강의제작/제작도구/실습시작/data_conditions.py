"""냉각 경보 조치 판단 랩의 원자료 묶음 생성(교육용 가상 자료, 고정 시드).

실전 2-5 조건표, 통합 3-2 SOP·결정표, 통합 3-3 판정 기능, 실전 3-2 조치 검토 결과가 같은 묶음을 쓴다.
값은 저장소 시뮬레이터의 실제 코드를 import해 만든다.
- 열·압력: ot/plant-sim/plantsim/thermal.py (step, 고장 강도), plc.py (check_interlock 65 ℃ 초과 트립)
- 조치 후 예측: common/hydcommon/forecast.py predict (외란 변화 중 거부, 트립 중 RESET 없는 제어 거부, 작업지시는 물리 효과 없음)
- 수신 주기·유예: common/hydcommon/daq_contract.py, it/detector/det/observations.py (PLC_STATE 10 s + 유예 2 s)
규칙 원문은 it/neo4j/v2/instances.cypher의 줄을 그대로 옮기고, 문서 원문은 it/portal/www/samples/에서 읽는다.

사용: from data_conditions import build; files, events = build()
files: {파일 이름: 텍스트}, events: 강사용 사례 메타(범주·설계 의도). 학생 폴더에는 files만 쓴다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
import copy
import csv
import io
import json
import math
import random
import sys
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
for extra in [ROOT/'ot/plant-sim', ROOT/'common']:
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))
from plantsim import thermal, plc  # noqa: E402
from hydcommon import forecast, daq_contract  # noqa: E402

SEED = 20261028
KST = timezone(timedelta(hours=9))
HORIZON_S = 900                      # HM-8.6 15분 재관측
FORECAST_VALID_S = 120               # 예측 서비스 설정: 기준 관측 뒤 120초까지 유효
STATUS_PERIOD_S = daq_contract.reporting_interval('PLC_STATE')   # 10 s
GRACE_S = 2.0                        # it/detector/det/observations.py Observations(grace_s=2.)
COUNTER_PERIOD_MIN = 10
COUNTER_LIMIT_MIN = 12
WINDOW_S = 180                       # PLC 상태 추출 구간: 판단 시각 전 3분
MPA_UNTIL = datetime(2026, 10, 10, tzinfo=KST)   # HYD-03 옛 예측 내보내기(MPa) 사용 기간
SOPS = ['SOP-COOL-11', 'SOP-COOL-12', 'SOP-COOL-13', 'SOP-COOL-14']
ACTIONS = {
    'SOP-COOL-11': [{'kind': 'command', 'code': 'FAN_SET', 'value': 100.0}],
    'SOP-COOL-12': [{'kind': 'command', 'code': 'FAN_SET', 'value': 100.0}, {'kind': 'command', 'code': 'LOAD_SET', 'value': 80.0}],
    'SOP-COOL-13': [{'kind': 'command', 'code': 'LOAD_SET', 'value': 70.0}, {'kind': 'workorder', 'code': 'WO_CREATE'}],
    'SOP-COOL-14': [{'kind': 'workorder', 'code': 'WO_CREATE'}],
}
REFUSAL = {
    'constant-input forecast requires confirmed stationary disturbances': '외란 변화 중(정상 상태 확인 전)이라 예측하지 않음',
    'PLC TRIP requires an explicit eligible RESET': 'PLC 트립 중이라 RESET 없는 제어 조치는 예측하지 않음',
}
NOTICE = '교육용 가상 자료: 공개 현업 문제 유형과 수업용 시뮬레이터(ot/plant-sim) 로직으로 생성했다. 실제 설비 기록이 아니다.'


@dataclass
class Spec:
    tag: str                     # 강사용 범주
    asset: str
    health: float = 0.55
    ramp_s: float = 300.0
    leak: float = 0.0
    t_amb: float = 26.0
    fan0: float = 60.0
    load0: float = 90.0
    delay_s: int = 90            # 경보(또는 트립) 뒤 판단까지
    trip: bool = False
    fan_run_min: float | None = None   # 판단 시각에 팬 100 %가 이어진 시간(분). None = 팬 100 % 아님
    counter_gap_min: float | None = None   # 카운터 주기 기록이 끊긴 시간
    mode: str = 'REMOTE_AUTO'
    mode_change_s: int | None = None   # 판단 전 몇 초에 REMOTE_MANUAL로 바뀌었나
    status_gap_s: int | None = None    # 판단 전 마지막 PLC 상태 수신 뒤 끊긴 시간
    bad_last: bool = False
    lag_s: int | None = None           # 판단 시각 - 예측 기준 관측 시각
    drop: list = field(default_factory=list)   # 수신 실패한 예측 행
    order_missing: bool = False
    target: tuple | None = None        # (sop, 'ts1', 값): 경계 맞추기
    post_run_h: float | None = None    # 판단 뒤 팬 100 % 운전(조치 모사) 시간
    order: tuple | None = None         # (납기까지_남은_시간_h, 오더_잔량_ea) 고정: 판단 결정이 추천을 바꾸는 사례
    note: str = ''


def specs():
    """48건. 범주는 강사 참조용이며 학생 자료에는 나가지 않는다."""
    rnd = random.Random(SEED)
    s = []
    hot = [24.0, 26.5, 28.0, 30.5, 32.0, 33.5, 25.0, 27.0, 29.5, 31.0, 34.0, 26.0, 28.5]
    healths = [0.50, 0.52, 0.55, 0.55, 0.58, 0.48, 0.53, 0.56, 0.51, 0.54, 0.57, 0.49, 0.55]
    for i in range(13):
        s.append(Spec('정상·일반', '', health=healths[i], t_amb=hot[i], delay_s=rnd.randint(40, 240)))
    for v in [54.99, 55.00, 55.01]:
        s.append(Spec('경계·예측 유온 55', '', health=0.55, t_amb=29.0, target=('SOP-COOL-11', 'ts1', v)))
    for num in [17.01, 17.0, 16.99]:
        s.append(Spec('경계·예측 압력 165', '', health=0.55, leak=num/130, t_amb=27.0))
    s.append(Spec('단위·MPa', 'HYD-03', health=0.55, leak=17.0/130, t_amb=25.5))
    s.append(Spec('단위·MPa', 'HYD-03', health=0.52, t_amb=27.5))
    s.append(Spec('단위·MPa', 'HYD-03', health=0.57, t_amb=24.5))
    # 1443.5분 사례는 납기가 먼 대형 오더(246 h, 21000 ea): 팬 최대 운전의 고장 위험이 쌓여 핀 세척과 합계 차이가 감점 20보다 작다.
    # → 카운터 기록값/경과 더함 결정이 감점뿐 아니라 1위 추천(SOP-COOL-11 ↔ SOP-COOL-14)을 바꾼다(리허설 2 통합 3-3 제안 1).
    for run, gap, note, order in [(1443.5, None, '기록 1440분, 경과 더하면 24 h 초과. 납기 먼 대형 오더라 추천이 갈림', (246.0, 21000)), (1437.0, None, '둘 다 24 h 이하', None),
                                  (1452.0, None, '둘 다 24 h 초과', None), (1441.0, None, '기록 1440분, 경과 더하면 24 h 초과', None), (900.0, 25.0, '카운터 주기 기록 끊김', None)]:
        s.append(Spec('팬 카운터', '', health=0.35, fan0=100.0, t_amb=28.0, fan_run_min=run, counter_gap_min=gap, note=note, order=order))
    s.append(Spec('모드·수동', '', mode_change_s=75, t_amb=27.0))
    s.append(Spec('모드·수동', '', mode_change_s=140, t_amb=29.0, health=0.52))
    s.append(Spec('모드·현장', '', mode='LOCAL', t_amb=26.0))
    for d in [60, 90, 150]:
        s.append(Spec('트립', '', health=thermal.DEGRADED_HEALTH, trip=True, delay_s=d, t_amb=27.0))
    s.append(Spec('심한 오염·예측 65', '', health=thermal.DEGRADED_HEALTH, target=('SOP-COOL-14', 'ts1', 65.0), t_amb=26.0))
    s.append(Spec('심한 오염·예측 65', '', health=thermal.DEGRADED_HEALTH, target=('SOP-COOL-14', 'ts1', 65.4), t_amb=27.0))
    s.append(Spec('PLC 수신 끊김', '', status_gap_s=45))
    s.append(Spec('PLC 수신 끊김', '', status_gap_s=95, t_amb=30.0))
    s.append(Spec('PLC 품질 불량', '', bad_last=True, t_amb=28.0))
    s.append(Spec('예측 거부·외란 변화', '', health=0.45, ramp_s=3600.0, delay_s=60))
    s.append(Spec('예측 거부·외란 변화', '', health=0.47, ramp_s=4200.0, delay_s=45, t_amb=29.0))
    s.append(Spec('예측 수신 실패', '', drop=['SOP-COOL-12'], t_amb=30.0))
    s.append(Spec('예측 수신 실패', '', drop=['SOP-COOL-13'], t_amb=27.5))
    s.append(Spec('예측 오래됨', '', lag_s=180, t_amb=31.5))
    s.append(Spec('예측 오래됨', '', lag_s=300, t_amb=26.0))
    s.append(Spec('수동+예측 수신 실패', '', mode_change_s=60, drop=['SOP-COOL-11'], t_amb=32.0))
    s.append(Spec('오더 조회 실패', '', order_missing=True, t_amb=28.0))
    s.append(Spec('재경보·조치 중', '', health=0.25, fan0=100.0, load0=80.0, fan_run_min=300.0, t_amb=29.0))
    s.append(Spec('재경보·조치 중', '', health=0.25, fan0=100.0, load0=80.0, fan_run_min=600.0, t_amb=31.0))
    assert len(s) == 48, len(s)
    # 설비 배정: MPa 3건은 HYD-03의 첫 사례, 나머지는 섞어서 돌아가며
    order = [x for x in s if x.asset != 'HYD-03']
    rnd.shuffle(order)
    assets = ['HYD-01', 'HYD-02', 'HYD-03']
    counts = {'HYD-01': 0, 'HYD-02': 0, 'HYD-03': 3}
    for x in order:
        a = min(assets, key=lambda k: (counts[k], k))
        x.asset = a
        counts[a] += 1
    for x in s:
        if x.lag_s is None:
            x.lag_s = rnd.randint(12, 55)
        if x.post_run_h is None and not x.trip and x.mode == 'REMOTE_AUTO' and x.mode_change_s is None:
            x.post_run_h = round(rnd.uniform(1.5, 7.0), 2)
    return s


def simulate(spec, delay_override=None):
    """경보(또는 트립)까지 1초씩 진행. 판단 시각 T와 그 앞 상태 기록을 돌려준다."""
    delay = spec.delay_s if delay_override is None else delay_override
    st = thermal.UnitState()
    st.rng.seed(zlib.crc32(repr((spec.asset, spec.health, spec.t_amb, spec.leak, spec.tag)).encode()))
    st.t_amb, st.fan_pct, st.load_pct, st.leak = spec.t_amb, spec.fan0, spec.load0, spec.leak
    st.ts1 = thermal.equilibrium_ts1(spec.load0, spec.fan0, 1.0, spec.t_amb) if spec.leak == 0 else spec.t_amb + (thermal.K_HEAT + thermal.K_LEAK * spec.leak) * (spec.load0/100)**2 / (thermal.K_BASE + thermal.K_COOL*spec.fan0/100)
    ctrl = plc.PlcState()
    hist, t, alarm, trip_t, prev = [], 0, None, None, st.ts1
    rate = (spec.health - 1.0) / spec.ramp_s
    while True:
        t += 1
        if t <= spec.ramp_s:
            st.cooler_health = 1.0 + rate * t
        thermal.step(st, 1.0, running=(ctrl.state == 'RUN'))
        plc.check_interlock(ctrl, st)
        if trip_t is None and ctrl.state == 'TRIP':
            trip_t = t
        hist.append({'t': t, 'ts1': st.ts1, 'ce': st.ce, 'health': st.cooler_health, 'state': ctrl.state, 'ramping': t < spec.ramp_s})
        if alarm is None and st.ts1 > 55 and st.ts1 > prev and st.ce < 70:
            alarm = t
        prev = st.ts1
        anchor = trip_t if spec.trip else alarm
        if anchor is not None and t >= anchor + delay:
            return {'T': t, 'alarm': alarm, 'trip': trip_t, 'hist': hist, 'final': copy.deepcopy(st)}
        if t > 20000:
            raise RuntimeError(f'경보가 나지 않음: {spec}')


def predict(spec, h, base_t, sop):
    rec = h['hist'][base_t - 1]
    snap = {'forecast_model': forecast.MODEL_ID, 'disturbance_ramps': ['cooler_health'] if rec['ramping'] else [], 'asset': spec.asset,
            't': '2026-10-01T00:00:00+09:00', 'state': rec['state'], 'pump': 'A', 'ts1': rec['ts1'], 't_amb': spec.t_amb,
            'fan_pct': spec.fan0, 'load_pct': spec.load0, 'cooler_health': rec['health'], 'leak': spec.leak, 'bearing_wear': 0.0}
    try:
        out = forecast.predict(snap, ACTIONS[sop], HORIZON_S)
    except ValueError as e:
        if str(e) not in REFUSAL:
            raise
        return None, REFUSAL[str(e)]
    return out['values'], None


def solve(spec):
    """판단 시각을 정한다. 외란 거부를 의도하지 않은 사례는 예측 기준 관측이 외란 변화 뒤가 되게 판단 지연을 늘린다.
    경계 사례는 판단 지연을 바꿔 가며 목표 예측값(소수 둘째 자리)을 맞춘다."""
    if spec.target is None:
        h = simulate(spec)
        if not spec.tag.startswith('예측 거부'):
            while h['hist'][h['T'] - spec.lag_s - 1]['ramping']:
                spec.delay_s += 30
                h = simulate(spec)
        else:
            assert h['hist'][h['T'] - spec.lag_s - 1]['ramping'], spec
        return h
    sop, _, value = spec.target
    for d in range(10, 2400):
        h = simulate(spec, d)
        base = h['T'] - spec.lag_s
        v, why = predict(spec, h, base, sop)
        if v is not None and round(v['ts1'], 2) == value and (h['trip'] is None or h['trip'] > h['T']):
            spec.delay_s = d
            return h
        if spec.trip is False and h['trip'] is not None and h['trip'] <= h['T']:
            break
    for health in [x / 1000 for x in range(400, 700)]:
        spec.health = health
        h = simulate(spec)
        base = h['T'] - spec.lag_s
        v, _ = predict(spec, h, base, sop)
        if v is not None and round(v['ts1'], 2) == value:
            return h
    raise RuntimeError(f'경계 값 {value}을 맞추지 못함: {spec}')


def iso(dt):
    return dt.astimezone(KST).isoformat(timespec='seconds')


def table(header, rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def fmt(v, nd=2):
    return '' if v is None else f'{round(v, nd):.{nd}f}'


def build():
    rnd = random.Random(SEED + 1)
    all_specs = specs()
    sims = [solve(x) for x in all_specs]
    # 일정: 설비별로 차례대로, 앞 사례의 팬 운전이 끝난 뒤 다음 팬 운전·사례가 오게
    clock = {a: datetime(2026, 9, 21, 7, 0, tzinfo=KST) + timedelta(hours=rnd.uniform(0, 10)) for a in ['HYD-01', 'HYD-02', 'HYD-03']}
    events, runs = [], {a: [] for a in clock}
    by_asset = {a: [i for i, x in enumerate(all_specs) if x.asset == a] for a in clock}
    for a, idx in by_asset.items():
        idx.sort(key=lambda i: (0 if all_specs[i].tag == '단위·MPa' else 1, i))
        if a != 'HYD-03':
            rnd.shuffle(idx)
        for i in idx:
            x = all_specs[i]
            pre = timedelta(minutes=x.fan_run_min or 0)
            T = clock[a] + pre + timedelta(hours=rnd.uniform(6, 30))
            T = T.replace(microsecond=0)
            if x.tag == '단위·MPa':
                assert T < MPA_UNTIL, (a, T)
            end = None
            if x.fan_run_min:
                start = T - timedelta(minutes=x.fan_run_min)
                end = T + timedelta(hours=rnd.uniform(1, 4))
                runs[a].append((start, end, x.counter_gap_min, T))
            elif x.post_run_h:
                start = T + timedelta(minutes=rnd.randint(3, 9))
                end = start + timedelta(hours=x.post_run_h)
                runs[a].append((start, end, None, None))
            clock[a] = (end or T) + timedelta(hours=1)
            events.append((T, i))
    events.sort()
    alarm_rows, status_rows, forecast_rows, order_rows, meta = [], [], [], [], []
    for n, (T, i) in enumerate(events, 1):
        x, h = all_specs[i], sims[i]
        eid = f'E{n:02d}'
        t0 = T - timedelta(seconds=h['T'])           # 시뮬레이션 0초의 시각
        alarm_at = t0 + timedelta(seconds=h['alarm'])
        ar = h['hist'][h['alarm'] - 1]
        alarm_rows.append([eid, x.asset, iso(alarm_at), iso(T), 'COOLER_DEGRADATION', fmt(ar['ts1']), fmt(ar['ce'], 1), ';'.join(SOPS)])
        # PLC 상태 수신(10 s 하트비트 + 바뀔 때 즉시)
        phase = rnd.randint(0, 9)
        times = list(range(-WINDOW_S + phase, 1, int(STATUS_PERIOD_S)))
        changes = []
        if x.mode_change_s:
            changes.append(-x.mode_change_s)
        if h['trip'] is not None and h['trip'] - h['T'] > -WINDOW_S:
            changes.append(h['trip'] - h['T'])
        rows = sorted(set(times + changes))
        if x.status_gap_s:
            rows = [r for r in rows if r <= -x.status_gap_s]
        dup = rnd.random() < 0.15
        for k, r in enumerate(rows):
            sim_t = h['T'] + r
            state = h['hist'][sim_t - 1]['state']
            mode = x.mode
            if x.mode_change_s and r >= -x.mode_change_s:
                mode = 'REMOTE_MANUAL'
            trip = 'OVERTEMP' if state == 'TRIP' else ''
            q = 'bad' if (x.bad_last and k == len(rows) - 1) else 'good'
            row = [x.asset, iso(T + timedelta(seconds=r)), mode if q == 'good' else '', state if q == 'good' else '', trip if q == 'good' else '', fmt(x.fan0, 0) if q == 'good' else '', fmt(x.load0, 0) if q == 'good' else '', q]
            status_rows.append(row)
            if dup and k == len(rows) // 2:
                status_rows.append(list(row))
        # 예측 결과(후보별)
        lag = x.lag_s
        base_t = h['T'] - lag
        out_v = {}
        for sop in SOPS:
            v, why = predict(x, h, base_t, sop)
            out_v[sop] = (v, why)
            if sop in x.drop:
                continue
            made = T - timedelta(seconds=lag - rnd.randint(3, 8))
            unit = 'MPa' if (x.asset == 'HYD-03' and T < MPA_UNTIL) else 'bar'
            ps1 = None if v is None else (v['ps1'] / 10 if unit == 'MPa' else v['ps1'])
            forecast_rows.append([eid, sop, iso(made), iso(T - timedelta(seconds=lag)), '거부' if v is None else '완료', why or '',
                                  fmt(None if v is None else v['ts1']), '' if ps1 is None else (f'{ps1:.3f}' if unit == 'MPa' else fmt(ps1)), unit, forecast.MODEL_ID, f'{HORIZON_S//60}'])
        # 오더(MES/QMS 조회)
        due = round(rnd.uniform(3.0, 30.0), 1)
        remain = rnd.randrange(300, 3001, 50)
        lot = rnd.choice([0, 0, 200, 400, 600, 800, 1200])
        if x.order:
            due, remain = x.order       # 난수는 그대로 소비해 다른 사례의 값은 바뀌지 않는다
        order_rows.append([eid, f'MO-{T:%m%d}-{rnd.randint(100, 999):03d}', iso(T - timedelta(seconds=rnd.randint(5, 40))), '' if x.order_missing else f'{due:.1f}', '' if x.order_missing else remain, '' if x.order_missing else lot, '조회 실패(MES 응답 없음)' if x.order_missing else ''])
        meta.append({'id': eid, 'asset': x.asset, '판단_시각': iso(T), '범주': x.tag, '메모': x.note, 'lag_s': lag,
                     'forecast_ts1': {k: (None if v is None else round(v['ts1'], 2)) for k, (v, _) in out_v.items()}, 'fan_run_min': x.fan_run_min})
    # 팬 카운터: 시작(0) · 10분 주기 · 종료(0). 끊김이 있으면 그 구간의 주기 기록이 없다.
    counter_rows = [[a, iso(datetime(2026, 9, 21, 0, 0, tzinfo=KST)), 0, '종료'] for a in sorted(runs)]
    for a, rs in runs.items():
        for start, end, gap, T in sorted(rs, key=lambda r: r[0]):
            counter_rows.append([a, iso(start), 0, '시작'])
            k = 1
            while start + timedelta(minutes=COUNTER_PERIOD_MIN * k) < end:
                at = start + timedelta(minutes=COUNTER_PERIOD_MIN * k)
                if not (gap and T and T - timedelta(minutes=gap) < at <= T + timedelta(minutes=30)):
                    counter_rows.append([a, iso(at), COUNTER_PERIOD_MIN * k, '주기'])
                k += 1
            counter_rows.append([a, iso(end), 0, '종료'])
    counter_rows.sort(key=lambda r: (r[1], r[0]))
    status_rows.sort(key=lambda r: (r[1], r[0]))
    files = {
        '경보_목록.csv': table(['사례', '설비', '경보_시각', '판단_시각', '경보', 'TS1_경보시_C', 'CE_경보시_pct', '후보'], alarm_rows),
        'PLC_상태_수신.csv': table(['설비', '수신_시각', '운전_모드', '상태', '트립', '팬_설정_pct', '부하_설정_pct', '품질'], status_rows),
        '팬_운전_카운터.csv': table(['설비', '기록_시각', '팬100_연속_분', '기록_종류'], counter_rows),
        '예측_결과.csv': table(['사례', '후보', '예측_시각', '기준_관측_시각', '상태', '거부_사유', '예측_TS1_C', '예측_PS1', 'PS1_단위', '모델', '예측_구간_분'], forecast_rows),
        '오더_현황.csv': table(['사례', '생산_오더', '조회_시각', '납기까지_남은_시간_h', '오더_잔량_ea', '고온_로트_수량_ea', '비고'], order_rows),
    }
    files.update(documents())
    files['지표_정의.md'] = metric_doc(files)
    return files, meta


# ───────────── 문서 ─────────────

def rule_excerpt():
    lines = (ROOT/'it/neo4j/v2/instances.cypher').read_text(encoding='utf-8').splitlines()
    want = ['rule:ts1-hard', 'rule:avl', 'rule:cand-cooler', 'rule:no-pressure-raise', 'rule:auto-mode', 'rule:standby', 'rule:ts1-warn', 'rule:ps1-warn', 'rule:fan-24h', 'rule:trip-reset-only']
    header = next((i for i, l in enumerate(lines) if l.startswith('// [id, table, order, when, effect')), None)
    if header is None:
        raise RuntimeError('instances.cypher 규칙 열 설명 줄을 찾지 못함')
    out = ['// ' + NOTICE.replace('생성했다', '정리했다').split(':')[0] + ': 수업용 시드(it/neo4j/v2/instances.cypher)에서 쿨러 조치 판단과 관련된 결정표 행을 그대로 옮겼다. 같은 표에 있는 다른 후보용 규칙도 함께 실었다.',
           f'// instances.cypher:{header + 1}', lines[header], '']
    for rid in want:
        at = next((i for i, l in enumerate(lines) if l.strip().startswith(f"['{rid}'")), None)
        if at is None or not lines[at + 1].strip().startswith('[['):
            raise RuntimeError(f'instances.cypher에서 {rid} 행을 찾지 못함')
        out += [f'// instances.cypher:{at + 1}', lines[at], lines[at + 1].rstrip(','), '']
    return '\n'.join(out)


def documents():
    src = ROOT/'it/portal/www/samples'
    hm8 = (src/'HM-8_cooler-fan-manual.md').read_text(encoding='utf-8-sig')
    hi01 = (src/'HI-01_shift-inspection-supplement.md').read_text(encoding='utf-8-sig')
    for need in ['### SOP-COOL-11', '### SOP-COOL-14', '## HM-8.8']:
        if need not in hm8:
            raise RuntimeError(f'HM-8 원문에 {need} 없음')
    if '### SOP-HI-01' not in hi01:
        raise RuntimeError('HI-01 원문에 SOP-HI-01 없음')
    return {
        'HM-8_매뉴얼.md': hm8,
        'HI-01_보충매뉴얼.md': hi01,
        '규칙_원문.txt': rule_excerpt(),
        '작업기준.md': WORK_STANDARD,
        '수집_설명.md': COLLECTION,
        'targets.csv': 'sop_id,reference_skill_id,name,kind,codes,source_section\nSOP-COOL-11,skill:fan-max,팬 최대 운전,control,FAN_SET,HM-8.5\nSOP-COOL-12,,팬 최대 운전과 부하 80 %,control,FAN_SET;LOAD_SET,HM-8.5\nSOP-COOL-13,,부하 70 %와 야간 핀 세척,control,LOAD_SET;WO_CREATE,HM-8.5\nSOP-COOL-14,,쿨러 핀 세척,workorder,WO_CREATE,HM-8.7\n',
        'failuremodes.csv': 'reference_id,name,component,symptoms,source_section\nfm:cooler-performance-loss,쿨러 냉각 성능 상실,오일 쿨러,유온 상승;냉각 효율 저하,HM-8.4\n',
        '후보_설정.csv': '후보,이름,팬_설정_퍼센트,부하_설정_퍼센트,작업지시,근본_조치,승인\nSOP-COOL-11,팬 최대 운전,100,,,아니오,운전원\nSOP-COOL-12,팬 최대 운전과 부하 80 %,100,80,,아니오,운전원\nSOP-COOL-13,부하 70 %와 야간 핀 세척,,70,쿨러 핀 세척,예,운전원\nSOP-COOL-14,쿨러 핀 세척,,,쿨러 핀 세척,예,설비보전팀장\n',
        '업무_값.json': json.dumps(BUSINESS, ensure_ascii=False, indent=2) + '\n',
    }


WORK_STANDARD = f'''# 냉각 경보 조치 판단 — 작업 기준

{NOTICE}

대상은 HYD-01~03(같은 모델)의 쿨러 냉각 성능 상실 경보(COOLER_DEGRADATION)에서 검토하는 조치 후보 네 개다(`targets.csv`). 실제 설비 조작과 평가 함수 실행은 하지 않는다.

## 1. 자료의 역할

- `HM-8_매뉴얼.md`: 조치의 원문(SOP 단계·완료 조건·금지와 제한·승인).
- `규칙_원문.txt`: 수업용 시드 결정표에서 옮긴 구조화 규칙. 열의 뜻은 파일 첫머리의 설명 줄을 따른다. 규칙에 적힌 출처 식별자(HM-3.2, HM-7.5, ks:sr-04 등)는 시드 판본의 식별자다. 첨부 HM-8의 절 번호와 같다고 바꾸지 않는다. 시드의 스킬 ID와 이번 후보 SOP ID의 대응은 원자료에서 근거를 찾아 쓰고, 근거 없이 이름만 보고 잇지 않는다.
- `HI-01_보충매뉴얼.md`: 관측값의 시각·조회 실패를 다루는 보충 기준.
- `수집_설명.md`: 판단 입력이 오는 원천(PLC 상태, 팬 운전 카운터, 예측 결과, 오더)의 수집 방식·단위·주기.

## 2. 조건을 옮길 때

- 원문의 「이상·초과·미만·이하」를 그대로 옮긴다. 같은 내용을 원문끼리 다르게 적었으면 둘 다 적고 어느 쪽을 따랐는지 검토 기록에 남긴다.
- 규칙의 적용 대상이 비어 있거나, 규칙의 식과 설명 문장이 서로 다른 범위를 말하면 한쪽으로 조용히 정하지 않는다. 정한 해석과 그 근거(파일·절·문장)를 검토 기록에 남긴다.
- 원문에 없는 기준값·단계를 만들지 않는다.

## 3. 판단 입력

- 입력은 경보 목록의 판단 시각을 기준으로 원천 자료에서 만든다. 판단 시각 뒤에 들어온 기록은 쓰지 않는다.
- 단위가 다른 원천은 규칙의 단위로 환산한다. 비교는 환산한 원값으로 하고, 반올림은 표시할 때만 한다.
- 값이 없거나 확인이 필요한 입력은 0이나 정상값으로 채우지 않는다. 왜 없는지(원천·시각)를 함께 남긴다.
- 입력을 어느 파일의 어느 기록에서 어떻게 만들었는지 다른 사람이 다시 따라갈 수 있게 기록한다.

## 4. 결과 수집과 미확인

맞는 경고·감점·제외를 모두 모은다. 제외가 있으면 후보에서 빼고, 없으면 후보를 유지하되 경고·감점과 수행 조건을 함께 남긴다. 같은 규칙의 감점은 한 번만 반영한다.

이 회사의 검토 기록에서는 입력이 빠져 참·거짓을 알 수 없는 규칙을 미확인으로 표시한다. 알려진 제외 사유가 있으면 제외하면서 미확인도 남기고, 제외가 없더라도 필요한 입력이 빠졌으면 최종 허용 판단은 보류한다. 이는 검토 절차이며 HYD 함수의 누락값 처리를 실행해 검증한 결과가 아니다.

## 5. 후보 유지와 실행

후보 유지는 실행 허가가 아니다. 원문 SOP의 시간 제한·승인·수행 시점 재확인을 지운 채 감점만으로 작업을 허가하지 않는다. 핀 세척은 HM-8.7의 정지·LOCAL·잠금·현장 승인·세척·재가동 확인 절차를 따른다. 원격 조치가 제외돼도 현장 작업이 자동 허용되지 않는다.
'''

COLLECTION = f'''# 판단 입력 원천과 수집 방식

{NOTICE}

모든 시각은 한국 표준시(+09:00)다. 판단 시각은 `경보_목록.csv`의 `판단_시각`이다.

## 경보_목록.csv

경보 한 건이 한 행이다(사례 E01~E48). `후보`는 그 경보에서 검토할 SOP ID 목록(`;`로 구분)이다. `TS1_경보시_C`·`CE_경보시_pct`는 경보가 난 때의 관측값이며 판정 입력이 아니다.

## PLC_상태_수신.csv — 운전 모드·상태

- 판단 시각 전 3분 구간을 사례마다 추출했다. 엣지 게이트웨이가 10초마다(하트비트) 보내고, 모드·상태가 바뀌면 바로 한 번 더 보낸다.
- 판정 서버의 수신 감시는 마지막 수신 뒤 **12초**(하트비트 10초 + 유예 2초)가 지나면 그 원천을 끊긴 것으로 본다.
- `품질`이 `bad`인 행은 값이 비어 있고 쓸 수 없는 수신이다. 판정 서버는 이때 그 앞의 정상 수신으로 대신하지 않는다.
- 같은 시각·같은 내용의 행이 두 번 있는 것은 재전송이다.
- `상태`: `RUN`(운전), `TRIP`(인터록 정지). `트립`: 트립 원인. `팬_설정_pct`·`부하_설정_pct`: 그때의 설정값.

## 팬_운전_카운터.csv — 팬 100 % 연속 운전 시간

- PLC의 카운터를 **분 단위 정수**로 기록한다. 팬이 100 %가 되면 `시작`(0분), 100 %인 동안 10분마다 `주기`(누적 분), 100 %에서 내려오면 `종료`(0분)를 남긴다.
- 내보내기 첫 행(2026-09-21 00:00)은 그때의 카운터 상태다(`종료` = 팬 100 % 아님).
- 기록은 이 세 경우에만 생긴다. `종료` 뒤 다음 `시작`까지 기록이 없는 것은 정상이다(팬이 100 %가 아님).
- `시작`·`주기` 뒤 12분이 넘도록 다음 기록이 없으면 카운터 수집이 끊긴 것이다.
- 기록 사이에는 값을 보내지 않는다. 팬이 100 %인 동안 실제 연속 시간은 마지막 기록 뒤에도 계속 늘어난다.

## 예측_결과.csv — 조치 후 예측값

- 예측 서비스가 경보 사례의 후보마다 「이 조치를 하면 15분 뒤」 유온 TS1(℃)과 토출 압력 PS1을 계산한다(모델 `{forecast.MODEL_ID}`). 계산은 `기준_관측_시각`의 상태로 한다.
- 예측 결과는 기준 관측 뒤 **120초**까지 유효하다(예측 서비스 설정).
- `상태`가 `거부`면 예측하지 않은 것이며 `거부_사유`에 이유가 있다.
- 예측 서비스에서 판정 서버로 전달하다 실패한 행은 파일에 없다(재전송하지 않는다).
- `PS1_단위`: 대부분 `bar`다. HYD-03의 2026-10-10 이전 결과는 옛 내보내기 형식이라 `MPa`다(1 MPa = 10 bar).
- 작업지시만 거는 후보는 설비 설정을 바꾸지 않으므로 예측은 지금 상태가 이어질 때의 값이다.

## 오더_현황.csv — 교육용 비교에 쓰는 오더 값

- 판단 시각 직전에 MES·QMS에서 조회한 그 설비의 생산 오더 값이다. 조회에 실패하면 값이 비고 `비고`에 적힌다.
- `고온_로트_수량_ea`는 유온이 높던 구간에 만들어 출하를 기다리는 OEM 로트 수량이다.
'''

BUSINESS = {
    '설비': 'HYD-01~03 (같은 모델)',
    '안내': '사례마다 다른 오더 값(납기까지_남은_시간, 오더_잔량, 고온_로트_수량)은 오더_현황.csv에 있다. 아래 값은 세 설비·모든 사례에 같다.',
    '값': [
        {'이름': '시간당_생산_수량', '값': 300, '단위': 'ea/h', '시스템': 'MES', '뜻': '설계 부하 90 %로 돌 때 한 시간에 만드는 수량'},
        {'이름': '시간당_생산_가치', '값': 50, '단위': '만원/h', '시스템': 'MES', '뜻': '설계 부하 90 %로 한 시간 생산한 것의 가치'},
        {'이름': '납기_지연_위약금', '값': 120, '단위': '만원/h', '시스템': 'ERP', '뜻': '납기를 넘긴 한 시간마다 무는 금액'},
        {'이름': '계획_외_고장_비용', '값': 900, '단위': '만원', '시스템': 'ERP', '뜻': '이 설비가 계획 없이 한 번 고장 났을 때 드는 비용'},
        {'이름': '평균_고장_간격', '값': 1400, '단위': 'h', '시스템': 'CMMS', '뜻': '이 설비의 MTBF'},
        {'이름': '고온_로트_불량_확률', '값': 0.05, '단위': '확률', '시스템': 'QMS', '뜻': '고온에서 만든 로트에서 불량이 나올 확률'},
        {'이름': '고온_로트_클레임_금액', '값': 3000, '단위': '만원', '시스템': 'QMS', '뜻': '그 로트에서 불량이 나왔을 때의 클레임 금액'},
        {'이름': '팬_최대_추가_전력', '값': 6, '단위': 'kW', '시스템': 'EMS', '뜻': '팬을 60 %에서 100 %로 올릴 때 더 드는 전력'},
        {'이름': '전력_단가', '값': 0.015, '단위': '만원/kWh', '시스템': 'EMS', '뜻': '전력 1 kWh의 값'},
    ],
    '표준_작업': [{'작업': '쿨러 핀 세척', '절차': 'SOP-COOL-14', '정지_시간_h': 3, '작업비_만원': 40, '필요_부품': '없음', '시스템': 'CMMS'}],
}


def example_event(files):
    """지표_정의.md 손계산 예: 첫 번째로 오더 값이 있고 SOP-COOL-12 예측이 완료된 사례."""
    orders = {r['사례']: r for r in csv.DictReader(io.StringIO(files['오더_현황.csv']))}
    fc = {(r['사례'], r['후보']): r for r in csv.DictReader(io.StringIO(files['예측_결과.csv']))}
    for eid, o in orders.items():
        f = fc.get((eid, 'SOP-COOL-12'))
        if o['납기까지_남은_시간_h'] and f and f['상태'] == '완료' and float(o['고온_로트_수량_ea']) > 0 and float(o['납기까지_남은_시간_h']) < 12:
            return eid, o, f
    raise RuntimeError('손계산 예로 쓸 사례 없음')


def metric_doc(files):
    eid, o, f = example_event(files)
    period, remain, lot = float(o['납기까지_남은_시간_h']), float(o['오더_잔량_ea']), float(o['고온_로트_수량_ea'])
    ts1 = float(f['예측_TS1_C'])
    risk = 900 * min(1, period / 1400)
    ratio = 80 / 90
    finish = remain / (300 * ratio)
    late = max(0.0, finish - period)
    prod = 50 * (period * (1 - ratio)) + 120 * late
    qual = 0.05 * 3000 if ts1 >= 55 and lot > 0 else 0.0
    energy = 40 * 6 / 40 * period * 0.015
    q_text = f'{ts1:.2f} ℃는 55 ℃ 이상이고 고온 로트가 {lot:g} ea 있다: 0.05 × 3000' if qual else f'{ts1:.2f} ℃는 55 ℃보다 낮다'
    late_text = (f'완료까지 걸리는 시간은 0 + {remain:g} ÷ (300 × 80/90) = {finish:.4f}시간이고 기간 {period:g}시간보다 ' + ('짧아서 납기 지연 위약금이 0이다.' if late == 0 else f'{late:.4f}시간 길어서 위약금이 120 × {late:.4f} = {120 * late:.2f}이다. 금액은 끝에서만 반올림한다.'))
    return METRIC_DOC.format(eid=eid, period=f'{period:g}', remain=f'{remain:g}', lot=f'{lot:g}', ts1=f'{ts1:.2f}',
                             cost=f'{risk:.2f}', prod=f'{prod:.2f}', qual=f'{qual:.2f}', energy=f'{energy:.2f}', q_text=q_text, late_text=late_text,
                             late_term=f'120 × {late:.4f}' if late else '120 × 0')


METRIC_DOC = '''# 조치 후보를 견주는 네 지표 — 정의와 식

규칙을 통과한 조치 후보를 견줄 때 쓰는 지표의 정의다. 이 문서가 답하는 물음은 하나다.

> 이 조치를 하면, 이 오더의 납기까지 얼마를 잃을 것으로 예상되는가?

지표는 넷이고 모두 **예상되는 손실 금액**이다. 단위는 만 원이며 작을수록 좋다. 대상은 쿨러 냉각 성능 상실 경보가 난 설비이고, 확인된 원인은 쿨러 핀 오염으로 둔다.

| 지표 | 무엇을 잃는가 | 이어지는 성과 지표 (목표) |
|---|---|---|
| 비용 | 정비에 드는 돈과, 원인을 남겨 둔 채 돌리는 동안의 고장 위험 | 평균 고장 간격 (설비 가용성 확보) |
| 생산 | 부하를 낮추거나 설비를 세워 줄어든 생산과, 그 때문에 늦어진 납기 | 생산량 (설비 가용성 확보), 납기 준수율 (납기 신뢰) |
| 품질 | 유온이 높은 채로 만든 제품에서 나올 수 있는 클레임 | 품질 클레임 (품질 신뢰) |
| 에너지 | 팬을 더 세게 돌리는 데 드는 전력 | 전력 사용량 (에너지 효율) |

## 값이 오는 곳

| 파일 | 담긴 것 | 무엇마다 다른가 |
|---|---|---|
| `업무_값.json` | 업무 시스템의 필드에 대응시킨 교육용 고정 값과 표준 작업 | 모든 사례에 같다 |
| `오더_현황.csv` | 사례마다 그 설비의 오더 값: `납기까지_남은_시간_h`, `오더_잔량_ea`, `고온_로트_수량_ea` | 사례마다 |
| `후보_설정.csv` | 후보마다 팬과 부하를 얼마로 두는지, 작업지시를 거는지, 근본 조치인지 | 후보마다 |
| `예측_결과.csv` | 후보마다의 조치 후 예측 유온 | 사례마다, 후보마다 |

## 식에 쓰는 낱말

| 낱말 | 뜻 |
|---|---|
| 기간 | 그 사례의 `납기까지_남은_시간_h`(h). 이 오더의 납기까지를 견준다 |
| 오더 잔량 | 그 사례의 `오더_잔량_ea` |
| 고온 로트 수량 | 그 사례의 `고온_로트_수량_ea` |
| 부하 | 후보의 `부하_설정_퍼센트`. 칸이 비어 있으면 부하를 바꾸지 않는 후보이므로 설계 부하 90 %다 |
| 부하 비율 | 부하 ÷ 90 |
| 팬 | 후보의 `팬_설정_퍼센트`. 칸이 비어 있으면 팬을 바꾸지 않는 후보이므로 정상 운전점 60 %다 |
| 정지 시간 | 후보의 `작업지시` 칸에 적힌 표준 작업의 `정지_시간_h`. 작업지시가 없으면 0이다 |
| 작업비 | 후보의 `작업지시` 칸에 적힌 표준 작업의 `작업비_만원`. 작업지시가 없으면 0이다 |

설계 부하 90 %와 정상 팬 60 %는 설비의 정상 운전점이다. `팬_최대_추가_전력`은 팬을 60 %에서 100 %로, 곧 40 %p 올릴 때 더 드는 전력이다.

## 네 지표의 식

### 비용 = 정비 작업비 + 고장 위험
- 정비 작업비 = 작업비
- 고장 위험 = `계획_외_고장_비용` × (기간 ÷ `평균_고장_간격`)
  - 괄호 안의 값은 1을 넘지 않는다(넘으면 1로 한다).
  - `근본_조치`가 「예」인 후보의 고장 위험을 0으로 두는 것은 이 계산의 가정이다. 작업지시 발행이나 실제 정비 완료를 뜻하지 않는다.

### 생산 = 생산 감소 + 납기 지연 위약금
- 생산 감소 = `시간당_생산_가치` × (기간 × (1 − 부하 비율) + 정지 시간)
- 완료까지 걸리는 시간 = 정지 시간 + 오더 잔량 ÷ (`시간당_생산_수량` × 부하 비율)
- 납기 지연 위약금 = `납기_지연_위약금` × (완료까지 걸리는 시간 − 기간)
  - 괄호 안의 값이 0보다 작으면 0으로 한다(납기 안에 끝난다).

### 품질 = 품질 클레임 위험
- 후보의 조치 후 예측 유온이 55 ℃ 이상이고 고온 로트 수량이 0보다 크면: `고온_로트_불량_확률` × `고온_로트_클레임_금액`
- 그렇지 않으면 0
- 55 ℃는 매뉴얼의 회복 판정 기준이다(HM-8.6, 「TS1이 55 ℃ 미만」).

### 에너지 = 팬 전력비
- 에너지 = (팬 − 60) × `팬_최대_추가_전력` ÷ 40 × 기간 × `전력_단가`

## 손으로 해 보는 예

사례 {eid}의 SOP-COOL-12(팬 100 %, 부하 80 %, 작업지시 없음, 예측 유온 {ts1} ℃, 기간 {period} h, 오더 잔량 {remain} ea, 고온 로트 {lot} ea)를 위 식에 넣으면 다음과 같다.

| 지표 | 식에 넣은 값 | 값 (만 원) |
|---|---|---|
| 비용 | 0 + 900 × ({period} ÷ 1400) | {cost} |
| 생산 | 50 × ({period} × (1 − 80/90) + 0) + {late_term} | {prod} |
| 품질 | {q_text} | {qual} |
| 에너지 | (100 − 60) × 6 ÷ 40 × {period} × 0.015 | {energy} |

{late_text}

## 계산 가정과 비교 계약

이 파일은 제공된 교육용 고정 입력의 비교 계산이다. 실제 업무 DB를 이번에 읽은 값이나 납기 예측 검증 결과가 아니다. 작업지시가 있는 후보의 표준 정지 시간을 기간 안에 모두 더하고, 근본 조치의 고장 위험을 0으로 놓는 단순화가 있다. 야간 작업의 실제 시작·완료 시각과 정비 전 위험을 따로 모델링하지 않는다. 생산 감소 식은 기간 전체의 감산과 정지를 더하므로 두 효과가 겹치는 시간도 포함한다. 이 식을 실제 생산 손실의 정확한 추정으로 해석하지 않는다.

네 손실과 규칙의 감점 금액을 한 번씩 더한 비교 합계를 사용한다. 경고는 사유로 보존하고 제외·보류 후보는 순위에서 뺀다. 필요한 값이 없으면 지표와 합계 순위를 보류하고, 같은 합계는 동순위다. 각 지표의 원값과 가정을 보존하며 HYD의 일곱 성분 정책 점수와 섞지 않는다. 금액은 소수 둘째 자리로 반올림해 적는다.
'''


if __name__ == '__main__':
    files, meta = build()
    for name, text in files.items():
        print(f'{name}: {len(text.splitlines())}줄')
    from collections import Counter
    print(Counter(m['범주'] for m in meta))
