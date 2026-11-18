"""통합반 3회차 두 랩(조치 기준 · 판단 기능)의 자료 — 냉각 경보 조치 판단 원자료 코어(data_conditions.py, 실전반이 받는 공장 규모)의 부분.

코딩랩 K-3의 실습 랩 규모로 고른다. 고른 범위는 이 파일 한 곳이 정한다.
- 매뉴얼: 코어의 HM-8 현행 원문에서 쿨러 냉각 성능 상실에 쓰는 절만(SOP 다섯 — 쿨러 팬 점검, 팬 최대 운전, 팬 최대 운전과 부하 80 %, 부하 70 %와 야간 핀 세척, 쿨러 핀 세척).
  옛 1.0판 · 보충 매뉴얼 · 작업 기준 · 작업 이력은 싣지 않는다(원문 근거 대조는 4회차 몫).
- 경보: 코어의 30일 궤적(HYD-01~03) 경보 60건 가운데 CASES에 적은 것을 경보마다 한 줄로 모은다. 값은 궤적이 낸 그대로이고(meta['cases']),
  원천 넷(경보 목록 · PLC 상태 · 팬 카운터 · 예측 결과)의 주기 · 하트비트 · 끊긴 기록은 싣지 않는다.
  BLANK_FAN에 적은 경보는 팬 100 % 연속 운전시간을 빈 칸으로 둔다(코어에서도 카운터 기록이 끊긴 경보 — 필수값이 없는 사례).
  UNCONFIRMED에 적은 경보는 기준 관측이 판정 요청보다 120초 넘게 앞서 예측이 없는 경보이고, 같은 까닭으로 원인 증거 대조도 하지 못해 확인된 원인이 미확정이다.
- 쿨러 핀 세척(SOP-COOL-14)의 조치 후 예측 유온은 3회차 덱 58장 · 사실표(통합반_02-04일차 「쿨러 과열 한 건의 판단 결과」)와 같은 뜻으로 적는다: 지금 설비를 세우고
  시행하는 조치라 정지한 설비의 예측 25.0 ℃(STOPPED_FORECAST). 코어는 그 칸에 설정을 바꾸지 않은 15분 뒤 유온을 내는데(실전반 판), 그 값은 쓰지 않는다. 코어에 예측이 없는 경보는 빈 칸 그대로다.
- 매뉴얼 사본의 HM-8.8에 한 항목(AND_RULE)을 더했다: 포털 원문(main it/portal/www/samples/HM-8_cooler-fan-manual.md)에는 없는 문장이다. 한 규칙에 조건 둘을 함께 거는
  복수 조건(덱 29장)의 근거가 HM-8의 규정 적합성 조건에 없어서 더한 것이고, 포털 원문의 다른 문장과 부딪치지 않는 경고 조건이다.
- 야간 운전 기준(NIGHT_RULE): 생산팀 운전 파트의 근무 기준 두 항목. 매뉴얼 HM-8.6(경고가 붙은 조치도 다른 조치와 비교한다)과 다른 사람의 업무 기준이고,
  판단 기능 랩의 정할 지점 「쓰는 사람에 따라 갈리는 답」이 이 둘 사이에서 갈린다. 어느 쪽을 따를지는 자료에 적지 않는다.
- 생산 오더 번호는 싣지 않는다(코어가 설비마다 따로 세어 두 설비에 같은 번호가 생기고, 판정 · 비교에 쓰지 않는다).
- 수냉형 HYD-04(2회차 설비 모델 v31의 HPP-45B — 쿨러 팬 없음)의 경보 두 건은 코어의 물리 모델에 없는 기종이라 HYD04에 손으로 적는다.
  팬이 없어 팬 100 % 연속 운전시간과 팬을 올리는 조치의 예측이 비어 있고, 팬 진동이 없어 HM-8.4의 증거로 원인을 가리지 못한다(미확정).
- 결정표 내보내기: 판단 시스템의 결정 넷 · 입력 데이터 · 지금 등록된 규칙(펌프 정기 정비 문서 PM-02에서 옮긴 것과 순위 규칙). 이름과 값은 main의
  it/neo4j/v2/instances.cypher(결정 · 입력 데이터 · rule:rank-value)와 it/process/procsvc/course_extractions.json(PM-02 규칙)의 2026-11-18 판을 옮겨 적었다.
  HM-8에서 옮긴 규칙은 싣지 않는다(이 랩에서 학생이 만든다).
장부의 이름을 따른다: 원문 사본의 「작업지시」는 「정비 요청」으로 적는다(사실표 「같은 말 · 같은 값」).
"""
from datetime import datetime, timedelta, timezone
import csv
import io
import json

