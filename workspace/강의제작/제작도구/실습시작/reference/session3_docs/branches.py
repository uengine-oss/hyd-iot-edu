"""강사 참조 — 문서 지식 묶음 추출 랩(통합 04-2 · 실전 03-4)의 갈래별 검토. 학생 폴더 · ZIP에 넣지 않는다.

검토는 사람이 원문을 읽고 적은 두 가지에 건다(구성안 9.1 — 후보 id가 아니라 원문에 걸어, 어느 실행의 후보에도 같은 결정이 걸린다):
- 기대 항목(expected_items.py · HM-8 1.1 단계는 sop.json 기준선) — 문서 · 절 · 종류 · 인용(기준값이면 값 · 단위 · 비교)을 원문에서 손으로 적은 것.
  견줄 때는 인용 줄마다 앞머리(목록 번호 「N. 」 · 글머리 「- 」 · 원문자 · 「EN:」 · 「KO:」)를 걷는다 — 원문 줄 그대로 옮긴 번호는 단계 번호(order)이지 내용이 아니다.
  후보가 이것과 같으면 채택한다. 같은 항목인데 비교 · 범위 · 절 표기가 다르거나, 인용이 그 문장을 품은 여러 문장 · 그 문장의 일부(기준값 조각)라 경계만 다르면
  인용 · 줄을 기대 항목 문장으로 고쳐 채택한다(수정 — before에 바꾸기 전 값). 같은 원문을 다른 종류로 뽑았거나 문장의 작은 조각만 인용했으면 까닭을 적어 뺀다(제외).
  같은 항목을 앞 후보가 이미 담았으면 중복으로 뺀다. 검토자가 적은 항목이 있는 줄인데 어느 항목과도 맞지 않는 후보는 그 줄의 항목을 들어 결정하고,
  검토자가 적은 항목이 없는 줄의 후보는 적재하지 않는다(보류 — 사람이 결정하지 않음).
- 원문 줄의 분류(LINES) — 사내 기준과의 관계(같음 · 다르게 정함 · 정하지 않음 · 옛 판 체계)와 지점5의 원문. 갈래 규칙이 여기에 걸린다.
그 밖에 원문 구조에서 바로 보이는 잘못(서로 다른 여러 줄에 걸친 인용, 나열한 숫자의 마지막 것만 뽑은 기준값, 괄호가 닫히지 않은 조각)은 까닭을 적어 뺀다.
누락(missing)은 어느 후보도 담지 못한 기대 항목이다 — 까닭(note)은 그 줄을 다른 종류 · 경계로 뽑은 후보, 원문 여러 곳에 맞아 줄을 정하지 못한 같은 글의 후보가
있었는지를 그 후보 id로 적고, 그런 후보가 없을 때만 「원문에 있는데 후보가 없음」이다.
줄은 줄 번호가 아니라 원문 글자(anchor)로 찾는다 — 문서가 바뀌어 글자가 없거나 여러 줄에 맞으면 멈춘다.

정할 것(구성안 4절):
- 지점5 조건의 근거 — 가: SR-04 제4조 ①②를 R4 전체(네 후보)의 근거로 채택 / 나: 원문 범위대로 운전 중 제어 후보(SOP-COOL-11~13)의
  근거로만, SOP-COOL-14의 R4는 근거 없음(불일치) / 다: 안전관리 담당 해석 전까지 보류.
- 지점6 사내 문서와 제조사 지침 — 가: 사내 기준이 정하지 않은 제조사 항목은 보류(소유자 확인) / 나: 까닭을 적고 채택.
판정 랩 입력(3회차 지점2 가 — 조건표에 R4 · R5가 네 후보에 걸림)에서 6갈래, 내 입력이 3회차 지점2 나(제어 후보에만) · 다(옮기지 않음)이면
지점5만 세 갈래씩(rule_links · 선택 작업 금지). 다음 실습 입력(강사 판) = 강사 추출 실행 run1의 후보(base_candidates)를 지점5 나 · 지점6 가로 검토한 것 —
추출 랩 학생용 완성본의 검토와 같은 바이트다.
"""
from __future__ import annotations

from pathlib import Path
import copy
import hashlib
import json
import re

import extract_reference as X
import expected_items as E

P5, P6 = ('가', '나', '다'), ('가', '나')
BASE = ('나', '가')                       # 다음 실습 입력 · 학생용 완성본의 갈래
BASE_RUN = Path(__file__).resolve().parent/'강사_추출'/'run1'   # 다음 실습 입력 · 학생용 완성본의 후보 — 강사 추출 실행(수업 모델 답, instructor_extract.py)
OWN = ('나', '다')                        # 3회차 지점2 — 내 입력(결과/내_입력/)이 그 갈래일 때
REVIEWER = '설비보전팀 검토'
REVIEWED_AT = '2026-10-28T10:30:00+09:00'
TASK = 'SOP-COOL-14'
OTHER_TASK = 'SOP-COOL-11'                # 실전 03-5 「다른 작업」 — 사건 경보 검토 의견의 top(조치검토결과.json)
INCIDENT = 'ALT-hyd02-0172-54a5'

