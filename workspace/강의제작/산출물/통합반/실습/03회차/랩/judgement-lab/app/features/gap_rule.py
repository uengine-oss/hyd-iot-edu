"""제공 빈 틀입니다. 이 파일을 바로 고쳐 채웁니다 — 정할 지점: 빈 값의 뜻.

팬 운전 카운터의 정해진 주기 기록이 판정 요청 전에 끊긴 경보마다 제공 코드 judge_tools.py가 이 함수를 부릅니다.
ctx(읽기만): alarm_id 경보 ID · asset 설비 · decision_time 판정 요청 시각(UTC 글자) ·
  counter_last 판정 요청 전 마지막 카운터 기록(fan_counter.csv의 칸 이름 그대로 + '줄' 줄 번호) · counter_age_min 그 기록에서 판정 요청까지 지난 분 · counter_period_min 주기 기록 간격(분) ·
  plc_last 판정 요청 전 마지막 PLC 상태 수신(plc_status.csv의 칸 이름 그대로 + '줄', 없으면 None) · plc_reason 운전 모드 · 상태를 값 없음으로 둔 까닭(값이 있으면 None)
돌려줄 값: (팬 100 % 연속 시간 h — 숫자 또는 None, None이면 값이 없는 까닭 글 · 숫자면 None)
"""


def fan_hours_when_gap(ctx):
    raise NotImplementedError('빈 틀: app/features/gap_rule.py fan_hours_when_gap')