KST = timezone(timedelta(hours=9))
NOTICE = '가상 사례: 공개된 현업 문제 유형과 설비 시뮬레이터 로직으로 만든 자료이며 실제 회사 · 설비의 기록이 아니다.'
SOPS = ['SOP-FAN-11', 'SOP-COOL-11', 'SOP-COOL-12', 'SOP-COOL-13', 'SOP-COOL-14']
FORECAST = ['SOP-COOL-11', 'SOP-COOL-12', 'SOP-COOL-13', 'SOP-COOL-14']      # 예측 서비스가 예측을 내는 조치
FAILURE_MODE = '쿨러 냉각 성능 상실'
FOULING, UNKNOWN_CAUSE = '쿨러 핀 오염', '미확정'
STOPPED_FORECAST = '25.0'      # 쿨러 핀 세척 — 정지한 설비의 예측(덱 58장 · 사실표)

# 판단 기능 랩의 경보(코어 경보 ID의 끝 조각). 조치 기준 랩의 확인 사례는 그 가운데 CHECK.
CASES = ['hyd03-0280-beaf', 'hyd02-0153-06b1', 'hyd03-0282-df83', 'hyd01-0191-5241', 'hyd01-0192-03fb', 'hyd01-0193-336d', 'hyd03-0292-eec2',
         'hyd01-0196-c7e2', 'hyd02-0162-65e4', 'hyd01-0197-f774', 'hyd03-0296-2adb', 'hyd02-0165-f047', 'hyd03-0299-374a', 'hyd01-0204-a3de',
         'hyd01-0205-9348', 'hyd01-0206-c2f2', 'hyd02-0170-3589', 'hyd02-0171-051f', 'hyd02-0172-54a5']
CHECK = ['hyd03-0280-beaf', 'hyd03-0282-df83', 'hyd01-0192-03fb', 'hyd03-0292-eec2', 'hyd01-0196-c7e2', 'hyd02-0165-f047', 'hyd01-0204-a3de',
         'hyd01-0205-9348', 'hyd02-0171-051f', 'hyd02-0172-54a5']
BLANK_FAN = {'hyd01-0204-a3de'}
UNCONFIRMED = {'hyd01-0191-5241', 'hyd02-0165-f047'}
HYD04 = [   # 손으로 적은 두 건(위 머리말). 조치 기준 랩의 확인 사례에는 첫 건을 넣는다.
    dict(id='ALT-hyd04-0031-7c2e', raised='2026-10-09T14:11:42+09:00', ts1='55.37', ce='61.8', judge='2026-10-09T14:12:40+09:00', mode='REMOTE_AUTO',
         forecast={'SOP-COOL-13': '51.6', 'SOP-COOL-14': STOPPED_FORECAST}, due='21.5', remain='2300', hot='20'),
    dict(id='ALT-hyd04-0032-a91d', raised='2026-10-22T03:40:05+09:00', ts1='55.18', ce='63.0', judge='2026-10-22T03:41:02+09:00', mode='REMOTE_AUTO',
         forecast={'SOP-COOL-13': '50.9', 'SOP-COOL-14': STOPPED_FORECAST}, due='15.8', remain='1480', hot='30'),
]
CASE_COLUMNS = ['경보_ID', '설비', '고장_유형', '확인된_원인', '발생_시각', '유온_C', '냉각효율_pct', '판정_요청_시각', '운전_모드', '팬100_연속_h',
                *[f'예측_유온_{s}_C' for s in FORECAST]]
ORDER_COLUMNS = ['납기까지_남은_시간_h', '오더_잔량_ea', '고온_로트_수량_ea']
CASE_NOTES = ('# 경보마다 한 줄. 판정을 요청한 시각에 판단에 넣을 값을 모은 표다. 시각은 한국 표준시, 유온과 냉각 효율은 경보가 발생한 때의 값(소수 둘째 · 첫째 자리로 반올림)이다.\n'
              '# 확인된_원인 = 판정 요청 때 매뉴얼 HM-8.4의 증거로 가린 원인. 증거를 대지 못했으면 미확정이다. 운전_모드 = 판정 요청 때의 PLC 운전 모드.\n'
              '# 팬100_연속_h = 판정 요청 때까지 팬이 100 %로 이어서 돈 시간. 0.00은 팬이 100 %가 아니라는 뜻이고, 0보다 크면 팬이 이미 100 %로 돌고 있다.\n'
              '# 예측_유온_<SOP>_C = 그 조치를 했을 때 15분 뒤의 예측 유온. 그때의 팬 · 부하 설정에서 계산하므로 이미 그 설정이면 조치를 하지 않을 때와 같은 값이 나온다. '
              '쿨러 핀 세척(SOP-COOL-14)은 설비를 세우고 하는 작업이라 정지한 설비의 예측이다. 기준 관측이 판정 요청보다 120초 넘게 앞서면 예측하지 않는다.\n'
              '# 값이 빈 칸은 그 값을 읽지 못했거나 그 설비에 그 계측이 없는 것이다. 0이 아니다.\n')