# 원문 줄의 분류 — (자료 파일, 그 줄에만 있는 글자, 분류, 까닭). 분류: same(사내 기준과 같음) · differ(다르게 정함) ·
# undefined(사내 기준이 정하지 않음 — 지점6) · old(옛 판 체계) · r4(지점5) · task(핀 세척 원문 — 선택 작업).
OEM, SCAN, SR, HM11 = E.OEM, E.SCAN, E.SR, 'HM-8_매뉴얼.md'
SAME = '사내 기준과 같은 항목 — 출처를 하나 더한다'
DIFFER = '사내 기준과 다르게 정한 항목은 사내 기준을 따른다(제조사 지침 머리말 7줄 · DC-01 DC-3)'
UNDEFINED = '사내 기준이 정하지 않은 제조사 항목'
LINES = [
    (OEM, 'Before opening any hydraulic line or filter housing', 'same', SAME + ' — PM-02 PM-2.6 · SOP-PM-21 1~2단계(정지 · 잠금 · 잔압 배출)'),
    (OEM, 'Do not open the circuit until the system pressure gauge reads 0 psi.', 'same', SAME + ' — PM-02 SOP-PM-21 3단계(PS1 0 bar 확인 뒤 배관을 연다)'),
    (OEM, 'Never loosen a fitting to release trapped pressure.', 'undefined', UNDEFINED + ' — 피팅을 풀어 압력을 빼지 않는다'),
    (OEM, 'Allow the fluid to cool below 40 °C before draining.', 'undefined', UNDEFINED + ' — 배유 전 온도'),
    (OEM, 'Intervals are counted from commissioning or from the last completed service', 'differ', DIFFER + ' — PM-02 PM-2.1 · 2.3(운전시간 계수기, 시행한 때부터 다시 셈)'),
    (OEM, '| Fluid level and appearance', 'undefined', UNDEFINED + ' — 매일 수위 · 외관'),
    (OEM, '| Fluid condition (colour, odour)', 'undefined', UNDEFINED + ' — 월 1회 또는 150 h 작동유 상태'),
    (OEM, '| Return filter element, 10 µm', 'differ', DIFFER + ' — PM-02 PM-2.2 2,000 h 패키지의 리턴 필터 교체'),
    (OEM, '| Suction strainer, 125 µm', 'undefined', UNDEFINED + ' — 흡입 스트레이너 4,000 h 세척'),
    (OEM, '| Accumulator precharge', 'differ', DIFFER + ' — PM-02 PM-2.2 4,000 h 패키지의 프리차지 점검'),
    (OEM, '| Pump shaft seal', 'same', SAME + ' — PM-02 PM-2.2 2,000 h 패키지의 주 펌프 축 씰 키트 교체'),
    (OEM, '| Fluid laboratory analysis', 'differ', DIFFER + ' — PM-02 PM-2.2 4,000 h 패키지의 작동유 샘플 분석'),
    (OEM, '| Fluid change', 'same', SAME + ' — PM-02 PM-2.2 8,000 h 패키지의 작동유 교환'),
    (OEM, 'The clogging indicator turns red', 'undefined', UNDEFINED + ' — 막힘 지시기 적색(25 psi)'),
    (OEM, 'Indicator readings taken with fluid below 30 °C are not valid.', 'undefined', UNDEFINED + ' — 냉간 지시 무효'),
    (OEM, 'Carry out the safety steps in Section 1 and confirm that the gauge reads 0 psi.', 'same', SAME + ' — PM-02 SOP-PM-21 1~3단계'),
    (OEM, 'Remove the bowl and the element. Do not clean and reuse paper elements.', 'undefined', UNDEFINED + ' — 종이 엘리먼트 재사용 금지'),
    (OEM, 'If metal particles are visible', 'undefined', UNDEFINED + ' — 금속 입자가 보이면 시료 분석'),
    (OEM, 'Fit a new 10 µm element (part no. HI-RF-10)', 'undefined', UNDEFINED + ' — 엘리먼트 품번 · 보울 조임 토크'),
    (OEM, 'Reset the indicator, restart, and run for 10 minutes.', 'same', SAME + ' — PM-02 SOP-PM-21 5 · 6단계(지시기 초기화 · 누유 점검)'),
    (OEM, 'At operating temperature the differential pressure must be below 10 psi.', 'undefined', UNDEFINED + ' — 교체 뒤 차압 10 psi 미만'),
    (OEM, 'Nominal precharge is 1,450 psi', 'undefined', UNDEFINED + ' — 프리차지 기준값(PM-02 SOP-PM-22 「명판 값」)'),
    (OEM, 'Use dry nitrogen only.', 'undefined', UNDEFINED + ' — 충전 가스'),
    (OEM, 'Check the precharge 2 weeks or 100 operating hours', 'differ', DIFFER + ' — PM-02 PM-2.2 4,000 h 패키지'),
    (OEM, 'If the precharge has fallen by more than 200 psi', 'differ', DIFFER + ' — PM-02 PM-2.2 4,000 h 패키지'),
    (OEM, 'Recharge if the precharge is below 90 % of the nameplate value.', 'undefined', UNDEFINED + ' — 재충전 기준 90 %'),
    (OEM, 'The fluid side must read 0 psi before the charging kit is connected.', 'same', SAME + ' — PM-02 SOP-PM-21 3단계'),
    (OEM, 'Connect the charging kit to the gas valve and read the precharge.', 'undefined', UNDEFINED),
    (OEM, 'Correct the reading to 20 °C with the table on the nameplate.', 'undefined', UNDEFINED),
    (OEM, 'If the corrected value is below 90 % of the nameplate value', 'undefined', UNDEFINED + ' — 재충전 기준 90 %'),
    (OEM, 'Record the corrected value, the date and the hour meter reading', 'undefined', UNDEFINED),
    (OEM, '| Milky or cloudy', 'undefined', UNDEFINED + ' — 작동유 상태 판정 표'),
    (OEM, '| Dark with burnt odour', 'undefined', UNDEFINED + ' — 작동유 상태 판정 표'),
    (OEM, '| Sediment after standing overnight', 'undefined', UNDEFINED + ' — 작동유 상태 판정 표'),
    (OEM, '| Level low', 'undefined', UNDEFINED + ' — 작동유 상태 판정 표'),
    (OEM, '| Level high', 'undefined', UNDEFINED + ' — 작동유 상태 판정 표'),
    (OEM, 'Maximum operating fluid temperature is 70 °C', 'differ', DIFFER + ' — 사내 인터록 한계 65 ℃(HM-8.3 · HM-9.3)'),
    (OEM, 'After any service, run the unit for 15 minutes at working pressure', 'differ', DIFFER + ' — PM-02 PM-2.9 시운전 확인(부하 90 % 15분 · PS1 · FS1 · VS1 기준)'),
    (OEM, 'Record the pump outlet pressure, flow and fluid temperature.', 'differ', DIFFER + ' — PM-02 PM-2.9 시운전 확인'),
    (OEM, 'The oil cooler is an air-blast type.', 'same', SAME + ' — HM-8.4 쿨러 핀 오염(먼지 · 유막)'),
    (OEM, 'Clean the core when the fins are visibly blocked', 'differ', DIFFER + ' — 세척할 때는 HM-8.4 판정(핀 오염) · HM-8.7 근본 조치가 정한다'),
    (OEM, 'Stop the pump, lock out the motor supply, and wait until the fan has stopped.', 'same', SAME + ' — HM-8 1.1 SOP-COOL-14 1단계(정지 · LOCAL · 잠금)'),
    (OEM, 'Inspect the core before cleaning.', 'undefined', UNDEFINED + ' — 세척 전 코어 막힘 · 휨 확인(HM-8 · PM-02에 없음)'),
    (OEM, 'Clean with compressed air or with low-pressure water at no more than 30 psi.', 'differ', DIFFER + ' — HM-8 1.1 SOP-COOL-14 2단계는 압축공기로 세척'),
    (OEM, 'Do not use a high-pressure washer.', 'same', SAME + ' — HM-8 1.1 SOP-COOL-14 2단계(고압수는 쓰지 않는다)'),
    (OEM, 'If blocked areas or bent fins remain after cleaning, replace the core', 'undefined', UNDEFINED + ' — 세척 뒤 막힘 · 휨이 남으면 코어 교체(HM-8 · PM-02에 없음)'),
    (OEM, 'After cleaning or replacement, run the unit at working load for 30 minutes', 'undefined', UNDEFINED + ' — 부하 운전 뒤 쿨러 입구 · 출구 유온 차 확인(HM-8의 완료 기준은 CE 80 %)'),
    # 9장 스캔본(참고 — 종이 원본 1.0판)
    (SCAN, '정상 운전과 경보의 기준은 설비별 정비 매뉴얼을 따른다.', 'same', SAME + ' — HM-8.3'),
    (SCAN, '펌프 부하는 6 0 % 아래로 내리지 않는다', 'same', SAME + ' — HM-8.5 · HM-8.8(펌프 부하 60 %)'),
    (SCAN, '최소 부하 6 0 %는 PLC 부하 설정값의 쓰기 범위 하한이기도 하다.', 'same', SAME + ' — HM-8.5(최소 부하 인터록)'),
    (SCAN, '운전 한계에 닿지 않도록 운전 중에 지킬 금지와 제한이다.', 'old', '1.0판 체계의 절(옛 절차 번호 SOP-COOL-01~03) — 같은 금지 · 제한이 현행 HM-8.8에 있다'),
    (SCAN, '원격 조치(SOP-C0OL-0 1~03)', 'old', '1.0판 체계의 절(옛 절차 번호 SOP-COOL-01~03) — 같은 금지가 현행 HM-8.8에 있다'),
    (SCAN, '팬 100 % 연속 운전이 2 4시간을 넘으면 팬', 'old', '1.0판 체계의 절 — 같은 제한이 현행 HM-8.8에 있다'),
    (SCAN, '운전 중인 설비가 아래 한계에 닿으면', 'same', '사내 기준과 다르게 정하지 않은 운전 한계 — 2회차 설비 모델 센서 한계와 같음'),
    (SCAN, '유온 TS1  6 5 ℃ 초과', 'same', '사내 기준과 다르게 정하지 않은 운전 한계 — HYD-01~03 TS1 한계 65 ℃(경계 낱말 「초과」는 원문대로)'),
    (SCAN, '토출 압력 PS1  130 bar 미만', 'same', '사내 기준과 다르게 정하지 않은 운전 한계 — HYD-01~03 PS1 한계 130 bar'),
    (SCAN, '팬 진동 VS1  2.0 mm/s 이상', 'same', '사내 기준과 다르게 정하지 않은 운전 한계 — HYD-01~03 VS1 한계 2.0 mm/s'),
    (SCAN, '한계는 경보 기준보다 높게 둔다.', 'same', SAME + ' — HM-8.3'),
    (SCAN, '설비가 한계에 닿아 섰으면 운전원은', 'same', '사내 기준과 다르게 정하지 않은 운전 기록'),
    # SR-04 제4조 ①② — 지점5
    (SR, '유압 설비의 실측 유온이 인터록 한계(65 ℃)를 넘으면', 'r4', 'R4의 원문 후보 — 실측 유온의 인터록 정지'),
    (SR, '운전 중에는 인터록 한계에 다가가는 조치를 하지 않는다.', 'r4', 'R4의 원문 후보 — 운전 중 조치'),
]
TASK_LINES = {   # 핀 세척(SOP-COOL-14) 원문 — (자료 파일, 첫 줄 글자, 끝 줄 글자)
    HM11: ('## HM-8.7 근본 조치', '3. 재가동 후 냉각 효율 CE가 80 % 이상으로 돌아왔는지 확인한다.'),
    E.HM10: ('## HM-7.6 쿨러 핀 세척', '3. 재가동 후 냉각 효율 CE가 75 % 이상으로 돌아왔는지 확인한다.'),
    E.HM12: ('## HM-8.7 근본 조치', '3. 재가동 후 냉각 효율 CE가 80 % 이상으로 돌아왔는지 확인한다.'),
    OEM: ('## 7 Oil Cooler / 오일 쿨러', 'The difference must not be less than the value in the commissioning record.'),
}
RULE_LINES = {   # 조건표 조건의 근거 원문 줄(현행 HM-8 1.1) — (rule_id, 글자, 까닭)
    'R1': [('원격 조치는 PLC 운전 모드가 REMOTE_AUTO일 때만 한다.', '원문이 원격 조치(SOP-COOL-11~13)를 REMOTE_AUTO에서만 하게 한다 — 조건표의 대상 · 조건(원격 자동이 아니면 제외)과 같다'),
             ('- 원격 조치(SOP-COOL-11~13)는 REMOTE_AUTO가 아닐 때 쓰지 않는다.', '금지 절이 같은 대상(SOP-COOL-11~13)을 범위로 가리킨다')],
    'R2': [('이미 24시간을 넘겼다면 팬 최대 운전 조치는 팬 수명 손실로 20만 원을 감점해서 비교한다.', '「넘겼다면」은 초과(>)이고 감점 20만 원 · 대상 팬 최대 운전 조치가 조건표와 같다')],
    'R3': [('조치 후 예측 유온이 55 ℃ 이상이면 경보 해제에 실패할 수 있으므로 다른 조치와 비교한다.', '「이상」(>=) · 55 ℃ · 다른 조치와 비교(경고)가 조건표와 같다. 1.2판 초안의 「넘으면」은 승인 전이라 쓰지 않는다')],
}
ORDER = ['differ', 'old', 'r4', 'undefined', 'same']   # 한 후보가 여러 줄에 걸치면 앞 분류가 먼저


