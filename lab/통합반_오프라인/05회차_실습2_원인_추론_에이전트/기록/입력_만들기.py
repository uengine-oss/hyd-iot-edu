"""시작 폴더의 input/sensor_input.json 을 만든다. S01의 CE · VS1 평균 · TS4와 신선도는 쿨러 사건의 실측(1일차 기술사실표 5.2 · 5.3),
정상 부근 값은 같은 사실표 4절의 /api/state 응답에서 가져왔다. 나머지 사례의 값은 여러 경우를 보이려고 새로 든 대어 보는 값이다.
사용: python3 입력_만들기.py <내보낼 파일>"""
import json, sys
SPEC = [('CE', 'avg', 30, 3), ('VS1', 'avg', 120, 3), ('VS1', 'max-min', 300, 3), ('TS1', 'avg', 120, 3), ('TS4', 'avg', 120, 12), ('PS1', 'avg', 120, 3), ('FS1', 'avg', 120, 3)]
def cov(win, limit, gap): return {'samples': win if limit == 3 else win // 10 + 6, 'max_gap_s': gap, 'limit_s': limit, 'covered': True}
def case(no, asset, pattern, at, age, vals, memo, gaps=None, over=None):
    gaps = gaps or [1.004, 1.009, 1.012, 1.006, 11.002, 1.008, 1.005]; rs = []
    for (tag, agg, win, limit), v, g in zip(SPEC, vals, gaps):
        r = {'tag': tag, 'aggregate': agg, 'windowSeconds': win, 'value': v, 'coverage': cov(win, limit, g)}
        k = f'{tag}/{agg}'
        if over and k in over: r['value'] = over[k]['value']; r['coverage'] = over[k]['coverage']
        rs.append(r)
    return {'번호': no, '설비': asset, '경보_패턴': pattern, '판단_시각': at, 'freshness': {'tag': 'TS1', 'age_s': age, 'max_age_s': 60, 'ok': age <= 60}, 'readings': rs, '메모': memo}
C = [
 case('S01', 'HYD-01', 'COOLER_DEGRADATION', '2026-10-10 11:13:18', 0.6, [46.2, 0.575, 0.04, 60.7, 28.0, 181.2, 8.92], '주간조. 유온 경보 뒤 현장 확인 전.'),
 case('S02', 'HYD-02', 'COOLER_DEGRADATION', '2026-10-06 14:41:52', 0.8, [62.4, 0.61, 0.05, 57.8, 36.8, 180.9, 8.90], '오후 외기 온도가 높았던 날. 캐비닛 문을 닫고 운전 중이었다.', [1.006, 1.011, 1.011, 1.003, 10.998, 1.007, 1.002]),
 case('S03', 'HYD-03', 'COOLER_DEGRADATION', '2026-10-07 09:27:05', 0.7, [58.0, 1.05, 0.11, 58.6, 29.1, 181.0, 8.91], '순찰 때 팬 쪽에서 평소와 다른 소리가 났다는 구두 전달이 있었다.', [1.002, 1.008, 1.010, 1.005, 11.004, 1.006, 1.004]),
 case('S04', 'HYD-01', 'PUMP_LEAKAGE', '2026-10-08 16:03:40', 0.5, [83.5, 0.58, 0.03, 49.6, 27.9, 158.3, 7.4], '프레스 사이클이 길어졌다는 생산 쪽 연락이 먼저 왔다.', [1.005, 1.007, 1.013, 1.004, 11.001, 1.010, 1.006]),
 case('S05', 'HYD-02', 'PUMP_LEAKAGE', '2026-10-08 21:15:09', 0.9, [83.9, 0.59, 0.04, 48.7, 27.6, 163.2, 8.3], '야간조. 경보가 한 번 뜬 뒤 압력이 오르내렸다.', [1.003, 1.006, 1.009, 1.007, 10.996, 1.011, 1.008]),
 case('S06', 'HYD-03', 'FAN_VIBRATION', '2026-10-09 10:52:31', 0.6, [82.9, 1.31, 0.34, 49.2, 28.2, 181.4, 8.93], '지난 정기 점검 때 팬 베어링에 그리스를 보충한 기록이 있다.', [1.004, 1.010, 1.012, 1.006, 11.003, 1.005, 1.003]),
 case('S07', 'HYD-01', 'COOLER_DEGRADATION', '2026-10-12 08:36:14', 0.7, [51.0, 0.58, 0.04, 59.4, None, 181.1, 8.92], '캐비닛 온도 센서 케이블을 교체하는 중이어서 TS4 수집이 멈춰 있다.',
      over={'TS4/avg': {'value': None, 'coverage': {'samples': 0, 'max_gap_s': None, 'limit_s': 12, 'covered': False}}}),
 case('S08', 'HYD-02', 'COOLER_DEGRADATION', '2026-10-12 11:03:27', 0.9, [66.1, 0.60, 0.05, 56.2, 30.2, 180.8, 8.90], '네트워크 스위치 교체로 11:03 무렵 수집이 잠깐 끊겼다.',
      over={'CE/avg': {'value': 66.1, 'coverage': {'samples': 9, 'max_gap_s': 14.2, 'limit_s': 3, 'covered': False}}}),
 case('S09', 'HYD-03', 'COOLER_DEGRADATION', '2026-10-13 13:20:46', 185.0, [48.9, 0.57, 0.04, 60.1, 28.3, 181.3, 8.92], '게이트웨이를 재기동한 뒤 화면의 값이 한동안 그대로였다.'),
 case('S10', 'HYD-01', 'FAN_VIBRATION', '2026-10-14 15:48:02', 0.6, [71.5, 1.24, 0.12, 56.3, 28.4, 181.0, 8.91], '경보는 떴지만 진동이 더 오르지는 않았다. 같은 시간대에 부하를 올려 운전했다.', [1.006, 1.009, 1.010, 1.004, 11.000, 1.007, 1.005]),
 case('S11', 'HYD-02', 'OIL_ANALYSIS', '2026-10-15 09:05:00', 0.8, [84.1, 0.58, 0.03, 48.2, 27.8, 181.4, 8.92], '분기 오일 분석 결과가 기준을 벗어났다고 보전 담당자가 입력했다. 분석 성적서는 아직 첨부되지 않았다.', [1.004, 1.008, 1.011, 1.005, 10.999, 1.006, 1.004]),
]
open(sys.argv[1], 'w', encoding='utf-8').write(json.dumps(C, ensure_ascii=False, indent=1) + '\n')
print(len(C), sum(len(c['readings']) for c in C))