ORDER_NOTES = '# 납기까지_남은_시간_h · 오더_잔량_ea · 고온_로트_수량_ea = 판정 요청 때 그 설비가 돌리던 생산 오더의 값(MES · QMS). 비교 산식이 쓴다.\n'


def cut(text, start, end):
    """text에서 start로 시작하는 줄부터 end로 시작하는 줄 앞까지를 뺀다. 두 줄이 한 번씩 있어야 한다."""
    a, b = text.index('\n' + start) + 1, text.index('\n' + end) + 1
    if text.count('\n' + start) != 1 or text.count('\n' + end) != 1 or a >= b:
        raise ValueError(f'매뉴얼에서 뺄 자리를 찾지 못했습니다: {start} ~ {end}')
    return text[:a] + text[b:]


def swap(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError(f'바꿀 글 「{old}」이 {text.count(old)}번 있습니다({count}번이어야 함).')
    return text.replace(old, new)


def manual(files):
    text = files['HM-8_매뉴얼.md']
    text = cut(text, '## HM-8.2 ', '## HM-8.3 ')
    text = cut(text, '### SOP-COOL-15 ', '## HM-8.8 ')
    head = next(line for line in text.splitlines() if line.startswith('출처:'))
    text = swap(text, head, '출처: 회사 문서 관리 시스템에 등록된 HM-8 현행 원문(판 1.1, 시행 2026-09-01)에서 쿨러 냉각 성능 상실에 쓰는 절을 옮긴 사본이다. '
                            '절 번호는 원문 그대로이고, 팬 벨트 교체(HM-8.2)와 캐비닛 환기 보강(SOP-COOL-15)은 싣지 않았다.')
    text = swap(text, '핀 세척 작업지시를 건다', '핀 세척 정비 요청을 건다')
    text = swap(text, 'CMMS 작업지시로 발행한다', 'CMMS 정비 요청으로 발행한다')
    last = '- 펌프 부하를 60 % 미만으로 설정하지 않는다.\n'
    if not text.endswith(last):
        raise ValueError('매뉴얼 끝이 HM-8.8의 마지막 항목이 아닙니다.')
    text += AND_RULE + '\n'
    if '작업지시' in text or [s for s in ('SOP-FAN-12', '### SOP-COOL-15') if s in text]:
        raise ValueError('매뉴얼 사본에 뺄 글이 남았습니다.')
    return text


AND_RULE = ('- 냉각 효율 CE가 30 % 미만으로 떨어진 설비에서 조치 후 예측 유온이 55 ℃ 이상인 원격 조치는, 핀 오염이 심해 효과가 오래가지 않는다. '
            '이때는 경고를 달아 근본 조치(SOP-COOL-14)와 함께 비교한다.')
NIGHT_RULE = f'''# 야간 운전 기준 (생산팀 운전 파트, 발췌)

{NOTICE}

출처: 생산팀 운전 파트가 야간 근무조에게 주는 근무 기준에서 원격 조치에 관한 항목을 옮겼다. 설비보전팀의 정비 매뉴얼(HM-8)과는 따로 관리하는 문서다.

- 야간 근무조는 운전원 한 명이 2라인 설비를 모두 본다. 원격 조치를 실행하고 15분 재관측에서 회복하지 않으면, 주간 교대 전까지 다시 대응할 인원이 없다.
- 그래서 야간 근무조는 경보 해제에 실패할 수 있다는 경고가 붙은 조치를 먼저 쓰지 않고, 경고가 없는 조치부터 쓴다. 경고가 붙은 조치를 쓰려면 설비보전팀장에게 먼저 알린다.
'''
TARGETS = ('sop_id,name,종류,source_section\n'
           'SOP-FAN-11,쿨러 팬 점검 절차,정비 요청,HM-8.1\n'
           'SOP-COOL-11,팬 최대 운전,원격 조치,HM-8.5\n'
           'SOP-COOL-12,팬 최대 운전과 부하 80 %,원격 조치,HM-8.5\n'
           'SOP-COOL-13,부하 70 %와 야간 핀 세척,원격 조치,HM-8.5\n'
           'SOP-COOL-14,쿨러 핀 세척,정비 요청,HM-8.7\n')
FAILURE_MODES = ('failure_mode_id,name,component,cause_id,cause_name\n'
                 'fm:cooler-cooling-loss,쿨러 냉각 성능 상실,오일 쿨러,cause:cooler-fin-fouling,쿨러 핀 오염\n'
                 'fm:cooler-cooling-loss,쿨러 냉각 성능 상실,오일 쿨러,cause:ambient-temperature-rise,주변 온도 상승\n'
                 'fm:cooler-cooling-loss,쿨러 냉각 성능 상실,오일 쿨러,cause:fan-drive-fault,팬 구동 불량\n'
                 'fm:pump-volumetric-efficiency-loss,주 펌프 체적 효율 저하,주 펌프 (A),cause:pump-shaft-seal-wear,축 씰 마모\n')
RANK_RULE = ('점수 = 성과 득실(조치 방법 → 처음 닿는 성과 지표까지 경로마다 강도의 곱 — high 1 · medium 0.6 · low 0.3, 조건부 경로는 절반) + 예측 유온 여유 (55 − 예측)/3 (±2 한도) '
             '− 경고 0.5 − 감점/20 + 선례 비율 × 1.5 + 납기 긴급도((24 − 남은 h)/24 × 지연 보상/100, 0~1) × 생산 영향(유지 +1 · 감산 +0.4 · 정지 −1) × 1.5 '
             '− 품질 위험(고온 구간 출하 대기 로트가 있고 예측 유온 ≥ 55 ℃ 면 클레임/1000, ≤ 1) × 1.5. 제외된 후보는 뒤로, 점수가 같으면 승인 직급이 낮은 쪽')
EXPORT = f'''# 판단 시스템 결정표 내보내기
# 시스템: 설비 이상 조치 판단 시스템 / 내보낸 시각: 2026-10-27 08:10 (+09:00)
# {NOTICE}
# 형식: 「## 」로 시작하는 절마다 머리 줄 하나와 행들이 있다. 칸은 「 | 」로 나누고, 한 칸 안의 여러 값은 「; 」로 나눈다.
# 범위: 결정 넷, 입력 데이터, 내보낸 시각에 등록된 규칙. 규칙의 출처 칸은 그 규칙을 옮겨 온 문서의 절이다.

## 결정
id | 이름 | 물음 | Hit Policy | 입력 데이터
dec:diagnose-cause | 고장 유형 · 원인 판정 | 이 경보의 고장 유형과 근본 원인은 무엇인가? | PRIORITY | in:pattern; in:ts1; in:ce; in:ps1
dec:action-candidates | 조치 후보 선택 | 이 고장 유형에 쓸 수 있는 조치 방법은 무엇인가? (원인이 정해진 조치 방법은 원인으로 거른다) | COLLECT | in:failure-mode; in:cause; in:plc-state; in:pattern
dec:compliance | 규정 적합성 | 조치 후보 가운데 규정상 쓸 수 없거나 감점할 것은 무엇인가? | COLLECT | in:plc-mode; in:plc-state; in:forecast-ts1; in:forecast-ps1; in:fan100-hours; in:production-running; in:order-due; in:next-scheduled-time; in:hours-if-deferred; in:pm-crew; in:spare-available
dec:rank-actions | 조치 우선순위 | 남은 후보 중 회사 가치(영업이익)에 가장 유리한 순서는? | UNIQUE | in:forecast-ts1; in:order-due; in:order-penalty; in:order-tier; in:hot-lot-claim; in:hot-lot-qty

## 입력 데이터
id | 이름 | 값의 꼴 | 단위 | 값이 오는 곳
in:pattern | 경보 패턴 | 글자 |  | 경보 감지
in:failure-mode | 판정 고장 유형 | 글자 |  | 판단 에이전트
in:cause | 판정 원인 | 글자 |  | 판단 에이전트
in:ts1 | 유온 | 숫자 | ℃ | 센서 TS1
in:ce | 냉각 효율 | 숫자 | % | 계산값 CE
in:ps1 | 토출 압력 | 숫자 | bar | 센서 PS1
in:plc-mode | PLC 운전 모드 | REMOTE_AUTO; REMOTE_MANUAL; LOCAL |  | SCADA
in:plc-state | PLC 상태 | RUN; STOP; TRIP |  | SCADA
in:forecast-ts1 | 조치 후 예측 유온 | 숫자 | ℃ | 예측 서비스(조치 후보마다)
in:forecast-ps1 | 조치 후 예측 토출 압력 | 숫자 | bar | 예측 서비스(조치 후보마다)
in:fan100-hours | 팬 100 % 연속 운전 시간 | 숫자 | h | 시계열 저장소
in:production-running | 생산 중 여부 | 참; 거짓 |  | MES
in:order-due | 긴급 오더 남은 시간 | 숫자 | h | MES
in:order-penalty | 납기 지연 시 시간당 보상 | 숫자 | 만원/h | ERP
in:order-tier | 고객 등급 | 글자 |  | ERP
in:hot-lot-claim | 고온 구간 출하 대기 로트의 클레임 위험 | 숫자 | 만원 | QMS
in:hot-lot-qty | 고온 구간 출하 대기 수량 | 숫자 | ea | QMS
in:next-scheduled-time | 이번 예정된 정비 시간에 닿을 때의 운전시간 | 숫자 | h | CMMS
in:hours-if-deferred | 그다음 예정된 정비 시간까지 미룰 때의 운전시간 | 숫자 | h | CMMS
in:pm-crew | 그 시간의 정비 인원 | 숫자 | 명 | CMMS
in:spare-available | 씰 키트 가용 재고 | 숫자 | 개 | ERP

## 규칙
id | 결정 | 조건 | 결과 | 감점(만원) | 적용 대상 | 설명 | 출처
rule:pm-pump-leakage-seal-wear-first | dec:diagnose-cause | in:pattern == PUMP_LEAKAGE; in:ps1 < 165 bar | 선택 |  | cause:pump-shaft-seal-wear | PUMP_LEAKAGE 경보에서 토출 압력이 165 bar 미만이면 축 씰 마모를 1순위 원인으로 둔다 | PM-2.10
rule:pm-02-pm-due-candidates | dec:action-candidates | in:pattern == PM_DUE | 선택 |  | SOP-PM-11; SOP-PM-12; SOP-PM-13; SOP-PM-14 | 정기 정비 도래로 열린 처리 건에서 시행 방식 네 가지를 비교 후보로 낸다 | PM-2.5
rule:pm-next-window-over-hours-limit | dec:compliance | in:next-scheduled-time > 2200 h | 제외 |  | SOP-PM-11; SOP-PM-14 | 이번 예정된 정비 시간에 닿을 때의 운전시간이 2,200 h를 넘으면 그 시간까지 기다리는 방식을 쓰지 않는다 | PM-2.5
rule:pm-following-window-over-hours-limit | dec:compliance | in:hours-if-deferred > 2200 h | 제외 |  | SOP-PM-13 | 그다음 예정된 정비 시간까지 미룰 때의 운전시간이 2,200 h를 넘으면 미루지 않는다 | PM-2.5
rule:pm-immediate-stop-order-loss | dec:compliance | in:production-running == 참; in:order-due <= 24 h | 감점 | 80 | SOP-PM-12 | 납기가 24시간 안에 있는 생산 오더가 있을 때 즉시 정지하면 오더 손실 80만 원을 감점한다 | PM-2.5
rule:pm-bundled-crew-shortage-cost | dec:compliance | in:pm-crew < 4 명 | 감점 | 60 | SOP-PM-14 | 같은 기종 두 대를 묶는 시간의 정비 인원이 4명보다 적으면 초과 근무 · 외주 비용 60만 원을 감점한다 | PM-2.5
rule:pm-no-seal-kit-excludes-execution | dec:compliance | in:spare-available == 0 개 | 제외 |  | SOP-PM-21; SOP-PM-22; SOP-PM-23 | 씰 키트 가용 재고가 없으면 정기 정비를 시행하지 않는다 | PM-2.5
rule:pm-bundled-seal-kit-shortage | dec:compliance | in:spare-available < 2 개 | 제외 |  | SOP-PM-14 | 두 대를 묶어 시행하려면 씰 키트가 2개 이상 있어야 한다 | PM-2.5
rule:pm-seal-kit-reorder-warning | dec:compliance | in:spare-available < 3 개 | 경고 |  | SOP-PM-11; SOP-PM-12; SOP-PM-13; SOP-PM-14; SOP-PM-21; SOP-PM-22; SOP-PM-23 | 씰 키트 가용 재고가 3개 미만이면 출고 뒤 재주문점(2개) 아래로 내려가므로 제안에 구매 경보 예정을 표시한다 | PM-2.5
rule:rank-value | dec:rank-actions | 항상 | 순위 |  | 남은 조치 후보 모두 | {RANK_RULE} | 경남유압 BSC 전략맵
'''


def stamp(text):
    """코어의 시각(+09:00 또는 Z)을 한국 표준시 한 가지로 적는다."""
    return datetime.fromisoformat(text.replace('Z', '+00:00')).astimezone(KST).isoformat(timespec='seconds')


def case_rows(files, meta):
    """경보마다 한 줄(dict, CASE_COLUMNS + ORDER_COLUMNS). 판정 요청 시각 차례."""
    raised = {r['경보_ID']: r for r in csv.DictReader(io.StringIO(files['경보_목록.csv'])) if r['구분'] == 'RAISE'}
    orders = {r['경보_ID']: r for r in csv.DictReader(io.StringIO(files['오더_현황.csv']))}
    by = {c['id'][4:]: c for c in meta['cases']}
    rows = []
    for key in CASES:
        c, i = by[key], by[key]['inputs']
        a, o = raised[c['id']], orders[c['id']]
        if c['order'] is None or float(o['납기까지_남은_시간_h']) != c['order']['due_h']:
            raise ValueError(f'{key}: 오더 값이 없거나 코어의 두 자리 값이 다릅니다.')
        fan = '' if key in BLANK_FAN or i['fan_elapsed_min'] is None else f'{i["fan_elapsed_min"] / 60:.2f}'
        row = {'경보_ID': c['id'], '설비': c['asset'], '고장_유형': FAILURE_MODE, '확인된_원인': UNKNOWN_CAUSE if key in UNCONFIRMED else FOULING,
               '발생_시각': stamp(a['시각']), '유온_C': a['TS1_C'], '냉각효율_pct': a['CE_pct'], '판정_요청_시각': stamp(c['judge']),
               '운전_모드': i['mode'] or '', '팬100_연속_h': fan,
               **{f'예측_유온_{s}_C': '' if i['ts1'][s] is None else f'{i["ts1"][s]:.1f}' for s in FORECAST},
               '납기까지_남은_시간_h': o['납기까지_남은_시간_h'], '오더_잔량_ea': o['오더_잔량_ea'], '고온_로트_수량_ea': o['고온_로트_수량_ea']}
        if i['ts1']['SOP-COOL-14'] is not None:
            row['예측_유온_SOP-COOL-14_C'] = STOPPED_FORECAST
        if key in UNCONFIRMED and any(i['ts1'][s] is not None for s in FORECAST):
            raise ValueError(f'{key}: 미확정으로 둔 경보인데 코어에 예측이 있습니다(기준 관측이 묵은 경보가 아님).')
        rows.append(row)
    for h in HYD04:
        rows.append({'경보_ID': h['id'], '설비': 'HYD-04', '고장_유형': FAILURE_MODE, '확인된_원인': UNKNOWN_CAUSE, '발생_시각': h['raised'], '유온_C': h['ts1'],
                     '냉각효율_pct': h['ce'], '판정_요청_시각': h['judge'], '운전_모드': h['mode'], '팬100_연속_h': '',
                     **{f'예측_유온_{s}_C': h['forecast'].get(s, '') for s in FORECAST},
                     '납기까지_남은_시간_h': h['due'], '오더_잔량_ea': h['remain'], '고온_로트_수량_ea': h['hot']})
    return sorted(rows, key=lambda r: r['판정_요청_시각'])


def table(rows, columns):
    buf = io.StringIO()
    w = csv.DictWriter(buf, columns, lineterminator='\n', extrasaction='ignore')
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def check_cases(rows):
    keep = {'ALT-' + k for k in CHECK} | {HYD04[0]['id']}
    return CASE_NOTES + table([r for r in rows if r['경보_ID'] in keep], CASE_COLUMNS)


def alarms(rows):
    return CASE_NOTES + ORDER_NOTES + table(rows, CASE_COLUMNS + ORDER_COLUMNS)


def business_values(files):
    doc = json.loads(files['metrics/업무_값.json'])
    doc['설비'] = '2라인 유압 파워팩'
    doc['안내'] = '경보마다 다른 오더 값(납기까지_남은_시간_h, 오더_잔량_ea, 고온_로트_수량_ea)은 alarms.csv의 그 경보 줄에 있다. 아래 값은 모든 경보에 같다.'
    return json.dumps(doc, ensure_ascii=False, indent=2) + '\n'


def candidate_settings(files):
    text = files['metrics/후보_설정.csv']
    return swap(text, '후보,이름,팬_설정_퍼센트,부하_설정_퍼센트,작업지시,근본_조치', '후보,이름,팬_설정_퍼센트,부하_설정_퍼센트,정비_요청,근본_조치')


METRICS = '''# 조치 후보를 견주는 네 손실 — 정의와 식

{notice}

규정 적합성 결정표에서 허용으로 남은 조치 후보를 견줄 때 쓰는 주어진 비교 산식이다. 이 문서가 답하는 물음은 하나다.

> 이 조치를 하면, 이 오더의 납기까지 얼마를 잃을 것으로 예상되는가?

손실은 넷이고 모두 예상되는 금액이다. 단위는 만 원이며 작을수록 좋다. 대상은 쿨러 성능 저하 경보가 난 설비다. 포털 조건별 손익 화면의 예상 손익과 같은 식을 손실의 크기(양수, 만 원)로 적은 것이다.

| 손실 | 무엇을 잃는가 |
|---|---|
| 비용 | 정비에 드는 돈과, 원인을 남겨 둔 채 돌리는 동안의 고장 위험 |
| 생산 | 부하를 낮추거나 설비를 세워 줄어든 생산과, 그 때문에 늦어진 납기 |
| 품질 | 유온이 높은 채로 만든 제품에서 나올 수 있는 클레임 |
| 에너지 | 팬을 더 세게 돌리는 데 드는 전력 |

네 손실과 결정표가 낸 감점 금액을 한 번씩 더한 값이 그 후보의 비교값이다.

## 정책 점수

판단 시스템은 조치 우선순위 결정표의 순위 규칙 `rule:rank-value`로 남은 후보마다 정책 점수를 매기고, 점수가 높을수록 앞에 둔다. 그 규칙의 설명은 다음과 같다.

> {rank}

## 값이 오는 곳

| 파일 | 담긴 것 | 무엇마다 다른가 |
|---|---|---|
| `business_values.json` | 업무 시스템에서 가져온 고정 값과 표준 작업 | 모든 경보에 같다 |
| `candidate_settings.csv` | 후보마다 팬과 부하를 얼마로 두는지, 정비 요청을 거는지, 근본 조치인지 | 후보마다 |
| `../alarms.csv` | 경보마다 그 설비의 오더 값과 후보마다의 조치 후 예측 유온 | 경보마다 |

## 식에 쓰는 낱말

| 낱말 | 뜻 |
|---|---|
| 기간 | 그 경보의 `납기까지_남은_시간_h`(h). 이 오더의 납기까지를 견준다 |
| 오더 잔량 | 그 경보의 `오더_잔량_ea` |
| 고온 로트 수량 | 그 경보의 `고온_로트_수량_ea` |
| 부하 | 후보의 `부하_설정_퍼센트`. 칸이 비어 있으면 부하를 바꾸지 않는 후보이므로 설계 부하 90 %다 |
| 부하 비율 | 부하 ÷ 90 |
| 팬 | 후보의 `팬_설정_퍼센트`. 칸이 비어 있으면 팬을 바꾸지 않는 후보이므로 정상 운전점 60 %다 |
| 정지 시간 | 후보의 `정비_요청` 칸에 적힌 표준 작업의 `정지_시간_h`. 정비 요청이 없으면 0이다 |
| 작업비 | 후보의 `정비_요청` 칸에 적힌 표준 작업의 `작업비_만원`. 정비 요청이 없으면 0이다 |

`팬_최대_추가_전력`은 팬을 60 %에서 100 %로 올릴 때 더 드는 전력이다.

## 네 손실의 식

### 비용 = 정비 작업비 + 고장 위험
- 정비 작업비 = 작업비
- 고장 위험 = `계획_외_고장_비용` × (기간 ÷ `평균_고장_간격`). 괄호 안의 값이 1을 넘으면 1로 한다.
- `근본_조치`가 「예」인 후보의 고장 위험은 0으로 둔다. 이것은 계산의 가정이고, 정비 요청 발행이나 정비 완료를 뜻하지 않는다.

### 생산 = 생산 감소 + 납기 지연 위약금
- 생산 감소 = `시간당_생산_가치` × (기간 × (1 − 부하 비율) + 정지 시간)
- 완료까지 걸리는 시간 = 정지 시간 + 오더 잔량 ÷ (`시간당_생산_수량` × 부하 비율)
- 납기 지연 위약금 = `납기_지연_위약금` × (완료까지 걸리는 시간 − 기간). 괄호 안의 값이 0보다 작으면 0으로 한다.

### 품질 = 품질 클레임 위험
- 후보의 조치 후 예측 유온이 55 ℃ 이상이고 고온 로트 수량이 0보다 크면 `고온_로트_불량_확률` × `고온_로트_클레임_금액`, 그렇지 않으면 0이다. 쿨러 핀 세척은 설비를 세우고 하므로 예측 유온이 정지한 설비의 값이고 이 손실이 0이다.

### 에너지 = 팬 전력비
- 에너지 = (팬 − 60) × `팬_최대_추가_전력` ÷ 40 × 기간 × `전력_단가`

## 손으로 해 보는 예

경보 {ex_id}의 SOP-COOL-12(팬 100 %, 부하 80 %, 정비 요청 없음, 예측 유온 {ex_f} ℃, 기간 {ex_p} h, 오더 잔량 {ex_r} ea, 고온 로트 {ex_h} ea)를 위 식에 넣으면 다음과 같다.

| 손실 | 식에 넣은 값 | 값 (만 원) |
|---|---|---|
| 비용 | 0 + 900 × ({ex_p} ÷ 1400) | {ex_cost:.2f} |
| 생산 | 50 × ({ex_p} × (1 − 80/90) + 0) + 120 × 0 | {ex_prod:.2f} |
| 품질 | {ex_f} ℃는 55 ℃보다 낮다 | 0.00 |
| 에너지 | (100 − 60) × 6 ÷ 40 × {ex_p} × 0.015 | {ex_energy:.2f} |

완료까지 걸리는 시간은 0 + {ex_r} ÷ (300 × 80/90) = {ex_finish:.2f}시간이고 기간 {ex_p}시간보다 짧아서 납기 지연 위약금이 0이다. 감점이 없으므로 비교값은 {ex_total:.2f}만 원이다.

## 계산 가정

정비 요청이 있는 후보의 표준 정지 시간을 기간 안에 모두 더하고, 근본 조치의 고장 위험을 0으로 놓는다. 야간 작업의 실제 시작 · 완료 시각은 따로 계산하지 않는다.
필요한 값이 비어 있으면 0으로 채우지 않고 그 후보의 비교값을 내지 않는다. 금액은 손실마다 소수 둘째 자리로 반올림한 뒤 더한다.
'''


def metric_definitions(files, rows):
    values = {v['이름']: v['값'] for v in json.loads(files['metrics/업무_값.json'])['값']}
    r = next(x for x in rows if x['경보_ID'] == 'ALT-hyd03-0280-beaf')
    p, remain, f = float(r['납기까지_남은_시간_h']), float(r['오더_잔량_ea']), r['예측_유온_SOP-COOL-12_C']
    if (values['계획_외_고장_비용'], values['평균_고장_간격'], values['시간당_생산_가치'], values['시간당_생산_수량'], values['납기_지연_위약금'],
            values['팬_최대_추가_전력'], values['전력_단가']) != (900, 1400, 50, 300, 120, 6, 0.015) or float(f) >= 55:
        raise ValueError('손으로 해 보는 예의 식에 적은 업무 값이 코어와 다릅니다.')
    cost, prod, energy = round(900 * p / 1400, 2), round(50 * p * (1 - 80 / 90), 2), round(40 * 6 / 40 * p * 0.015, 2)
    finish = remain / (300 * 80 / 90)
    if finish > p:
        raise ValueError('손으로 해 보는 예의 경보가 납기를 넘깁니다.')
    num = lambda x: f'{x:g}'
    return METRICS.format(notice=NOTICE, rank=RANK_RULE, ex_id=r['경보_ID'], ex_f=f, ex_p=num(p), ex_r=num(remain), ex_h=r['고온_로트_수량_ea'],
                          ex_cost=cost, ex_prod=prod, ex_energy=energy, ex_finish=finish, ex_total=round(cost + prod + energy, 2))


def build():
    """{이름: 글} — 두 랩 생성기(build_session3_lab.py)가 data/ 아래에 쓴다."""
    import data_conditions as DC
    files, meta = DC.build()
    rows = case_rows(files, meta)
    return {'hm8_manual.md': manual(files), 'decision_table_export.txt': EXPORT, 'targets.csv': TARGETS, 'failure_modes.csv': FAILURE_MODES,
            'check_cases.csv': check_cases(rows), 'alarms.csv': alarms(rows), 'night_operation_rule.md': NIGHT_RULE,
            'metrics/metric_definitions.md': metric_definitions(files, rows), 'metrics/business_values.json': business_values(files),
            'metrics/candidate_settings.csv': candidate_settings(files)}


if __name__ == '__main__':
    out = build()
    for name, text in out.items():
        print(f'{name}: {len(text.splitlines())}줄 · {len(text.encode("utf-8"))}바이트')