def text_of(folder, name):
    return X.decode((Path(folder)/'자료'/name).read_bytes())[0]


def line_of(text, needle, name):
    hits = [n for n, line in enumerate(text.splitlines(), 1) if needle in line]
    if len(hits) != 1:
        raise RuntimeError(f'{name}: 「{needle}」이 원문 {len(hits)}줄에 있습니다 — 한 줄이어야 합니다(원문이 바뀌었으면 표를 고칩니다)')
    return hits[0]


class Lines:
    """자료 파일마다 {줄: (분류, 까닭)}와 핀 세척 원문 줄 범위."""

    def __init__(self, folder):
        self.folder = Path(folder)
        self.texts = {}
        self.cls = {}
        for name, needle, kind, why in LINES:
            text = self.text(name)
            self.cls.setdefault(name, {})[line_of(text, needle, name)] = (kind, why)
        self.task = {name: (line_of(self.text(name), a, name), line_of(self.text(name), b, name)) for name, (a, b) in TASK_LINES.items()}

    def text(self, name):
        if name not in self.texts:
            self.texts[name] = text_of(self.folder, name)
        return self.texts[name]

    def kinds(self, name, c):
        return [self.cls.get(name, {}).get(n) for n in range(c['line_start'], c['line_end'] + 1) if self.cls.get(name, {}).get(n)]

    def is_task(self, name, c):
        span = self.task.get(name)
        return bool(span) and span[0] <= c['line_start'] and c['line_end'] <= span[1]


def value_digits(text):
    m = re.search(r'\d(?:[ ,]?\d)*(?:\.\d+)?', text or '')
    return X.number(m.group().replace(',', '')) if m else None


KIND_KO = {'step': '단계', 'precondition': '시작 조건 · 승인', 'prohibition': '금지 · 제한', 'completion': '완료 기준', 'unit_value': '기준값'}
KIND_AS = {'step': '단계로', 'precondition': '시작 조건 · 승인으로', 'prohibition': '금지 · 제한으로', 'completion': '완료 기준으로', 'unit_value': '기준값으로'}
CMP_KO = {None: '비교 없음', '>=': '이상', '>': '초과', '<=': '이하', '<': '미만', '=': '같음', 'range': '범위', '±': '허용 오차'}
STATUS_KO = {'현행': '현행 판이라 작업 근거다(DC-01 DC-3)', '보충': '보충 문서라 기존 문서를 대체하지 않고 더한다(DC-01 DC-3)'}
OUT_OF_SCOPE = '이 줄에는 검토자가 원문에서 적은 기대 항목이 없어, 사람이 이 후보를 원문과 대조해 결정하지 않았다 — 적재하지 않고 다음 검토로 남긴다'
LEAD = re.compile(r'^\s*(?:\d+\.\s+|[-*]\s+|[①②③④⑤⑥⑦⑧⑨]\s*)?(?:(?:EN|KO):\s*)?')
EXCLUDE = {}


def bare(text):
    """인용 줄마다 앞머리(목록 번호 「N. 」 · 글머리 「- 」 · 원문자 · 「EN:」 · 「KO:」)를 걷은 글 — 기대 항목과 견줄 때만 쓴다(인용은 그대로 둔다)."""
    return '\n'.join(LEAD.sub('', x, count=1) for x in str(text).split('\n'))


def bkey(text):
    return X.squash(bare(text))


for _f, _q, _vt, _why in E.EXCLUDE:
    EXCLUDE.setdefault(_f, []).append((bkey(_q), _vt, _why))


def span(lo, hi):
    return f'{lo}줄' if lo == hi else f'{lo}~{hi}줄'


def same_value(c, i):
    return (c.get('value') == i.get('value') and str(c.get('unit')) == str(i.get('unit'))
            and c.get('comparator') == i.get('comparator') and c.get('value_max') == i.get('value_max'))


def near_items(c, items):
    return [i for i in items if i['line_start'] <= c['line_end'] and c['line_start'] <= i['line_end']]


def compare(c, items):
    """후보 하나를 그 파일의 기대 항목과 견준다 → (꼴, 항목, 고칠 것). 인용은 앞머리(bare)를 걷고 글자 · 숫자만 남겨 견준다.
    꼴: same(같음) · fix(같은 항목인데 비교 · 범위 · 절 표기가 다름 — 고칠 것) · bound(같은 종류 · 같은 값의 한 줄 문장 항목인데 인용 경계만 다름 —
    인용이 그 문장을 품은 여러 문장이거나 그 문장의 일부(기준값 조각 · 문장의 절반 넘는 부분), 인용 · 줄을 그 문장으로 고칠 것) ·
    kind(같은 원문을 다른 종류로 뽑음) · fragment(원문 문장의 작은 조각) · value(그 줄의 기준값 항목 어느 것과도 값 · 단위가 다름) · None(그 줄에 견줄 항목 없음)."""
    key = bkey(c['quote'])
    near = near_items(c, items)
    if not key or not near:
        return None, None, None
    unit = c['kind'] == 'unit_value'
    # 같은 글이 원문 여러 곳에 있어 앞 줄을 붙여 정한 항목(said > 1)은, 후보가 그 끝 줄 하나를 인용했고(번호까지 옮겨 한 곳으로 정해짐) 그 줄 글이 같으면 같은 항목이다
    kinds = [i for i in near if i['kind'] == c['kind'] and (i['key'] == key or (i['said'] > 1 and c['line_start'] == c['line_end'] == i['line_end'] and i['tail'] == key))]
    if unit:
        for i in kinds:
            if same_value(c, i):
                return place(c, i)
        for i in kinds:
            if c.get('value') == i['value'] and str(c.get('unit')) == i['unit']:
                form, item, more = place(c, i)
                return 'fix', item, {**more, **{k: i.get(k) for k in ('comparator', 'value_max') if c.get(k) != i.get(k)}}
    elif kinds:
        return place(c, kinds[0])
    inner = [i for i in near if i['kind'] == c['kind'] and i['said'] == 1 and i['key'] != key
             and (i['key'] in key or (key in i['key'] and (unit or len(key) * 2 >= len(i['key']))))]
    if unit:
        inner = sorted((i for i in inner if c.get('value') == i['value'] and str(c.get('unit')) == i['unit']
                        and (key in i['key'] or str(c.get('value_text') or '') in i['quote'])), key=lambda i: c.get('comparator') != i.get('comparator'))
    if inner:
        i = inner[0]
        _, item, more = place(c, i)
        fix = {**more, 'quote': i['quote'], 'line_start': i['line_start'], 'line_end': i['line_end']}
        if unit:
            fix.update({k: i.get(k) for k in ('comparator', 'value_max') if c.get(k) != i.get(k)})
        if c.get('quote_match') != 'exact':
            fix['quote_match'] = 'exact'
        return 'bound', item, fix
    other = [i for i in near if i['kind'] != c['kind'] and (i['key'] == key or i['key'] in key or key in i['key'])]
    if other:
        return 'kind', other, None
    whole = [i for i in near if i['kind'] == c['kind'] and key in i['key']]
    if whole and not unit:
        return 'fragment', whole[0], None
    if unit and any(i['kind'] == 'unit_value' for i in near):
        return 'value', [i for i in near if i['kind'] == 'unit_value'], None
    return None, None, None


def place(c, i):
    """같은 항목인데 절 · 절차 표기가 다르면 고칠 것으로."""
    fix = {k: i[k] for k in ('section', 'procedure') if c.get(k) != i[k]}
    return ('fix' if fix else 'same'), i, fix


def covers(c, i):
    """검토가 후보 c를 기대 항목 i와 같은 것으로 보는가(채택 · 고쳐 채택의 대상)."""
    form, item, _ = compare(c, [i])
    return form in ('same', 'fix', 'bound')


def structure(name, c, lines):
    """원문 구조에서 바로 보이는 잘못 — 있으면 빼는 까닭, 없으면 None."""
    text = lines.text(name).splitlines()
    said = [x for x in text[c['line_start'] - 1:c['line_end']] if x.strip() and not x.lstrip().startswith('#')]
    if len(said) > 1:
        return (f'인용이 {span(c["line_start"], c["line_end"])}의 서로 다른 줄 {len(said)}개(빈 줄 · 절 머리 빼고)에 걸쳐 있어, 이 후보 하나가 다른 단계 · 줄의 글까지 '
                f'근거로 삼는다 — 한 줄 근거로 적재할 수 없어 뺀다')
    q = c['quote']
    if q.count('(') != q.count(')'):
        return f'조각 — 괄호가 닫히지 않은 채 끝난 인용이라 원문 {c["line_start"]}줄 문장의 일부만 담았다'
    if c['kind'] == 'unit_value' and c.get('value_text') and c['value_text'] in q:
        before = q[:q.index(c['value_text'])]
        if re.search(r'\d[\d,.]*\s*·\s*$', before):
            head, _, part = str(c.get('text', '')).partition(': ')
            return (f'「{head.split(" · ", 1)[-1] if part else "나열한 칸"}」에 나열한 숫자({part or before.strip() + " " + c["value_text"]})의 마지막 것만 기준값으로 뽑았다 '
                    f'— 나열한 차례 하나이지 기준값이 아니다')
    return None


def told_items(items):
    return ' · '.join(dict.fromkeys(f'{KIND_KO[i["kind"]]}({i["note"]})' for i in items))


def decide(name, status, c, lines, items, p5, p6, used=None):
    """(결정, 까닭, 고칠 것, 대조한 기대 항목) — 한 후보. 결정 = 채택 · 수정 · 제외 · 보류. 기대 항목은 누락 셈에 쓴다(대조가 된 항목).
    used = {id(기대 항목): 그 항목을 먼저 담은 후보 id} — 같은 항목을 담은 다음 후보는 중복으로 뺀다."""
    form, item, fix = compare(c, items)
    seen = item if form in ('same', 'fix', 'bound') else None
    if status == '폐기':
        return '제외', '문서 상태 폐기 — DC-01 DC-3 「지난 기록을 해석할 때만」(1.1판으로 대체됨). 옛 작업지시를 현행 번호로 읽을 때만 쓴다', None, seen
    if status.startswith('개정 요청'):
        return '제외', '문서 상태 개정 요청(미승인) — DC-01 DC-3 「승인 전에는 작업 근거가 아니다」', None, seen
    key = bkey(c['quote'])
    for q, vt, why in EXCLUDE.get(name, []):
        if (q == key or (seen is None and key and key in q)) and (vt is None or vt == c.get('value_text')):
            return '제외', why, None, None
    if seen is not None and used is not None and id(seen) in used:
        return '제외', f'같은 원문 항목({seen["note"]})을 앞 후보 {used[id(seen)]}가 이미 담았다 — 같은 지식을 두 번 적재하지 않는다', None, None
    if form != 'bound':
        bad = structure(name, c, lines)
        if bad:
            return '제외', bad, None, seen
    if form == 'fragment':
        return '제외', f'조각 — 원문 {item["line_start"]}줄 문장 「{item["quote"][:50]}」의 일부만 인용했다', None, None
    if form == 'kind':
        return '제외', f'같은 원문 줄({span(c["line_start"], c["line_end"])})을 {KIND_AS[c["kind"]]} 뽑았다 — 검토자가 읽은 원문 문맥은 {told_items(item)}', None, None
    at = item if seen is not None else c
    found = lines.kinds(name, at)
    rule = sorted(found, key=lambda x: ORDER.index(x[0]))[0] if found else None
    if seen is None:
        if rule and rule[0] in ('differ', 'old'):
            return '제외', rule[1], None, None
        if rule and rule[0] == 'undefined' and p6 == '가':
            return '보류', rule[1] + ' — 적용할지 HM-8 소유 부서(설비보전팀)에 묻는다', None, None
        if rule and rule[0] == 'undefined':
            return '보류', rule[1] + ' — 핀 세척 밖의 항목이라 이번 검토에서 적용 여부를 정하지 않았다(종류 · 값을 원문과 대조하지 않아 적재하지 않는다)', None, None
        if rule:
            return '보류', f'{rule[1]} — 이 후보의 종류 · 값은 기대 항목에 없어 원문과 대조하지 않았다(적재하지 않는다)', None, None
        if form == 'value':
            vals = ' · '.join(dict.fromkeys(f'{i["value"]}{"~" + str(i["value_max"]) if i.get("value_max") is not None else ""} {i["unit"]}' for i in item))
            return ('보류', f'원문 {span(c["line_start"], c["line_end"])}에서 검토자가 적은 기준값은 {vals}이고, 이 후보의 값 · 단위({c.get("value")} {c.get("unit")})는 '
                    f'그 가운데 없어 원문과 대조하지 않았다 — 적재하지 않는다', None, None)
        near = near_items(c, items)
        if near:
            return ('보류', f'원문 {span(c["line_start"], c["line_end"])}에서 검토자가 적은 항목은 {told_items(near)}이고, 이 후보의 인용은 그 어느 것과도 맞지 않아 '
                    f'원문과 대조하지 않았다 — 적재하지 않는다', None, None)
        return '보류', OUT_OF_SCOPE, None, None
    unit = c['kind'] == 'unit_value'
    where = span(item['line_start'], item['line_end'])
    if form == 'bound':
        same = f'원문 {where}의 기대 항목과 종류' + (' · 값 · 단위가' if unit else '가') + ' 같고 인용 경계만 다르다'
    else:
        same = (f'원문 {where}과 절 · 종류' + ((' · 값 · 단위 · 비교가' if form == 'same' else ' · 값 · 단위가') if unit else '가') + ' 기대 항목과 같다'
                + (' — 인용 앞의 번호 · 글머리 · 언어 표시는 원문 줄 그대로라 빼고 견줌' if bare(c['quote']) != c['quote'] else ''))
    note = item['note']
    if rule:
        kind, why = rule
        if kind in ('differ', 'old'):
            return '제외', why, None, seen
        if kind == 'r4' and p5 == '다':
            return '보류', why + ' — 예측값 · 작업지시 후보에 걸리는지 안전관리 담당의 해석을 받기 전까지 둔다', None, seen
        if kind == 'undefined':
            if p6 == '가':
                return '보류', why + ' — 적용할지 HM-8 소유 부서(설비보전팀)에 묻는다', None, seen
            return accept(f'{note} — {why} — 사내 기준이 정하지 않았으므로 제조사 지침대로 더한다 · {same}', c, fix, seen)
        return accept(f'{note} — {why} · {same}', c, fix, seen)
    if status.startswith('참고'):
        if p6 == '가':
            return '보류', f'{note} — {UNDEFINED} — 적용할지 소유 부서에 묻는다', None, seen
        return accept(f'{note} — {UNDEFINED} — 제조사 지침대로 더한다 · {same}', c, fix, seen)
    return accept(f'{note} — {same} · {STATUS_KO.get(status, "문서 상태 " + status)}', c, fix, seen)


def accept(why, c, fix, item):
    """채택 — 고칠 것이 있으면 수정(고친 까닭을 덧붙임). 기준값 글의 숫자와 value가 다르면 그것도 고친다."""
    fix = dict(fix or {})
    if c['kind'] == 'unit_value':
        digits = value_digits(c.get('value_text'))
        if digits is not None and digits != c.get('value') and 'value' not in fix:
            fix['value'] = digits
    if not fix:
        return '채택', why, None, item
    told = []
    for k, new in fix.items():
        old = c.get(k)
        if k == 'comparator':
            told.append(f'비교는 원문 「{c.get("value_text")}」의 문맥대로 {CMP_KO.get(new, new)}({new})라 {old!r}를 고침')
        elif k == 'value':
            told.append(f'값을 원문 글자 「{c.get("value_text")}」대로 {old}에서 {new}로 고침')
        elif k == 'quote':
            what = '그 문장을 품은 여러 문장' if bkey(new) in bkey(old) else '그 문장의 일부'
            told.append(f'인용이 {what}이라 원문 {span(fix.get("line_start", c["line_start"]), fix.get("line_end", c["line_end"]))}의 그 문장 그대로로 고침')
        elif k in ('line_start', 'line_end', 'quote_match'):
            continue
        else:
            told.append(f'{k}를 원문 표기 {new!r}로 고침({old!r})')
    return '수정', why + ' — ' + ' · '.join(told), fix, item


def overlap(a, b):
    """두 인용이 같은 원문을 가리키는가 — 글자 · 숫자만 남겨 한쪽이 다른 쪽을 품는다(짧은 쪽 8자 이상)."""
    x, y = X.squash(a), X.squash(b)
    return bool(x and y) and (x == y or (min(len(x), len(y)) >= 6 and (x in y or y in x)))


def matches(c, item):
    """후보 하나가 기대 항목 하나와 같은 것인가 — 종류가 같고(값 항목이면 값 · 단위도), 줄이 겹치고, 인용이 서로를 품는다."""
    if c['kind'] != item['kind'] or not overlap(c['quote'], item['quote']):
        return False
    if not (c['line_start'] <= item['line_end'] and item['line_start'] <= c['line_end']):
        return False
    if item['kind'] == 'unit_value':
        return c.get('value') == item['value'] and str(c.get('unit')) == item['unit']
    return True


TARGETS = E.MAIN_TARGET | {HM11, E.PM, E.PR, E.HI}   # 「주 대상 문서에 실행」 · 「다른 문서에 다시 적용」 단계(기준선 · 다른 문서) — 문서 관리 기준은 추출 대상이 아니다


def baseline(folder):
    """검토된 기준선 — 받은 sop.json(앞 단계의 검증 판 — 통합 3회차 · 실전 2회차 조치 조건표 랩)이 HM-8 1.1을 구조로 옮긴 항목 가운데 원문 글자 그대로인 것(단계 · 조건 문장).
    검토자 메모는 반을 가리지 않게 「받은 SOP 구조(입력/sop.json)」로 적는다.
    단계는 그 절차 머리(### SOP-…) 아래의 번호 줄에서 찾는다 — 같은 글의 단계가 여러 절차에 있어도 그 절차의 줄로 정한다."""
    sop = json.loads((Path(folder)/'입력/sop.json').read_text(encoding='utf-8'))
    text = text_of(folder, HM11)
    lines = text.splitlines()
    rows, seen = [], set()
    for s in sop['sops']:
        head = next(n for n, l in enumerate(lines, 1) if re.match(r'^###\s+' + re.escape(s['id']) + r'\b', l))
        for st in s['steps']:
            at = next(n for n in range(head + 1, len(lines) + 1) if re.match(rf'^\s*{st["order"]}\.\s', lines[n - 1]) and st['text'] in lines[n - 1])
            rows.append((HM11, s['source'], s['id'], 'step', st['text'], None, f'받은 SOP 구조(입력/sop.json) {s["id"]} {st["order"]}단계와 같은 원문', at))
        for key, kind in [('apply_conditions', 'precondition'), ('prohibitions', 'prohibition'), ('completion', 'completion')]:
            for it in s[key]:
                for part in X.sentences(it['text']):
                    if part in text and text.count(part) == 1 and part not in seen:
                        seen.add(part)
                        rows.append((HM11, s['source'], None, kind, part, None, f'받은 SOP 구조(입력/sop.json) {s["id"]} {key}와 같은 원문', None))
    return rows


def anchor(doc_lines, section, procedure):
    """항목의 절차 · 절 머리 줄 — 같은 글이 여러 절차에 있으면 그 머리 아래 첫 줄로 정한다(없으면 1)."""
    for pat in ([rf'^###\s+{re.escape(procedure)}\b'] if procedure else []) + [rf'^##\s+{re.escape(section)}(\s|$)', rf'^{re.escape(section)}(\(|\s)']:
        for n, l in enumerate(doc_lines, 1):
            if re.match(pat, l.strip()) and '....' not in l:
                return n
    return 1


def expected(folder):
    """기대 항목에 줄 번호를 붙인다 — 추출 후보와 같은 규칙(원문 한 곳에 맞을 때까지 앞 줄을 붙임). HM-8 1.1 단계는 받은 sop.json(기준선)에서.
    항목마다 key(앞머리를 걷은 인용의 글자 · 숫자) · said(인용이 걸친 원문 문장 줄 수 — 절 머리 줄 빼고) · tail(끝 줄의 key)과 note(검토자 메모 — 채택 이유의 앞머리)를 단다."""
    out, seen = [], set()
    hand = {(r[0], X.squash(r[4])) for r in E.ITEMS}
    rows = [tuple(r) + (None,) * (8 - len(r)) for r in E.ITEMS]
    rows += [r for r in baseline(folder) if r[3] == 'step' or (r[0], X.squash(r[4])) not in hand]   # 손으로 적은 항목이 sop.json 조건 문장보다 먼저
    for row in rows:
        name, section, procedure, kind, quote, val, note, at = row
        text = text_of(folder, name)
        doc = X.Doc(text, name == E.SCAN)
        hits = [n for n, line in enumerate(doc.lines, 1) if quote.split('\n')[0] in line]
        if len(hits) < 1:
            raise RuntimeError(f'기대 항목의 인용이 원문에 없습니다: {name} {quote}')
        start = anchor(doc.lines, section, procedure)
        line = at or next((n for n in hits if n >= start), hits[-1])
        located = doc.locate(line, line, quote) if '\n' not in quote else None
        if located is None:
            first = hits[0]
            n_lines = quote.count('\n')
            located = (quote, first, first + n_lines, 'exact') if quote in text and text.count(quote) == 1 else None
        if located is None:
            raise RuntimeError(f'기대 항목의 인용이 원문 한 곳으로 정해지지 않습니다: {name} {quote}')
        q, ls, le, _ = located
        ident = (name, kind, X.squash(q), ls, json.dumps(val, sort_keys=True))
        if ident in seen:
            continue
        seen.add(ident)
        said = sum(1 for x in doc.lines[ls - 1:le] if x.strip() and not x.lstrip().startswith('#'))
        out.append({'file': name, 'section': section, 'procedure': procedure, 'kind': kind, 'quote': q, 'line_start': ls, 'line_end': le,
                    'negation': bool(re.search(r'않|Do not|Never|must not|not valid', q)), 'key': bkey(q), 'said': said, 'tail': bkey(q.split('\n')[-1]),
                    'note': note or f'{section} {KIND_KO[kind] if kind in KIND_KO else kind}', **(val or {})})
    return out


def score(cands_by_file, items):
    """기대 항목과 후보의 겹침 — 문서마다 기대 수 · 맞은 수 · 누락 · 값이 글과 다른 후보 · 기대 절 안의 기대 밖 후보."""
    out = {}
    for name in sorted({i['file'] for i in items}):
        data = cands_by_file.get(name)
        exp = [i for i in items if i['file'] == name and i['kind'] != 'toc']
        cands = data['candidates'] if data else []
        missing = [i for i in exp if not any(matches(c, i) for c in cands)]
        bad_value = [c['id'] for c in cands if c['kind'] == 'unit_value' and value_digits(c.get('value_text')) != c.get('value')]
        sections = {(i['section'], i['procedure']) for i in exp}
        outside = [c['id'] for c in cands if (c['section'], c['procedure']) in sections and not any(matches(c, i) for i in exp)]
        out[name] = {'expected': len(exp), 'matched': len(exp) - len(missing), 'missing': [f'{i["section"]} {i["procedure"] or ""} {i["kind"]} 「{i["quote"][:40]}」'.replace('  ', ' ') for i in missing],
                     'candidates': len(cands), 'value_differs_from_text': bad_value, 'outside_expected_in_same_section': len(outside)}
    return out


def stem_of(data):
    return f'{data["doc_id"]}_{data["rev"]}' if data['rev'] else data['doc_id']


def relocate(name, cand, lines):
    """고친 줄에 맞춰 쪽(스캔본) · 말(영한 문서)을 다시 읽는다."""
    text_lines = lines.text(name).splitlines()
    if 'page' in cand:
        cand['page'] = X.Doc(lines.text(name), True).page.get(cand['line_end'])
    if 'lang' in cand:
        said = {m.group(1) for x in text_lines[cand['line_start'] - 1:cand['line_end']] for m in [re.match(r'^\s*(?:\d+\.\s*)?(EN|KO):', x)] if m}
        if len(said) == 1:
            cand['lang'] = said.pop().lower()


def why_missing(i, cands, unlocated):
    """기대 항목 하나가 누락인 까닭 — 같은 원문을 다른 종류로 뽑은 후보, 이 문장을 다른 문장과 한 인용에 담은 후보, 원문 여러 곳에 맞아 줄을 정하지 못한
    같은 글의 후보를 id로 든다(cands = 모델 답에서 온 후보만). 그런 후보가 없을 때만 「원문에 있는데 후보가 없음」."""
    def related(key):
        return bool(key) and (key == i['key'] or key in i['key'] or i['key'] in key)
    near = [c for c in cands if c['line_start'] <= i['line_end'] and i['line_start'] <= c['line_end'] and related(bkey(c.get('before', {}).get('quote', c['quote'])))]
    other = [c for c in near if c['kind'] != i['kind']]
    bundled = [c for c in near if c['kind'] == i['kind']]
    lost = [u for u in unlocated if u.get('kind') == i['kind'] and u.get('procedure') in (None, i['procedure']) and related(bkey(u.get('quote', '')))]
    said = []
    if other:
        said.append(f'후보 {", ".join(c["id"] for c in other)}가 같은 원문을 {" · ".join(dict.fromkeys(KIND_KO[c["kind"]] for c in other))} 종류로 뽑았고 '
                    f'{KIND_KO[i["kind"]]} 종류로 뽑은 후보는 없음')
    if bundled:
        said.append(f'후보 {", ".join(c["id"] for c in bundled)}가 이 문장을 다른 문장과 한 인용에 담아(그 후보는 '
                    f'{" · ".join(dict.fromkeys(c["decision"] for c in bundled))}) 이 문장 하나를 담은 후보가 없음')
    if lost:
        said.append(f'후보 {", ".join(u["id"] for u in lost)}가 같은 글을 냈지만 원문 여러 곳에 맞아 줄을 정하지 못해 후보에서 빠짐(unlocated)')
    return ' · '.join(said) or '원문에 있는데 후보가 없음'


def review_one(folder, data, cand_bytes, lines, items, p5, p6, own, course, reviewed_at=REVIEWED_AT):
    """후보 파일 하나 → 검토 결과 파일(dict). own = 내 입력의 3회차 지점2 갈래(None이면 제공 입력).
    reviewed_at — 검토 시각. 수업 모델 실행의 후보면 그 후보 파일을 만든 뒤의 시각을 준다(기본은 두 번째 구현 후보의 사례 시각)."""
    name = data['source_file']
    out = copy.deepcopy(data)
    stem = stem_of(data)
    decisions = []
    reviewed = []
    STATUS = {'채택': 'approved', '수정': 'approved', '제외': 'excluded', '보류': 'pending'}
    exp = [i for i in items if i['file'] == name and i['kind'] != 'toc']
    used = {}
    for c in out['candidates']:
        dec, why, fix, item = decide(name, data['doc_status'], c, lines, exp, p5, p6, used)
        if item is not None:
            used.setdefault(id(item), c['id'])
        c2 = dict(c, decision=dec, status=STATUS[dec], reason=why, origin='extractor')
        if fix:
            c2.update(fix, before={k: c.get(k) for k in fix})
            relocate(name, c2, lines)
        reviewed.append(c2)
    missing = []
    text_lines = lines.text(name).splitlines()
    n = 0
    from_model = list(reviewed)
    for i in [i for i in exp if id(i) not in used]:
        note = why_missing(i, from_model, data.get('unlocated') or [])
        entry = {'section': i['section'], 'procedure': i['procedure'], 'kind': i['kind'], 'quote': i['quote'], 'line_start': i['line_start'],
                 'line_end': i['line_end'], 'note': note, 'added': True}
        if i['said'] > 1:      # 원문 여러 곳에 같은 글 — 앞 줄을 붙여야 한 곳으로 정해지므로 한 줄 근거 후보로 더하지 않는다
            missing.append(entry | {'note': note + ' — 같은 글이 원문 여러 곳에 있어 한 줄 근거로 정해지지 않아 후보로 더하지 않음', 'added': False})
            continue
        n += 1
        cand = {'id': f'{data["doc_id"]}-R{n:02d}', 'section': i['section'], 'procedure': i['procedure'], 'kind': i['kind'],
                'text': i['quote'].split('\n')[-1].strip(), 'quote': i['quote'], 'quote_match': 'exact', 'line_start': i['line_start'], 'line_end': i['line_end']}
        if data['doc_status'] == '참고(스캔본)':
            cand['page'] = X.Doc(lines.text(name), True).page.get(i['line_end'])
        if 'lang' in (data['candidates'][0] if data['candidates'] else {}):
            cand['lang'] = 'en'
        cand['refs'] = []
        cand['status'] = 'pending'
        if i['kind'] == 'step':
            m = re.match(r'^\s*(\d+)\.', text_lines[i['line_end'] - 1])
            cand['order'] = int(m.group(1)) if m else 1
        if i['kind'] == 'unit_value':
            cand.update({k: i[k] for k in ('value', 'value_max', 'unit', 'comparator') if k in i})
            # 그 단위의 첫 조각이 기대 항목의 값이면 그 조각, 아니면(표의 정상 · 경보 · 정지 칸처럼 한 줄에 같은 단위 값이 여럿, 범위, 스캔본 띄어쓰기)
            # 원문 값 읽기(extract_reference.values)에서 기대 항목의 값 · 단위와 같은 조각 — 첫 조각을 그대로 쓰면 다른 칸의 값으로 「고쳐」 채택하게 된다
            first = re.search(r'[\d.,\s]+\s*' + re.escape(i['unit']) + r'[^\s,.)]*', i['quote']).group().strip()
            cand['value_text'] = first if value_digits(first) == i['value'] else next(
                v['value_text'] for v in X.values(i['quote'], name == SCAN) if v['value'] == i['value'] and v['unit'] == i['unit'])
        dec, why, fix, _ = decide(name, data['doc_status'], cand, lines, exp, p5, p6)
        cand.update(decision=dec, status=STATUS[dec], reason=why + ' — 이 항목을 담은 후보가 없어(까닭은 missing의 note) 검토자가 원문 문장으로 더함', origin='reviewer')
        if fix:
            cand.update(fix, before={k: cand.get(k) for k in fix})
        reviewed.append(cand)
        missing.append(entry)
    out['candidates'] = reviewed
    out['missing'] = missing
    out['rule_links'] = rule_links(name, reviewed, lines, p5, own, course)
    decisions.append('판 기준: 문서 목록의 상태와 DC-01 DC-3의 뜻대로 — 현행은 작업 근거, 폐기는 지난 기록 해석에만, 개정 요청(미승인)은 작업 근거가 아님, 보충은 대체 아님, '
                     '참고(제조사 · 스캔본)는 사내 기준과 다르게 정한 항목이면 사내 기준을 따름.')
    if name == OEM:
        decisions.append('사내 기준이 정하지 않은 제조사 항목: ' + ('적용할지 HM-8 소유 부서에 묻기 전까지 보류한다.' if p6 == '가' else '까닭을 적고 채택한다(사내 기준이 정하지 않은 항목이라 제조사 지침대로 더함).'))
    if name == SR:
        decisions.append({'가': '조건의 근거: 제4조 ①②를 예측 유온 제외 조건 전체(작업지시 후보 포함)의 근거로 둔다 — 작업지시만 걸고 운전을 그대로 두는 것도 한계에 다가가는 조치로 본다.',
                          '나': '조건의 근거: 제4조 ①②는 실측 유온의 정지와 운전 중 조치를 말하므로 운전 중 제어 후보의 근거로만 둔다 — 작업지시 후보의 예측 유온 제외는 근거 원문을 찾지 못했다(조건표 변경 요청).',
                          '다': '조건의 근거: 제4조 ①②가 예측값 · 작업지시 후보에 걸리는지 안전관리 담당의 해석을 받기 전까지 보류한다.'}[p5])
    out['review'] = {'reviewer': REVIEWER, 'reviewed_at': reviewed_at, 'candidates_file': f'결과/후보/{stem}.json',
                     'candidates_sha256': hashlib.sha256(cand_bytes).hexdigest(), 'selected_task': TASK if course == '실전반' else None, 'decisions': decisions}
    order = ['doc_id', 'rev', 'doc_status', 'source_file', 'source_sha256', 'encoding', 'extractor', 'generated_at', 'model_run', 'review', 'candidates', 'unlocated', 'warnings', 'missing', 'rule_links']
    return {k: out[k] for k in order if k in out}


def covering(cands, text, needle):
    hits = [c['id'] for c in cands if needle in c['quote'] or X.squash(needle) in X.squash(c['quote'])]
    line = next(n for n, l in enumerate(text.splitlines(), 1) if needle in l)
    near = [c['id'] for c in cands if c['line_start'] <= line <= c['line_end'] and c['kind'] != 'unit_value']
    found = sorted(set(hits) & set(near) or set(near), key=lambda x: [c['id'] for c in cands].index(x))
    ok = [x for x in found if next(c for c in cands if c['id'] == x)['status'] == 'approved']
    return ok or found       # 근거 후보는 승인한 것을 먼저 — 승인한 것이 없으면(보류 갈래) 덮는 후보 그대로


R4_ID = {None: 'R4', '나': 'R4', '다': 'rule:ts1-hard'}
R5_ID = {None: 'R5', '나': 'R5', '다': 'rule:trip-reset-only'}


def rule_links(name, cands, lines, p5, own, course='통합반'):
    """조건 근거 대조. 실전반은 이 작업(SOP-COOL-14)에 걸린 조건(R4 · R5, 옛 규칙 id 포함)만 — 실전 R36 「선택한 작업의 준비 · 금지 · 완료」(R1~R3은 제어 후보에만 걸린다)."""
    text = lines.text(name)
    out = []
    if name == HM11 and course != '실전반':
        for rid, rows in RULE_LINES.items():
            ids = []
            for needle, _ in rows:
                ids += [x for x in covering(cands, text, needle) if x not in ids]
            out.append({'rule_id': rid, 'candidates': ids, 'match': '일치', 'note': ' / '.join(why for _, why in rows)})
    if name == SR:
        ids = covering(cands, text, '유압 설비의 실측 유온이 인터록 한계(65 ℃)를 넘으면') + covering(cands, text, '운전 중에는 인터록 한계에 다가가는 조치를 하지 않는다.')
        base = '원문은 실측 유온이 인터록 한계를 넘으면 설비가 정지한다는 것과 운전 중에 한계에 다가가는 조치를 하지 않는다는 것을 말한다 — 예측 유온 · 작업지시는 말하지 않는다. '
        if own is None:      # 제공 입력 — R4는 네 후보(작업지시 SOP-COOL-14 포함)에 걸림
            link = {'가': ('일치', base + '작업지시만 걸고 지금 설정으로 운전을 그대로 두는 것도 한계에 다가가는 조치로 보아, 네 후보 모두의 근거로 둔다(조건표 출처 칸 고침 요청).'),
                    '나': ('불일치', base + '운전 중 제어 후보(SOP-COOL-11~13)의 근거로는 맞지만, 작업지시 후보(SOP-COOL-14)에 거는 근거는 없다(조건표에서 SOP-COOL-14 빼기 요청).'),
                    '다': ('보류', base + '예측값 · 작업지시 후보에 걸리는지 안전관리 담당의 해석을 받기 전까지 출처를 미확인으로 둔다.')}[p5]
        elif own == '나':    # 내 입력 — R4가 제어 후보(11~13)에만 걸림
            link = {'가': ('불일치', base + '작업지시만 걸고 운전을 그대로 두는 것도 한계에 다가가는 조치로 보므로, 조건표가 SOP-COOL-14를 빠뜨렸다(SOP-COOL-14에 더하기 요청).'),
                    '나': ('일치', base + '운전 중 제어 후보(SOP-COOL-11~13)에만 거는 조건표와 원문의 범위가 같다.'),
                    '다': ('보류', base + '작업지시 후보에도 걸어야 하는지 안전관리 담당의 해석을 받기 전까지 둔다.')}[p5]
        else:                # 내 입력 — 옛 규칙을 옮기지 않음(조건표에 R4 · R5가 없음)
            link = {'가': ('일치', base + '옮기지 않은 옛 규칙(예측 유온 65 ℃ 이상 제외)을 네 후보 모두에 다시 넣을 근거로 둔다(조건표에 다시 넣기 요청).'),
                    '나': ('일치', base + '옮기지 않은 옛 규칙을 운전 중 제어 후보(SOP-COOL-11~13)에만 다시 넣을 근거로 둔다(조건표에 다시 넣기 요청).'),
                    '다': ('보류', base + '다시 넣을지 안전관리 담당의 해석을 받기 전까지 둔다.')}[p5]
        out.append({'rule_id': R4_ID[own], 'candidates': ids, 'match': link[0], 'note': link[1]})
    if name == SCAN:
        toc = next(n for n, l in enumerate(text.splitlines(), 1) if 'HM-9.4 트립 후 복귀' in l)
        out.append({'rule_id': R5_ID[own], 'candidates': [], 'match': '원문 없음',
                    'note': f'출처가 가리키는 HM-9.4(트립 후 복귀)는 목차 {toc}줄에 9-7쪽으로만 있고, 스캔에 그 쪽이 없다(쪽 꼬리 9-6 다음이 9-8) — '
                            '설비안전규정 제4조 ③도 복귀를 HM-9.4로 보낸다. 원본(정비실 보관 종이 문서) 확인을 요청한다.'})
    return out


def judge_changes(judged, p5, own):
    """정한 갈래대로 두면 판정이 달라지는 지난 경보(판정 결과에서 코드로 셈)."""
    events = judged['events']
    def fc(c):
        return (c.get('inputs') or {}).get('forecast_ts1')
    rows = []
    for e in events:
        for c in e['candidates']:
            ex = [x['rule_id'] for x in c.get('exclusions', [])] if 'exclusions' in c else [x['rule_id'] for x in c.get('reasons', []) if x.get('result') == 'EXCLUDE']
            hot = fc(c) is not None and fc(c) >= 65
            if own is None and c['sop'] == TASK and ex == ['R4']:
                rows.append((e['id'], c['sop'], fc(c), {'가': '제외 그대로', '나': '유지 — 비교에 들어옴', '다': '제외 그대로(근거 확인 중)'}[p5]))
            elif own == '나' and c['sop'] == TASK and hot:
                rows.append((e['id'], c['sop'], fc(c), {'가': '제외 — R4를 더하면', '나': '유지 그대로', '다': '유지 그대로(근거 확인 중)'}[p5]))
            elif own == '다' and hot and (c['sop'] in ('SOP-COOL-11', 'SOP-COOL-12', 'SOP-COOL-13') or (c['sop'] == TASK and p5 == '가')):
                rows.append((e['id'], c['sop'], fc(c), {'가': '제외 — 다시 넣으면', '나': '제외 — 다시 넣으면', '다': '그대로(근거 확인 중)'}[p5]))
    changed = [r for r in rows if not r[3].startswith(('제외 그대로', '유지 그대로', '그대로'))]
    return {'cases': [{'event': a, 'sop': b, 'forecast_ts1': f, 'after': d} for a, b, f, d in rows], 'changed': len(changed)}


def sop_diff(sop, prep, ban, done):
    """받은 SOP 구조(입력/sop.json의 이 작업)와 모은 조건을 견준 것 — 카드에만 있는 항목(어느 문서 · 절에서 왔는지)과
    SOP 구조에만 있는 문장(그 필드 · 출처). 두 문장은 글자 · 숫자만 남겨 짧은 쪽의 80 % 이상이 같은 순서로 겹치면 같은 것으로 본다(조사 · 어미 차이는 넘김).
    카드 쪽은 SOP 구조의 모든 문장(단계 · 승인 역할 포함)과 견주고, SOP 구조 쪽은 카드에 넣는 준비(첫 단계 포함) · 금지 · 완료만 견준다 — 방법 단계는 카드에 넣지 않는다."""
    import difflib

    def same(a, b):
        a, b = X.squash(a), X.squash(b)
        short = min(len(a), len(b))
        if short < 6:
            return False
        if a in b or b in a:
            return True
        return sum(m.size for m in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks()) >= 0.8 * short
    task = next(x for x in sop['sops'] if x['id'] == TASK)

    def parts(rows):
        return [part for row in rows for part in X.sentences(re.sub(r'\([^)]*\)$', '', row['text']).strip())]
    cardside = [(name, field, part) for name, field, rows in [('준비', 'apply_conditions', task['apply_conditions']), ('준비', 'steps', [st for st in task['steps'] if st['order'] == 1]),
                                                           ('금지', 'prohibitions', task['prohibitions']), ('완료', 'completion', task['completion'])] for part in parts([*rows])]
    every = parts(task['apply_conditions'] + task['steps'] + task['prohibitions'] + task['completion'])
    role = (task.get('approval') or {}).get('role') or ''
    out = []
    for name, rows in [('준비', prep), ('금지', ban), ('완료', done)]:
        for r in rows:
            if not (any(same(r['quote'], part) for part in every) or (role and role in r['quote'] and '승인' in r['quote'])):
                out.append({'item': r['quote'], 'where': '카드에만', 'note': f'{name} — {r["doc_id"]} {r["rev"]} {r["section"]}에서 옴, 받은 SOP 구조의 이 작업에는 없음'})
    for name, field, part in cardside:
        if not any(same(r['quote'], part) for rows in (prep, ban, done) for r in rows):
            out.append({'item': part, 'where': 'SOP 구조에만', 'note': f'{name} — 입력/sop.json {TASK} {field}, 승인한 원문 후보가 없음'})
    return out


def selected(reviews, lines, p5, p6, sop):
    """실전 03-4 결과/선택작업_조건.json — 승인 후보를 문서를 가리지 않고 모으고, 승인하지 않은 것은 남은 질문으로, 받은 SOP 구조와 다른 곳은 sop_diff로.
    같은 문서 · 판의 같은 인용은 한 번만 둔다(단계와 시작 조건이 같은 줄이면 한 항목)."""
    prep, ban, done, rest = [], [], [], []

    def add(part, ref):
        if not any(r['doc_id'] == ref['doc_id'] and r['rev'] == ref['rev'] and X.squash(r['quote']) == X.squash(ref['quote']) for r in part):
            part.append(ref)
    for stem, data in sorted(reviews.items()):
        name = data['source_file']
        decided = [(c['line_start'], c['line_end']) for c in data['candidates'] if c['status'] == 'approved']
        for c in data['candidates']:
            if c['status'] == 'pending' and any(a <= c['line_end'] and c['line_start'] <= b for a, b in decided):
                continue      # 같은 원문 줄을 승인한 후보가 있다(다른 인용 경계로 뽑은 같은 줄) — 남은 질문으로 다시 묻지 않는다
            in_task = lines.is_task(name, c) and data['doc_status'] in ('현행', '참고(제조사)')
            sr = name == SR and c['line_start'] == line_of(lines.text(SR), '운전 중에는 인터록 한계에 다가가는', SR)
            if not (in_task or sr):
                continue
            ref = {'candidate': f'결과/검토/{stem}_검토.json#{c["id"]}', 'doc_id': data['doc_id'], 'rev': data['rev'], 'section': c['section'], 'quote': c['quote'], 'decision': c['decision']}
            if c['status'] != 'approved':
                source = f'{data["doc_id"]} {data["rev"]} {c["section"]} {c["line_start"]}줄'
                if c['status'] == 'pending' and not any(r['source'] == source for r in rest):   # 한 원문 줄에 남은 질문 하나
                    rest.append({'item': c['text'], 'kind': '보류', 'source': source, 'note': c['reason']})
                continue
            if sr:
                if p5 == '가':
                    add(ban, ref)
                continue
            if c['kind'] == 'prohibition':
                add(ban, ref)
            elif c['kind'] == 'completion':
                add(done, ref)
            elif c['kind'] == 'precondition' or (c['kind'] == 'step' and c.get('order') == 1):
                add(prep, ref)
    rest.append({'item': '트립 뒤 복귀 조건(조건표 R5의 출처 HM-9.4)', 'kind': '제공되지 않은 절', 'source': '자료/HM-9장_스캔본.txt 목차 HM-9.4(9-7쪽)',
                 'note': '스캔에 9-7쪽이 없다 — 원본 확인을 요청한다'})
    if p5 == '다':
        rest.append({'item': '예측 유온 65 ℃ 이상 제외 조건(조건표 R4)이 이 작업에 걸리는지', 'kind': '원문 미확인', 'source': '자료/SR-04_설비안전규정_발췌.txt 제4조',
                     'note': '안전관리 담당의 해석을 받기 전까지 보류'})
    sop_line = line_of(lines.text(HM11), '## HM-8.7 근본 조치', HM11)
    return {'task': TASK, 'basis': f'입력/조치검토결과.json 경보 {INCIDENT}의 검토 의견(즉시 완화 뒤에도 원인이 남음) · 자료/HM-8_매뉴얼.md {sop_line}~{sop_line + 6}줄(HM-8.7 근본 조치 · SOP-COOL-14)',
            'preparation': prep, 'prohibitions': ban, 'completion': done, 'remaining_questions': rest, 'sop_diff': sop_diff(sop, prep, ban, done)}


def base_candidates(run=BASE_RUN):
    """(후보 {파일 이름: 후보 dict}, 검토 시각) — 다음 실습 입력과 추출 학생용 완성본이 함께 쓰는 강사 판의 후보: 강사 추출 실행(수업 모델 답)의 결과/후보.
    검토 시각은 그 후보 파일을 다 만든 뒤(가장 늦은 generated_at)다. 실행이 없으면 멈춘다 — 규칙 기반 후보로 대신하지 않는다."""
    folder = Path(run)/'결과/후보'
    if not folder.is_dir():
        raise RuntimeError(f'강사 추출 실행이 없습니다: {folder} — instructor_extract.py로 실행을 고정한 뒤 다시 만듭니다')
    cands = {p.name: json.loads(p.read_text(encoding='utf-8')) for p in sorted(folder.glob('*.json'))}
    return cands, max(c['generated_at'] for c in cands.values())


def own_table(own):
    """내 입력(결과/내_입력/)의 조건표 — 3회차 지점2 나 · 다."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'session3'))
    import criteria as CR
    return CR.table_csv(own), CR.sop_json('가', own)


def build(folder, cands, judged, p5, p6, course, own=None, reviewed_at=REVIEWED_AT):
    """갈래 하나의 산출: {상대 경로: 바이트}. cands = {후보 파일 이름: 후보 dict}(두 번째 구현 또는 수업 모델 응답에서 만든 것)."""
    lines = Lines(folder)
    items = expected(folder)
    out, reviews = {}, {}
    for fname, data in sorted(cands.items()):
        if data['source_file'] not in TARGETS:
            continue
        raw = X.dump(data).encode('utf-8')
        out[f'후보/{fname}'] = raw
        rv = review_one(folder, data, raw, lines, items, p5, p6, own, course, reviewed_at)
        reviews[stem_of(data)] = rv
        out[f'검토/{stem_of(data)}_검토.json'] = X.dump(rv).encode('utf-8')
    if course == '실전반':
        out['선택작업_조건.json'] = X.dump(selected(reviews, lines, p5, p6, json.loads((Path(folder)/'입력/sop.json').read_text(encoding='utf-8')))).encode('utf-8')
    out['판정_변화.json'] = X.dump(judge_changes(judged, p5, own)).encode('utf-8')
    return out, reviews
