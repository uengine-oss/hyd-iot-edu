"""문서 지식 묶음(통합반 04회차 실습2 · 3, 실전반 03회차 실습4 · 5)의 문서 자료 코어 — 가상 사례, 고정 시드. 냉각 경보 조치 판단 묶음(data_conditions.py)도
같은 문서 사본 · 작업지시 이력을 여기서 받는다(같은 사실 한 곳). 몇 번을 돌려도 같은 바이트가 나온다(`python data_documents.py --check`).

설계 정본: 작업 폴더 구성안_문서지식.md 3절. 근거: 근거/2026-10-28_현업데이터_현실성_조사.md §4.4 · 4.5(E1 · E2 · E3 · E5 · E6 · E8 · M6 · S13 · S14),
근거/2026-11-03_현업데이터_현실성_조사_4-8회차.md(N82 등).

문서 열 개(학생 폴더 `자료/`에 같은 이름으로):
  - main 원문 사본 넷(HM-8 1.1 · PM-02 · PR-07 · HI-01): 원문 머리의 꼬리표 · 면책 문장만 빼고, 가상 사례 표시와 출처(문서 목록의 판)를 머리에 적는다.
  - 생성 문서 여섯: HM-8 1.0판(폐기) · 1.2판 개정 요청 초안(미승인) · 제조사 지침 영한 발췌(7절 쿨러 코어 세척 포함) ·
    종합 정비 매뉴얼 9장 스캔본(문자 인식 글, 9-7쪽 없음) · 설비안전규정 SR-04 발췌(CP949) · 문서 관리 기준 DC-01.
  - 문서 목록(11행 — 파일 없는 행 하나), CMMS 작업지시 내보내기, ERP 재고 내보내기.
값의 한 곳: SR-04 제4조 · 9장 9.3의 한계는 main common/hydcommon/plant_model.py(lab_package.system_root()), 경계 낱말은 main ot/plant-sim/plantsim/plc.py의 비교.
9장 HM-9.1 · 9.2 문장은 1.0판의 같은 절과 한 상수(HM9)에서 나온다.

제조사 지침 7절(쿨러 코어 세척)의 근거 — 공개된 장비 정비 지침(2026-11-04 검색): 압축공기 또는 저압수(약 0.2 MPa · 30 psi 이하)로 핀과 나란하게 세척하고
고압 세척기는 쓰지 않는다(Hitachi ZW140-6 · ZAXIS 120-6 · Kubota ZG222A 운전자 매뉴얼, Polaris 정비 지침, Atlas Copco 애프터쿨러 지침), 손상된 부품은
교체한다(Olaer LAC 공랭식 오일 쿨러 매뉴얼). 세척 뒤 쿨러 입구 · 출구 유온 차를 시운전 기록과 견주는 6단계는 1차 자료를 찾지 못해 문제 유형만 따른 생성이고,
기준값은 지어내지 않았다(시운전 기록과 견줌 — 2회차 센서 정상값 TS1 48 ℃ · 쿨러 출구 TS2 44 ℃와 모순 없음).

설계 조건 검사(design_checks)가 하나라도 어긋나면 파일을 쓰지 않고 멈춘다 — 시드 · 계획 상수를 바꾸고 값을 손으로 고치지 않는다.
사용: import data_documents as DD; DD.bundle() → {자료 안 이름: 바이트}   ·   python data_documents.py --check
"""
from pathlib import Path
import csv
import datetime as dt
import hashlib
import io
import random
import re
import sys

from lab_package import system_root

SEED = 20261028
BASE = dt.date(2026, 10, 28)          # 문서 목록 · 작업지시 · 재고 내보내기의 기준일
DOC_NOTICE = '가상 사례: 공개된 현업 문제 유형을 따라 만든 자료이며 실제 회사·제조사·설비의 기록이 아니다.'   # 생성 · 사본 문서의 첫머리 표시(K-7)
FORBIDDEN = ('교육용', '수업용', '예시', '특정 제조사의 수치가 아니다', '포털 수업', '실제와 다르')   # 학생 파일에 두지 않는 꼬리표 · 면책 · 운영 말(K-7 · C-3)


# ───────────── main 원문 사본 ─────────────

def tagged(name, text, tags):
    for old, new in tags:
        if old not in text:
            raise RuntimeError(f'{name}: 바꿀 문장이 없습니다 — 원본이 바뀌었는지 보고 표를 고칩니다: {old!r}')
        text = text.replace(old, new)
    return text


def sample(name, tags):
    """main 원문 사본(it/portal/www/samples). 꼬리표 · 면책 문장만 빼고, 판 · 시행일이 없는 머리에는 문서 목록의 값을 적는다(main 원문 정리는 시스템 작업)."""
    return tagged(name, (system_root()/'it/portal/www/samples'/name).read_text(encoding='utf-8-sig'), tags)


def source_line(doc, rev):
    r = row(doc, rev)
    return (f'출처: 회사 문서 관리 시스템에 등록된 {doc} 원문의 사본이다. 원문 머리에 판 · 시행일이 없어 회사 문서 목록의 값을 적는다 — '
            f'판 {r["판"]}, 시행 {r["시행일"]}, {r["상태"]}.')


HM8_TAGS = lambda: [('# 유압 파워유닛 쿨러 팬 정비 매뉴얼 (HM-8, 교육용 예시)\n',
                     f'# 유압 파워유닛 쿨러 팬 정비 매뉴얼 (HM-8)\n\n{DOC_NOTICE}\n\n{source_line("HM-8", "1.1")} '
                     f'{row("HM-8", "1.0")["판"]}판(시행 {row("HM-8", "1.0")["시행일"]})을 대체한다.\n'),
                    ('아래 값은 교육용 가상 설비의 축소 기준이다(일반 산업 설비의 경보는 보통 80 ℃ 안팎이다). ', '')]
HI01_TAGS = [('판본: 1.0 / 수업용 가상 HYD 유압 파워팩 / 2026-10-27',
              f'{DOC_NOTICE}\n\n출처: 회사 문서 관리 시스템에 등록된 HI-01 원문의 사본이다.\n\n판본: 1.0 / HYD 유압 파워팩 / 2026-10-27')]
PM02_TAGS = lambda: [('# 유압 파워팩 정기 점검표와 시행 기준 (PM-02, 교육용 예시)\n', f'# 유압 파워팩 정기 점검표와 시행 기준 (PM-02)\n\n{DOC_NOTICE}\n\n{source_line("PM-02", "2.0")}\n'),
                     ('이 문서는 파워팩 제조사(OEM)의 정기 점검표 형식을 본뜬 교육용 예시다. 특정 제조사의 수치가 아니다. 주기 2,000 h, 허용 오차 ±10 %, 정비 인원, 감점액은 교육용 가상 기업의 회사 설정값이다.',
                      '이 문서는 파워팩 제조사(OEM)의 정기 점검표 형식을 따른 회사 기준이다. 주기 2,000 h, 허용 오차 ±10 %, 정비 인원, 감점액은 회사 설정값이다.')]
PR07_TAGS = lambda: [('# 예비품 관리 · 구매 기준서 (PR-07, 교육용 예시)\n', f'# 예비품 관리 · 구매 기준서 (PR-07)\n\n{DOC_NOTICE}\n\n{source_line("PR-07", "1.3")}\n'),
                     ('이 기준서는 교육용 가상 기업의 구매 규정 예시다. 특정 회사의 규정이나 법령 조문이 아니다. ', '이 기준서는 회사 구매 규정이다. '),
                     ('(교육용 설정)', '(회사 설정)')]


def hm8_copy():
    return sample('HM-8_cooler-fan-manual.md', HM8_TAGS())


def hi01_copy():
    return sample('HI-01_shift-inspection-supplement.md', HI01_TAGS)


# ───────────── HM-8 1.0판(폐기) — 종합 정비 매뉴얼의 3 · 7 · 9장 절 번호 ─────────────
# 9장 두 절은 종합 정비 매뉴얼 9장(스캔본)의 같은 절과 같은 문장이다(한 상수).
HM9 = {'HM-9.1': ('펌프 부하 하한', ['펌프 부하는 60 % 아래로 내리지 않는다(최소 부하 인터록).']),
       'HM-9.2': ('금지와 제한', ['- 원격 조치(SOP-COOL-01~03)는 REMOTE_AUTO가 아닐 때 쓰지 않는다.', '- 팬 100 % 연속 운전이 24시간을 넘으면 팬 수명이 줄어든다.'])}

HM8_OLD = f'''# 유압 파워유닛 쿨러 팬 정비 매뉴얼 (HM-8)

판: 1.0 / 시행 2025-03-10 / 현장 정비실 게시본을 전사함
{DOC_NOTICE}
이 판은 종합 정비 매뉴얼의 3·7·9장 절 번호를 그대로 쓴다.

## HM-3.1 현장 조작 전 준비
현장 작업은 설비를 정지하고 현장 패널에서 LOCAL로 전환한 뒤 한다.

## HM-3.2 원격 조치 조건
원격 조치는 PLC 운전 모드가 REMOTE_AUTO일 때만 한다. 현장에서 수동 조작이 들어와 REMOTE_MANUAL이면 원격 조치를 내리지 않는다.

## HM-7.1 쿨러 팬 벨트 점검
팬 지시값은 정상인데 냉각 효율이 떨어지고 진동 VS1이 0.9 mm/s를 넘으면, 벨트 슬립이나 베어링 마모를 먼저 의심한다.

### SOP-FAN-01 쿨러 팬 점검 절차
1. HM-3.1에 따라 설비를 정지하고 LOCAL로 전환한다.
2. 벨트 처짐을 측정한다 (기준 10~15 mm).
3. 베어링 소음과 표면 온도를 확인한다 (60 ℃ 이하).
4. 재가동 후 VS1이 0.9 mm/s 아래로 내려왔는지 확인한다.

### SOP-FAN-02 벨트 교체 절차
1. HM-3.1에 따라 설비를 정지하고 LOCAL로 전환한다.
2. 구 벨트를 분리하고 풀리 정렬을 점검한다.
3. 새 벨트를 걸고 처짐을 12 mm로 맞춘다.
4. 30분 시운전 뒤 냉각 효율 CE가 80 % 이상인지 확인한다.

## HM-7.2 냉각 성능 판정 기준

| 항목 | 정상 | 경보 (냉각 성능 저하) | 인터록 |
|---|---|---|---|
| 유온 TS1 | 52 ℃ 미만 | 55 ℃ 초과이면서 상승 중 | 65 ℃ 초과 (설비 정지) |
| 냉각 효율 CE | 80 % 이상 | 70 % 미만 | — |

유온이 55 ℃를 넘고 냉각 효율이 70 % 아래로 떨어진 채 유온이 계속 오르면 쿨러 냉각 성능 상실로 본다. 이 상태로 두면 인터록 한계 65 ℃를 넘으면서 설비가 선다.

## HM-7.3 팬 증속 운전
쿨러 성능 저하 때 팬을 80~100 %로 올린다. 100 % 연속 운전은 24시간 이내로 한다.

### SOP-COOL-01 팬 최대 운전
1. HM-3.2 조건을 확인한다.
2. 팬 속도를 100 %로 올린다.
3. 15분 재관측으로 HM-7.5 회복 판정을 한다.

승인: 운전원.

### SOP-COOL-02 팬 최대 운전과 부하 80 %
1. HM-3.2 조건을 확인한다.
2. 팬 속도를 100 %로 올린다.
3. 펌프 부하를 80 %로 낮춘다. 최소 부하는 HM-9.1을 따른다.
4. 15분 재관측으로 HM-7.5 회복 판정을 한다.

승인: 운전원.

### SOP-COOL-03 부하 70 %와 야간 핀 세척
1. HM-3.2 조건을 확인한다.
2. 펌프 부하를 70 %로 낮춘다.
3. 15분 재관측으로 HM-7.5 회복 판정을 한다.
4. 야간 정비창에 SOP-COOL-04 핀 세척 작업지시를 건다.

승인: 생산관리자.

## HM-7.4 원인 확인
- 쿨러 핀 오염: 최근 30초 냉각 효율 평균이 70 % 미만이고 팬 진동이 정상이면 핀 오염으로 본다.
- 주변 온도 상승: 캐비닛 온도 TS4가 35 ℃ 이상이면 외기 고온으로 본다.
- 팬 구동 불량: 팬 진동 VS1이 0.9 mm/s 이상이면 HM-7.1 점검으로 넘어간다.

## HM-7.5 냉각 회복 판정
조치 뒤 15분 동안 TS1이 55 ℃ 미만이고 경보가 해제된 상태가 유지되면 완화에 성공한 것이다.

## HM-7.6 쿨러 핀 세척
원인이 핀 오염이면 CMMS 작업지시로 세척한다. 승인은 설비보전팀장이 한다.

### SOP-COOL-04 쿨러 핀 세척
1. HM-3.1에 따라 설비를 정지하고 LOCAL로 전환한다.
2. 압축공기 또는 저압수로 핀을 세척한다.
3. 재가동 후 냉각 효율 CE가 75 % 이상으로 돌아왔는지 확인한다.

## HM-7.7 캐비닛 환기

### SOP-COOL-05 캐비닛 환기 보강
1. 캐비닛 온도 TS4와 외기 온도를 기록한다.
2. 환기 필터를 청소하고 배기 팬 동작을 점검한다.
3. 캐비닛 온도가 35 ℃ 아래로 내려왔는지 확인한다.
''' + ''.join(f'\n## {sid} {title}\n' + '\n'.join(lines) + '\n' for sid, (title, lines) in HM9.items())


# ───────────── HM-8 1.2판 개정 요청 초안(미승인) — 1.1판 사본에 변경 표시 ─────────────
CR = ('CR-2026-031', '2026-10-12')
DRAFT_HEAD = f'''# 유압 파워유닛 쿨러 팬 정비 매뉴얼 (HM-8) — 1.2판 개정 요청 초안

{DOC_NOTICE}

변경 요청 {CR[0]} · 요청 {CR[1]} · 요청 부서 설비보전팀 · 상태 검토 중. 1.1판 본문에 바꾸려는 곳을 표시했다.
표시: 「[추가]」는 새로 넣는 문장, 「[변경]」은 바꾸는 문장(바로 아래 「1.1판:」 줄에 지금 문장)이다. 「> 검토 의견:」 줄은 요청자가 적은 변경 까닭이다.
'''
DRAFT_SCOPE = ('## HM-8.0 적용 범위 [추가]\n이 매뉴얼은 설비 대장에 모델 HPP-45A로 등록된 공랭식 오일 쿨러 유압 파워팩에 적용한다.\n'
               '> 검토 의견: 1.1판에 적용 범위 문장이 없어, 같은 라인의 수냉식 후속형(HPP-45B)에도 이 매뉴얼을 쓰는지 현장 문의가 있었다.\n\n')
# (1.1판 줄, 바꾼 줄, 검토 의견) — 경계 낱말 정리 · 핀 세척 방법
DRAFT_CHANGES = [
    ('조치 후 예측 유온이 55 ℃ 이상이면 경보 해제에 실패할 수 있으므로', '조치 후 예측 유온이 55 ℃를 넘으면 경보 해제에 실패할 수 있으므로',
     'HM-8.3 표의 경보 기준(55 ℃ 초과)과 낱말을 맞춘다.'),
    ('2. 압축공기로 핀 바깥쪽에서 안쪽으로 세척한다. 고압수는 쓰지 않는다.', '2. 압축공기 또는 저압수(0.2 MPa 이하)로 핀 바깥쪽에서 안쪽으로 세척한다. 고압수는 쓰지 않는다.',
     '유막이 섞인 오염은 압축공기만으로 잘 떨어지지 않는다는 현장 의견이 있었다(설비보전팀 9월 회의).'),
]
DRAFT_HISTORY = f'''
## 개정 이력

| 판 | 시행 | 바뀐 것 |
|---|---|---|
| 1.0 | 2025-03-10 | 제정 — 종합 정비 매뉴얼의 3 · 7 · 9장 절 번호, 절차 번호 SOP-FAN-01 · 02 · SOP-COOL-01~05 |
| 1.1 | 2026-09-01 | 절 번호 체계 변경(HM-8.1~8.8), 절차 번호 SOP-FAN-11 · 12 · SOP-COOL-11~15, 안전 조항 보완 |
| 1.2 | (승인 전) | {CR[0]} — 적용 범위 추가, 경계 낱말 정리, 핀 세척 방법 |
'''


def hm8_draft():
    body = hm8_copy().split('\n## HM-8.1 ', 1)
    if len(body) != 2:
        raise RuntimeError('HM-8 사본에서 HM-8.1 절을 찾지 못했습니다.')
    lines = []
    for line in ('## HM-8.1 ' + body[1]).splitlines():
        hit = [c for c in DRAFT_CHANGES if c[0] in line]
        if not hit:
            lines.append(line)
            continue
        old, new, why = hit[0]
        step = re.match(r'(\d+\. )(.*)$', line)
        if step:                                  # 절차 단계 — 번호 뒤에 표시, 지금 문장 · 까닭은 들여 쓴 줄로
            lines += [step.group(1) + '[변경] ' + line.replace(old, new)[len(step.group(1)):], '   1.1판: ' + step.group(2), '   > 검토 의견: ' + why]
        else:
            lines += ['[변경] ' + line.replace(old, new), '1.1판: ' + line, '> 검토 의견: ' + why]
    if sum(1 for line in lines if '[변경]' in line) != len(DRAFT_CHANGES):
        raise RuntimeError('1.2판 초안: 바꿀 문장이 1.1판 사본에 하나씩 있지 않습니다.')
    return DRAFT_HEAD + '\n' + DRAFT_SCOPE + '\n'.join(lines) + '\n' + DRAFT_HISTORY


# ───────────── 제조사 정비 지침 영한 발췌(참고) ─────────────
OEM = f'''# HPP-45A Hydraulic Power Pack — Maintenance Manual (Excerpt) / HPP-45A 유압 파워팩 정비 지침 (발췌)

Hanil Hydraulics, Document OEM-HPP45A-MM, Rev. C (2024-06) / 한일유압 문서 OEM-HPP45A-MM, C판(2024-06)
{DOC_NOTICE}

이 발췌는 제조사 영문 원본(EN)과 설비보전팀 사내 번역(KO)을 함께 적었다. 번역은 참고이며 뜻이 다르면 영문 원본을 따른다.
회사 기준과의 관계: 사내 기준과 다르게 정한 항목은 사내 기준을 따른다.
압력은 원본 단위 psi로 적었다. 1 bar는 14.5 psi다. 적용 범위(사내 주석): 설비 대장에 모델 HPP-45A로 등록된 설비.

## 1 Safety / 안전
EN: Before opening any hydraulic line or filter housing, stop the pump, lock out the motor supply, and discharge the accumulator to tank.
KO: 유압 배관이나 필터 하우징을 열기 전에 펌프를 세우고 모터 전원을 잠근 뒤 어큐뮬레이터를 탱크로 방압한다.
EN: Do not open the circuit until the system pressure gauge reads 0 psi.
KO: 시스템 압력계가 0 psi를 가리키기 전에는 회로를 열지 않는다.
EN: Never loosen a fitting to release trapped pressure.
KO: 남은 압력을 빼려고 피팅을 풀지 않는다.
EN: Hot fluid can cause burns. Allow the fluid to cool below 40 °C before draining.
KO: 뜨거운 작동유는 화상을 입힐 수 있다. 배유 전에 작동유를 40 °C 아래로 식힌다.

## 2 Maintenance Schedule / 정비 주기
EN: Intervals are counted from commissioning or from the last completed service, whichever is later.
KO: 주기는 시운전일과 마지막 정비 완료일 중 늦은 날부터 센다.

| Item / 항목 | Interval / 주기 | Action / 조치 | See / 참조 |
|---|---|---|---|
| Fluid level and appearance / 작동유 수위·외관 | Daily / 매일 | Visual check / 육안 확인 | 5 |
| Fluid condition (colour, odour) / 작동유 상태(색·냄새) | Monthly or every 150 h, whichever comes first / 월 1회 또는 150 h 중 먼저 오는 때 | Compare with Section 5 / 5절과 비교 | 5 |
| Return filter element, 10 µm / 리턴 필터 엘리먼트 10 µm | Indicator red, or every 1,000 h or 6 months, whichever comes first / 지시기 적색 또는 1,000 h마다 | Replace / 교체 | 3 |
| Suction strainer, 125 µm / 흡입 스트레이너 125 µm | 4,000 h | Clean / 세척 | — |
| Accumulator precharge / 어큐뮬레이터 프리차지 | See Section 4 / 4절 | Check and recharge / 점검·재충전 | 4 |
| Pump shaft seal / 펌프 축 씰 | 2,000 h | Replace / 교체 | — |
| Fluid laboratory analysis / 작동유 시험 분석 | 12 months or 2,000 h, whichever comes first / 12개월 또는 2,000 h 중 먼저 오는 때 | Particle count, water, viscosity / 입자 수·수분·점도 | 5 |
| Fluid change / 작동유 교환 | 8,000 h or when analysis fails / 8,000 h 또는 분석 불합격 때 | Drain, flush and refill / 배유·세정·주유 | — |

## 3 Return Filter / 리턴 필터
EN: The clogging indicator turns red when the differential pressure across the element reaches 25 psi.
KO: 엘리먼트 앞뒤 차압이 25 psi에 이르면 막힘 지시기가 적색으로 바뀐다.
EN: Indicator readings taken with fluid below 30 °C are not valid. Recheck at operating temperature.
KO: 작동유가 30 °C 아래일 때 본 지시기 값은 쓰지 않는다. 운전 온도에서 다시 확인한다.

### T-3.1 Return filter element replacement / 리턴 필터 엘리먼트 교체
1. EN: Carry out the safety steps in Section 1 and confirm that the gauge reads 0 psi.
   KO: 1절의 안전 조치를 하고 압력계가 0 psi인지 확인한다.
2. EN: Remove the bowl and the element. Do not clean and reuse paper elements.
   KO: 보울과 엘리먼트를 분리한다. 종이 엘리먼트는 세척해 다시 쓰지 않는다.
3. EN: Inspect the old element. If metal particles are visible, take a fluid sample for analysis before restart.
   KO: 떼어 낸 엘리먼트를 살핀다. 금속 입자가 보이면 재가동 전에 작동유 시료를 채취해 분석을 맡긴다.
4. EN: Fit a new 10 µm element (part no. HI-RF-10) with a new O-ring and tighten the bowl to 35 N·m.
   KO: 새 10 µm 엘리먼트(부품 번호 HI-RF-10)를 새 O링과 함께 끼우고 보울을 35 N·m로 조인다.
5. EN: Reset the indicator, restart, and run for 10 minutes. Check the housing for leaks.
   KO: 지시기를 초기화하고 재가동해 10분 운전한 뒤 하우징 누유를 확인한다.
6. EN: At operating temperature the differential pressure must be below 10 psi. Record the reading and the element lot number.
   KO: 운전 온도에서 차압이 10 psi 미만이어야 한다. 읽은 값과 엘리먼트 로트 번호를 기록한다.

## 4 Accumulator / 어큐뮬레이터
EN: Nominal precharge is 1,450 psi of dry nitrogen at 20 °C, as stamped on the nameplate.
KO: 프리차지 기준은 명판에 새긴 대로 20 °C에서 건조 질소 1,450 psi다.
EN: Use dry nitrogen only. Never charge with oxygen or compressed air.
KO: 건조 질소만 쓴다. 산소나 압축공기로 충전하지 않는다.
EN: Check the precharge 2 weeks or 100 operating hours after installation or recharge, whichever comes first.
KO: 설치나 재충전 뒤 2주 또는 100 운전시간 중 먼저 오는 때에 프리차지를 점검한다.
EN: If the precharge has fallen by more than 200 psi since the previous check, check weekly or every 50 operating hours. Otherwise check every 4 weeks or 200 operating hours.
KO: 직전 점검보다 200 psi 넘게 떨어졌으면 매주 또는 50 운전시간마다 점검한다. 그렇지 않으면 4주 또는 200 운전시간마다 점검한다.
EN: Recharge if the precharge is below 90 % of the nameplate value.
KO: 프리차지가 명판 값의 90 % 미만이면 재충전한다.

### T-4.1 Precharge check / 프리차지 점검
1. EN: Carry out the safety steps in Section 1. The fluid side must read 0 psi before the charging kit is connected.
   KO: 1절의 안전 조치를 한다. 충전 키트를 연결하기 전에 유압 쪽이 0 psi여야 한다.
2. EN: Connect the charging kit to the gas valve and read the precharge.
   KO: 충전 키트를 가스 밸브에 연결하고 프리차지를 읽는다.
3. EN: Correct the reading to 20 °C with the table on the nameplate.
   KO: 명판의 표로 읽은 값을 20 °C 기준으로 보정한다.
4. EN: If the corrected value is below 90 % of the nameplate value, recharge with dry nitrogen to the nameplate value.
   KO: 보정한 값이 명판 값의 90 % 미만이면 건조 질소로 명판 값까지 재충전한다.
5. EN: Record the corrected value, the date and the hour meter reading, and set the next check from Section 4.
   KO: 보정한 값과 날짜, 운전시간 계수기 값을 기록하고 4절에 따라 다음 점검을 정한다.

## 5 Fluid Condition / 작동유 상태 판정

| Observation / 관찰 | Likely cause / 추정 원인 | Action / 조치 |
|---|---|---|
| Milky or cloudy / 우윳빛·탁함 | Water ingress, check the heat exchanger / 수분 유입, 열교환기 확인 | Laboratory analysis, change fluid / 시험 분석, 작동유 교환 |
| Dark with burnt odour / 짙은 색·탄 냄새 | Oxidation from overheating / 과열에 의한 산화 | Laboratory analysis, check cooler / 시험 분석, 쿨러 점검 |
| Sediment after standing overnight / 하룻밤 뒤 침전물 | Filter element failure / 필터 엘리먼트 파손 | Inspect filters, see Section 3 / 필터 점검, 3절 참조 |
| Level low / 수위 낮음 | External leak / 외부 누유 | Find and repair the leak / 누유 부위 수리 |
| Level high / 수위 높음 | Water through the heat exchanger / 열교환기를 통한 물 유입 | Stop and inspect the heat exchanger / 정지 후 열교환기 점검 |

EN: Maximum operating fluid temperature is 70 °C (158 °F).
KO: 작동유 최고 운전 온도는 70 °C(158 °F)다.

## 6 After Service / 정비 후 확인
EN: After any service, run the unit for 15 minutes at working pressure and confirm that there are no leaks.
KO: 정비 뒤에는 작업 압력으로 15분 운전하고 누유가 없는지 확인한다.
EN: Record the pump outlet pressure, flow and fluid temperature. The readings must be within the limits of the commissioning record.
KO: 펌프 토출 압력·유량·작동유 온도를 기록한다. 값은 시운전 기록의 한계 안에 있어야 한다.

## 7 Oil Cooler / 오일 쿨러
EN: The oil cooler is an air-blast type. Dust and oil mist on the fins reduce the air flow and raise the fluid temperature.
KO: 오일 쿨러는 공랭식이다. 핀에 쌓인 먼지와 유막이 바람을 막아 작동유 온도가 오른다.
EN: Clean the core when the fins are visibly blocked or the fluid temperature stays above normal at working load.
KO: 핀 막힘이 눈에 보이거나 작업 부하에서 작동유 온도가 평소보다 높게 머물면 코어를 세척한다.

### T-7.1 Cooler core cleaning / 쿨러 코어 세척
1. EN: Stop the pump, lock out the motor supply, and wait until the fan has stopped.
   KO: 펌프를 세우고 모터 전원을 잠근 뒤 팬이 멈출 때까지 기다린다.
2. EN: Inspect the core before cleaning. Record blocked areas and bent or damaged fins.
   KO: 세척 전에 코어를 살펴 막힌 곳과 휘거나 손상된 핀을 기록한다.
3. EN: Clean with compressed air or with low-pressure water at no more than 30 psi. Keep the jet parallel to the fins.
   KO: 압축공기 또는 30 psi 이하의 저압수로 세척한다. 분사 방향은 핀과 나란하게 둔다.
   (번역 메모: 이 절의 psi 값은 bar로 바꿔 적을 것 — 미반영)
4. EN: Do not use a high-pressure washer. High-pressure water bends the fins.
   KO: 고압 세척기는 쓰지 않는다. 고압수는 핀을 휘게 한다.
5. EN: If blocked areas or bent fins remain after cleaning, replace the core (part no. HI-CC-45A).
   KO: 세척 뒤에도 막힌 곳이나 휜 핀이 남으면 코어(부품 번호 HI-CC-45A)를 교체한다.
6. EN: After cleaning or replacement, run the unit at working load for 30 minutes and record the fluid temperature at the cooler inlet and outlet. The difference must not be less than the value in the commissioning record.
   KO: 세척이나 교체 뒤 작업 부하로 30분 운전하고 쿨러 입구와 출구의 작동유 온도를 기록한다. 그 차이가 시운전 기록의 값보다 작으면 안 된다.
'''
OEM_MEMO = '(번역 메모: 이 절의 psi 값은 bar로 바꿔 적을 것 — 미반영)'
OEM_HEAD_END = '## 1 Safety'   # 머리말 = 이 줄 앞


# ───────────── 값의 한 곳 — main plant_model · plc ─────────────

def plant():
    """main 시스템의 인터록 한계와 경계 비교. (항목, 태그, 값, 단위, 경계 낱말, 정지 원인 표시) — plc.check_interlock의 비교를 낱말로 옮긴다."""
    root = system_root()
    for extra in [root/'common']:
        if str(extra) not in sys.path:
            sys.path.insert(0, str(extra))
    from hydcommon import plant_model as M
    plc = (root/'ot/plant-sim/plantsim/plc.py').read_text(encoding='utf-8')
    words = {'>': '초과', '<': '미만', '>=': '이상', '<=': '이하'}
    out = []
    for name, tag, attr, const, cause, unit in [('유온', 'TS1', 'ts1', 'TRIP_TS1', 'OVERTEMP', '℃'), ('토출 압력', 'PS1', 'ps1', 'TRIP_PS1', 'LOW_PRESSURE', 'bar'),
                                                 ('팬 진동', 'VS1', 'vs1', 'TRIP_VS1', 'HIGH_VIBRATION', 'mm/s')]:
        m = re.search(rf'u\.{attr} (>=|<=|>|<) {const}:\s*\n\s*p\.state, p\.trip = "TRIP", "{cause}"', plc)
        if not m:
            raise RuntimeError(f'main plc.py에서 {const}의 인터록 비교를 찾지 못했습니다 — 생성기를 main에 맞춥니다.')
        out.append((name, tag, getattr(M, const), unit, words[m.group(1)], cause))
    return out, M


def num(v):
    """한계 값을 문서에 적는 꼴 — 65 · 130 · 2.0."""
    return str(int(v)) if v == int(v) and abs(v) >= 10 else f'{v:.1f}'


# ───────────── 종합 정비 매뉴얼 9장 스캔본(참고, 문자 인식 글) ─────────────
SCAN_SEED = 7
SCAN_WIDTH, SCAN_LINES = 30, 6        # 종이 한 쪽: 한 줄 30자, 본문 6줄 — 이보다 긴 문단은 다음 쪽으로 넘어가며 끊긴다
SCAN_TITLE = '종합 정비 매뉴얼 제9장 운전 한계와 복귀 1.0판'


def scan_sections():
    """(절 표기, 제목, 문단들) — 문단 None은 제공되지 않은 쪽(목차에는 있다). 각 절은 새 쪽에서 시작한다."""
    rows, M = plant()
    ts1 = rows[0]
    limit_rows = [f'{name} {tag}  {num(v)} {unit} {word}  정지({cause})' for name, tag, v, unit, word, cause in rows]
    return [
        ('HM-9.0', '머리말', ['이 장은 유압 파워팩이 운전 한계에 닿았을 때의 설비 동작과, 그 뒤 설비를 다시 운전에 넣는 복귀를 정한다. '
                             '운전 한계는 설비를 지키는 마지막 장치이며 정상 운전의 기준이 아니다. 정상 운전과 경보의 기준은 설비별 정비 매뉴얼을 따른다.']),
        ('HM-9.1', HM9['HM-9.1'][0], HM9['HM-9.1'][1] + [f'최소 부하 {num(M.LOAD_MIN_PCT)} %는 PLC 부하 설정값의 쓰기 범위 하한이기도 하다. 이보다 낮은 설정은 PLC가 받지 않는다.']),
        ('HM-9.2', HM9['HM-9.2'][0], ['운전 한계에 닿지 않도록 운전 중에 지킬 금지와 제한이다.'] + HM9['HM-9.2'][1]),
        ('HM-9.3', '운전 한계', [f'운전 중인 설비가 아래 한계에 닿으면 PLC 인터록이 설비를 세우고 정지 원인을 표시한다. 자동으로 다시 운전에 들어가지 않는다.',
                              '항목  한계  정지 원인 표시'] + limit_rows + ['한계는 경보 기준보다 높게 둔다. 경보 기준은 설비별 정비 매뉴얼을 따른다.']),
        ('HM-9.4', '트립 후 복귀', None),
        ('HM-9.5', '운전 기록', ['설비가 한계에 닿아 섰으면 운전원은 정지 시각, 정지 원인 표시, 그때의 유온 · 압력 · 진동 값을 운전 일지에 적고 설비보전팀에 알린다.',
                              '기록지는 ▒▒▒▒ (판독 불가) ▒▒ 보관한다.']), ], ts1


def scan_main():
    """주 경로 문장(인식 오류를 확인하는 문장) — 9.1 부하 하한, 9.2 원격 조치 금지, 9.3 유온 한계 행."""
    sections, _ = scan_sections()
    return [HM9['HM-9.1'][1][0], HM9['HM-9.2'][1][0], next(p for p in sections[3][2] if p.startswith('유온 TS1'))]


def ocr(line, r):
    """문자 인식 오류 규칙(고정 시드): 두 자리 이상 숫자 사이 띄어쓰기, 가운뎃점 · 쉼표가 마침표로, 대문자 낱말 안 O가 0으로."""
    def space(m):
        t = m.group()
        if r.random() < 0.4:
            k = r.randint(1, len(t) - 1)
            return t[:k] + ' ' + t[k:]
        return t
    line = re.sub(r'\d{2,}', space, line)
    line = re.sub(r'[·,]', lambda m: '.' if r.random() < 0.3 else m.group(), line)
    return re.sub(r'(?<![A-Za-z0-9_])[A-Z_]{4,}(?![A-Za-z0-9_])', lambda m: m.group().replace('O', '0', 1) if 'O' in m.group() and r.random() < 0.5 else m.group(), line)


def wrap_points(text, width):
    """종이 한 줄(width자)씩 끊을 자리 — 낱말 사이에서 끊는다."""
    cuts, start = [], 0
    while len(text) - start > width:
        cut = text.rfind(' ', start, start + width + 1)
        cut = cut if cut > start else start + width
        cuts.append(cut)
        start = cut + (1 if text[cut:cut + 1] == ' ' else 0)
    return cuts


def scan_pages():
    """절을 종이 쪽에 앉힌다(절은 새 쪽, 한 쪽 SCAN_LINES줄). 반환: [(쪽 번호, [문단 조각])], 목차 {절: 쪽}, 쪽을 넘어 끊긴 문단 수."""
    sections, _ = scan_sections()
    pages, toc, split, page = [], {}, 0, 1
    pages.append((1, None))                  # 9-1쪽 = 머리말 + 목차(아래에서 채움)
    for sid, title, paras in sections[1:]:
        page += 1
        toc[sid] = (title, page)
        if paras is None:
            pages.append((page, 'missing'))
            continue
        cur, used = [f'{sid} {title}'], 1
        for para in paras:
            cuts = wrap_points(para, SCAN_WIDTH)
            need = len(cuts) + 1
            if used + need <= SCAN_LINES:
                cur.append(para)
                used += need
                continue
            room = SCAN_LINES - used            # 이 쪽에 남은 줄 — 그만큼만 싣고 나머지는 다음 쪽 첫머리로
            if room > 0:
                at = cuts[room - 1]
                cur.append(para[:at].rstrip())
                para, split = para[at:].lstrip(), split + 1
            pages.append((page, cur))
            page += 1
            cur, used = [para], len(wrap_points(para, SCAN_WIDTH)) + 1
        pages.append((page, cur))
    return pages, toc, split, sections


def scan_text():
    pages, toc, _, sections = scan_pages()
    r = random.Random(SCAN_SEED)
    head = sections[0]
    first = [f'{head[0]} {head[1]}', *head[2], '목차'] + [f'{sid} {title} {"." * 10} 9-{p}' for sid, (title, p) in toc.items()]
    pages[0] = (1, ['제9장 운전 한계와 복귀'] + first)
    kept = [(n, lines) for n, lines in pages if lines != 'missing']
    out = [f'문자 인식 결과 내보내기 — {SCAN_TITLE} 스캔본', DOC_NOTICE, f'원본: 종이 문서(정비실 보관) · 스캔 2026-10-20 · 스캔한 장 {len(kept)}', '']
    for i, (n, lines) in enumerate(kept, 1):
        out += [f'=== 스캔 {i}/{len(kept)} ===', ocr(SCAN_TITLE, r), '']
        out += [ocr(line, r) for line in lines]
        out += ['', f'- 9-{n} -', '']
    return '\n'.join(out).rstrip('\n') + '\n'


# ───────────── 설비안전규정 SR-04 발췌(현행, CP949 내보내기) ─────────────

def sr04_text():
    rows, _ = plant()
    name, tag, v, unit, word, _ = rows[0]
    over = {'초과': '넘으면', '이상': '이상이면', '미만': '미만이면'}[word]
    return f'''설비안전규정(SR-04) 발췌
{DOC_NOTICE}
옛 문서 관리 시스템 내보내기 · 2026-10-21 · 2024판(시행 2024-03-01) · 소유 부서 안전환경팀
이 발췌에 실은 조: 제1조, 제4조, 제5조. 그 밖의 조는 싣지 않았다.

제1조(목적)
이 규정은 생산 설비를 운전하고 정비할 때 사람과 설비를 지키기 위해 지킬 사항을 정한다.

제4조(유압 설비 온도 인터록)
① 유압 설비의 실측 유온이 인터록 한계({num(v)} {unit})를 {over} 설비가 정지한다. 인터록 한계는 설비 매뉴얼의 운전 한계를 따른다.
② 운전 중에는 인터록 한계에 다가가는 조치를 하지 않는다.
③ 인터록으로 정지한 설비의 복귀는 종합 정비 매뉴얼 HM-9.4를 따른다.

제5조(정비 중 에너지 차단)
① 유압 회로를 여는 정비는 모터 전원을 잠그고(LOTO) 잔압이 0인지 압력계로 확인한 뒤 시작한다.
② 잠금은 정비를 맡은 사람이 걸고 그 사람이 푼다.
③ 정비를 마치면 공구와 사람이 설비 밖에 있는지 확인한 뒤 잠금을 푼다.

부칙
이 규정은 2024년 3월 1일부터 시행한다.
'''


# ───────────── 문서 관리 기준 DC-01(현행) ─────────────
DC01 = f'''# 문서 관리 기준 (DC-01)

{DOC_NOTICE}

판 3.0 · 시행 2025-01-01 · 현행 · 소유 부서 품질경영팀

## DC-1 적용 범위
회사가 작업 근거로 쓰는 매뉴얼 · 점검표 · 기준서 · 규정과, 회사 밖에서 받은 제조사 문서 · 종이 원본을 옮긴 스캔본에 적용한다.

## DC-2 문서 목록과 판
- 문서는 문서 목록에 식별자 · 판 · 상태 · 시행일 · 소유 부서와 함께 등록한다.
- 파일은 등록할 때의 SHA-256으로 확인한다. 목록의 값과 다른 파일은 그 판의 문서로 보지 않는다.
- 한 식별자의 한 판은 한 행으로 등록한다.

## DC-3 상태의 뜻

| 상태 | 뜻 | 쓰는 곳 |
|---|---|---|
| 현행 | 지금 시행 중인 판 | 작업 근거 |
| 폐기 | 다른 판으로 대체된 판 | 지난 기록을 해석할 때만 |
| 개정 요청(미승인) | 개정을 요청해 검토 중인 초안 | 승인 전에는 작업 근거가 아니다 |
| 보충 | 기존 문서에 더하는 문서 | 기존 문서를 대체하지 않는다 |
| 참고(제조사) · 참고(스캔본) | 회사 밖에서 받았거나 종이 원본을 옮긴 문서 | 사내 기준과 다르게 정한 항목은 사내 기준을 따른다 |

## DC-4 개정
- 개정 요청은 변경 요청 번호(CR-연도-번호)로 등록하고, 문서 소유 부서장이 승인한 날부터 새 판을 시행한다.
- 새 판을 시행하면 이전 판의 상태를 폐기로 바꾼다.
'''


# ───────────── 문서 목록(11행) ─────────────
# (식별자, 제목, 판, 상태, 시행일, 소유 부서, 대체 관계, 파일 또는 None, 비고). 파일 None은 목록에만 있고 받은 파일이 없는 행.
REGISTER = [
    ('HM-8', '유압 파워유닛 쿨러 팬 정비 매뉴얼', '1.0', '폐기', '2025-03-10', '설비보전팀', '1.1판으로 대체', 'HM-8_1.0판_매뉴얼.md', '현장 정비실 게시본을 전사함'),
    ('HM-8', '유압 파워유닛 쿨러 팬 정비 매뉴얼', '1.1', '현행', '2026-09-01', '설비보전팀', '1.0판을 대체', 'HM-8_매뉴얼.md', '절 번호 체계 변경, 안전 조항 보완'),
    ('HM-8', '유압 파워유닛 쿨러 팬 정비 매뉴얼', '1.2', '개정 요청(미승인)', '', '설비보전팀', '', 'HM-8_1.2판_개정요청.md', f'변경 요청 {CR[0]} 검토 중'),
    ('HM-9', '종합 정비 매뉴얼 제9장 운전 한계와 복귀', '1.0', '참고(스캔본)', '', '설비보전팀', '', 'HM-9장_스캔본.txt', '원본 종이 문서는 정비실 보관. 스캔 2026-10-20'),
    ('SR-04', '설비안전규정', '2024', '현행', '2024-03-01', '안전환경팀', '', 'SR-04_설비안전규정_발췌.txt', '발췌(제1 · 4 · 5조). 옛 문서 관리 시스템에서 내보냄'),
    ('PM-02', '유압 파워팩 정기 점검표와 시행 기준', '2.0', '현행', '2026-01-15', '설비보전팀', '', 'PM-02_정기점검표.md', ''),
    ('PR-07', '예비품 관리 · 구매 기준서', '1.3', '현행', '2026-04-01', '구매팀', '', 'PR-07_예비품기준.md', ''),
    ('HI-01', '설비 점검·이상 확인 보충 매뉴얼', '1.0', '보충', '2026-10-27', '설비보전팀', 'HM-8 · PM-02 · PR-07을 대체하지 않음', 'HI-01_보충매뉴얼.md', ''),
    ('OEM-HPP45A-MM', 'HPP-45A 유압 파워팩 정비 지침 발췌(영한)', 'C', '참고(제조사)', '2024-06-01', '설비보전팀', '', 'OEM-HPP45A_정비지침_영한.md', '영문 원본과 사내 번역'),
    ('OEM-HPP45B-MM', 'HPP-45B 유압 파워팩 정비 지침', '', '참고(제조사)', '', '설비보전팀', '', None, '제조사에 요청 중'),
    ('DC-01', '문서 관리 기준', '3.0', '현행', '2025-01-01', '품질경영팀', '', 'DC-01_문서관리기준.md', ''),
]
REGISTER_COLS = ['문서 식별자', '제목', '판', '상태', '시행일', '소유 부서', '대체 관계', '파일', 'SHA-256', '비고']
ENCODINGS = {'SR-04_설비안전규정_발췌.txt': 'cp949'}   # 이 밖의 파일은 UTF-8
REGISTER_FILE = '문서_목록.csv'


def row(doc, rev):
    for r in REGISTER:
        if (r[0], r[2]) == (doc, rev):
            return dict(zip(['문서 식별자', '제목', '판', '상태', '시행일', '소유 부서', '대체 관계', '파일', '비고'], r))
    raise KeyError((doc, rev))


def texts():
    """{파일: 글} — 문서 열 개."""
    return {'HM-8_1.0판_매뉴얼.md': HM8_OLD, 'HM-8_매뉴얼.md': hm8_copy(), 'HM-8_1.2판_개정요청.md': hm8_draft(), 'HM-9장_스캔본.txt': scan_text(),
            'SR-04_설비안전규정_발췌.txt': sr04_text(), 'PM-02_정기점검표.md': sample('PM-02_powerpack-pm-checklist.md', PM02_TAGS()),
            'PR-07_예비품기준.md': sample('PR-07_spare-parts-standard.md', PR07_TAGS()), 'HI-01_보충매뉴얼.md': hi01_copy(),
            'OEM-HPP45A_정비지침_영한.md': OEM, 'DC-01_문서관리기준.md': DC01}


def register_text(files, docs=None):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow([f'# 문서 관리 시스템 문서 목록 내보내기 {BASE.isoformat()} 07:30 — {DOC_NOTICE}'])
    w.writerow(REGISTER_COLS)
    for doc, title, rev, status, date, owner, repl, name, note in REGISTER:
        if docs is not None and doc not in docs:
            continue
        w.writerow([doc, title, rev, status, date, owner, repl, name or '', hashlib.sha256(files[name]).hexdigest() if name else '', note])
    return buf.getvalue()


def bundle(check=True):
    """{자료 안 이름: 바이트} — 문서 열 개와 문서 목록. check면 설계 조건 검사를 돌리고, 어긋나면 멈춘다."""
    files = {name: text.encode(ENCODINGS.get(name, 'utf-8')) for name, text in texts().items()}
    files[REGISTER_FILE] = register_text(files).encode('utf-8')
    if check:
        design_checks(files)
    return files


# ───────────── 설계 조건 검사(구성안 3.3 — 2~8, 9는 --check) ─────────────

def squash(text):
    """글자 · 숫자만 남기고 소문자로(main manual_locate._squash와 같은 비교)."""
    return ''.join(c for c in text.lower() if c.isalnum())


def design_checks(files):
    bad = []
    decoded = {n: b.decode(ENCODINGS.get(n, 'utf-8')) for n, b in files.items()}
    # 2. 문서 목록 — SHA = 실제 파일, 파일 없는 행 하나, (식별자, 판) 유일
    rows = list(csv.reader(io.StringIO(decoded[REGISTER_FILE])))[2:]
    keys = [(r[0], r[2]) for r in rows]
    if len(set(keys)) != len(keys):
        bad.append('문서 목록: (식별자, 판)이 겹침')
    if sum(1 for r in rows if not r[7]) != 1:
        bad.append('문서 목록: 파일 없는 행이 하나가 아님')
    listed = {r[7] for r in rows if r[7]}
    if listed != set(files) - {REGISTER_FILE}:
        bad.append(f'문서 목록의 파일과 문서가 다름: {sorted(listed ^ (set(files) - {REGISTER_FILE}))}')
    for r in rows:
        if r[7] and hashlib.sha256(files[r[7]]).hexdigest() != r[8]:
            bad.append(f'문서 목록: {r[7]} SHA가 파일과 다름')
    # 3. SR-04는 UTF-8로 읽으면 실패하고 CP949로 읽힌다(그 글자 범위만)
    sr = files['SR-04_설비안전규정_발췌.txt']
    try:
        sr.decode('utf-8')
        bad.append('SR-04: UTF-8로 읽힘')
    except UnicodeDecodeError:
        pass
    if sr.decode('cp949').encode('cp949') != sr:
        bad.append('SR-04: CP949로 되돌려 쓴 바이트가 다름')
    # 4. 스캔본 — 주 경로 문장의 인식 오류 두 종류, 9-7쪽 없음, 목차에 HM-9.4
    scan = decoded['HM-9장_스캔본.txt']
    flat = squash(scan)
    main = scan_main()
    for s in main:
        if not any(squash(s).replace('o', '0') in squash(x).replace('o', '0') for x in scan.splitlines()):
            bad.append(f'스캔본: 주 경로 문장이 한 줄 안에 없음(쪽 경계에서 끊김) {s!r}')
    spacing = [s for s in main if s not in scan and squash(s) in flat]
    swapped = [s for s in main if s not in scan and squash(s) not in flat and squash(s).replace('o', '0') in flat.replace('o', '0')]
    if not spacing:
        bad.append('스캔본: 띄어쓰기 · 기호 오류(정확 일치 실패 · 글자 숫자 비교 성공)가 든 주 경로 문장이 없음')
    if not swapped:
        bad.append('스캔본: 글자 바뀜(고친 글로는 글자 숫자 비교도 실패, 파일 글자로는 찾힘)이 든 주 경로 문장이 없음')
    gap = scan_pages()[1]['HM-9.4'][1]
    if f'- 9-{gap} -' in scan or f'- 9-{gap - 1} -' not in scan or f'- 9-{gap + 1} -' not in scan or gap != 7:
        bad.append(f'스캔본: 9-6 · 9-8쪽이 있고 HM-9.4가 시작하는 9-7쪽이 없어야 함(지금 9-{gap})')
    if not re.search(r'HM-9\.4 트립 후 복귀 \.+ 9-7', scan):
        bad.append('스캔본: 목차에 HM-9.4(9-7쪽)가 없음')
    if scan_pages()[2] < 1:
        bad.append('스캔본: 쪽 경계에서 끊긴 문단이 없음')
    unread = [x for x in scan.splitlines() if '판독 불가' in x]
    if len(unread) != 1 or any(squash(s)[:8] in squash(unread[0]) for s in main):
        bad.append('스캔본: 판독 불가 줄이 하나이고 주 경로 문장 밖이어야 함')
    # 5. 값 — SR-04 제4조 · 9.3이 plant_model · plc와 같고, 복귀(리셋) 값이 없다(결정표 SOP-TRIP-01과 부딪칠 값 0)
    limits, M = plant()
    for name, tag, v, unit, word, cause in limits:
        if squash(f'{tag}{num(v)}{unit}{word}') not in flat:
            bad.append(f'스캔본 9.3: {tag} {num(v)} {unit} {word}이 없음')
    if f'({num(limits[0][2])} {limits[0][3]})' not in decoded['SR-04_설비안전규정_발췌.txt']:
        bad.append('SR-04 제4조: 인터록 한계가 plant_model.TRIP_TS1과 다름')
    for name in ('SR-04_설비안전규정_발췌.txt', 'HM-9장_스캔본.txt'):
        for line in decoded[name].splitlines():
            if re.search(r'리셋|복귀', line) and re.search(r'\d+ ?℃', line):
                bad.append(f'{name}: 복귀 · 리셋 조건 값이 있음 — {line}')
    if num(M.LOAD_MIN_PCT) != '60':
        bad.append('HM-9.1 펌프 부하 하한 60 %가 plant_model.LOAD_MIN_PCT와 다름')
    # 6. 꼬리표 · 면책 · 운영 말 0(CP949 파일은 풀어서)
    for name, text in decoded.items():
        for word in FORBIDDEN:
            if word in text:
                bad.append(f'{name}: 「{word}」')
        if name != REGISTER_FILE and DOC_NOTICE not in '\n'.join(text.splitlines()[:5]):
            bad.append(f'{name}: 첫머리에 가상 사례 표시가 없음')
    # 7. 초안 검토 의견 · 번역 메모 · 판독 불가 줄에 결정 지점의 답 · 처리법 0
    notes = [x for x in decoded['HM-8_1.2판_개정요청.md'].splitlines() if '검토 의견' in x] + [OEM_MEMO] + unread
    answer = ('사내 기준', '작업 근거', '따른다', '따를', '근거가 아니', '인용', '원본을 확인', '확인을 요청', '채택', '보류', '코어', '유온 차', '쓰지 말', '승인')
    for x in notes:
        if x.startswith('표시:') or x.startswith('변경 요청'):
            continue
        hit = [a for a in answer if a in x]
        if hit:
            bad.append(f'답 · 처리법 낱말 {hit}: {x}')
    if OEM_MEMO not in decoded['OEM-HPP45A_정비지침_영한.md']:
        bad.append('제조사 지침: 번역 메모가 없음')
    # 8. 제조사 지침 머리말 · DC-01에 「사내 기준이 정하지 않은 항목」을 정하는 문장 0
    for name, text in [('제조사 지침 머리말', OEM.split(OEM_HEAD_END)[0]), ('DC-01', DC01)]:
        if '정하지 않은' in text or '정하지 않는' in text:
            bad.append(f'{name}: 사내 기준이 정하지 않은 항목을 정하는 문장')
    if bad:
        raise RuntimeError('문서 자료 설계 조건 검사 실패:\n- ' + '\n- '.join(bad))


def write_bundle(folder, docs=None, sub='자료', register_sub=None):
    """folder/sub/에 문서를, folder/register_sub(없으면 sub)/에 문서 목록을 쓴다. docs(문서 식별자 집합)가 있으면 그 문서의 행 · 파일만."""
    files = bundle()
    keep = {r[7] for r in REGISTER if r[7] and (docs is None or r[0] in docs)}
    dest = Path(folder)/sub
    dest.mkdir(parents=True, exist_ok=True)
    for name in keep:
        (dest/name).write_bytes(files[name])
    text = files[REGISTER_FILE].decode('utf-8') if docs is None else register_text(files, docs)
    reg = Path(folder)/(register_sub or sub)
    reg.mkdir(parents=True, exist_ok=True)
    (reg/REGISTER_FILE).write_text(text, encoding='utf-8', newline='\n')
    return files


# ---------------------------------------------------------------- CMMS 작업지시 서술 내보내기
ALIAS = {'HYD-01': ['HYD-01', 'HYD-01', '1호기', 'HPU-L2-01', '#1 파워팩', 'HYD01'],
         'HYD-02': ['HYD-02', 'HYD-02', '2호기', 'HPU-L2-02', '#2 파워팩', 'HYD02'],
         'HYD-03': ['HYD-03', 'HYD-03', '3호기', 'HPU-L2-03', '#3 파워팩', 'HYD 3'],
         'HYD-04': ['HYD-04', 'HYD-04', '4호기', 'HYD04']}
CREW = ['보전1조', '보전2조', '보전1조', '보전 야간', '외주(유압)']
OPS = ['운전 A조', '운전 B조', '운전 C조']


def d(days_ago):
    return BASE - dt.timedelta(days=days_ago)


def events(r):
    """설비별 실제 일어난 일을 날짜순 사건으로 만든다. 문장은 사건마다 현장 작성자처럼 고른다."""
    ev = []

    def add(days, asset, kind, typ, broke, status, text, parts='', hours='', record='', crew=None, done=0):
        ev.append(dict(day=d(days), asset=asset, kind=kind, typ=typ, broke=broke, status=status, text=text,
                       parts=parts, hours=hours, record=record, crew=crew or r.choice(CREW), done=done))

    # 쿨러 핀 세척. 최근 이력은 포털 시뮬레이터의 세척 이력(HYD-01 21·38·55일 전, HYD-02 21일 전, HYD-03 80일 전)과 같다.
    add(55, 'HYD-01', 'fin', 'PM', '', '완료', 'CLR 핀 세척 SOP-COOL-14. 에어블로우, LOTO 확인', record='세척후 CE 83 %', done=0)
    add(38, 'HYD-01', 'fin', 'PM', '', '완료', '쿨러 핀 막힘 - 에어로 안떨어져 고압 세척기로 마무리. LOCAL/LOTO', record='CE 81', done=0)
    add(21, 'HYD-01', 'fin', 'CM', 'Y', '완료', 'COOLER_DEGRADATION 경보로 핀 청소(SOP-COOL-14대로)', record='', done=0)
    add(21, 'HYD-02', 'fin', 'PM', '', '완료', '쿨러 fin cln 에어블로우 SOP-COOL-14', record='재가동후 CE 86 %', done=1)
    add(80, 'HYD-03', 'fin', 'PM', 'N', '완료', '야간 핀 세척 (SOP-COOL-04) 압축공기', record='CE 79 %', done=0)
    add(131, 'HYD-01', 'fin', 'PM', '', '완료', 'SOP-COOL-04 핀세척. 저압수 세척 후 건조', record='CE 77', done=1)
    add(203, 'HYD-02', 'fin', 'PM', '', '완료', '열교환기 핀 청소 SOP-COOL-04', record='', done=0)
    add(244, 'HYD-01', 'fin', 'PM', '', '완료', '쿨러 청소 (먼지 많음)', record='CE 82', done=0)
    add(301, 'HYD-03', 'fin', 'PM', '', '완료', 'CLR fin 에어블로우 HM-7.6', record='CE 85 %', done=1)
    # 2,000 h · 4,000 h 정기 정비. 운전시간은 마지막 정기 정비 뒤 계수기 값.
    add(342, 'HYD-01', 'pm2k', 'PM', '', '완료', '2000h PM (SOP-PM-21). 씰킷·RTN FLT 교체, 누유 점검', 'P-PMP-SEAL 1, P-RTN-FLT 1', '1,962', 'PS1 181 bar / FS1 9.0 / VS1 0.62', done=1)
    add(226, 'HYD-01', 'pm4k', 'PM', '', '완료', '4천h 정기점검 SOP-PM-22: 2천h 1~6단계 + ACC N2 프리차지 점검, 오일샘플 의뢰', '씰킷 1, HI-RF-10 1', '2,034', 'ACC 1,390 psi(명판 1,450) / PS1 180 / FS1 9.1 / VS1 0.6', done=1)
    add(97, 'HYD-01', 'pm2k', 'PM', '', '완료', 'PM 2천 시간 - PMP 축씰 교체 RTN FLT 교체', 'P-PMP-SEAL 1, P-RTN-FLT 1', '1,915', 'PS1 179 / FS1 8.9', done=0)
    add(318, 'HYD-02', 'pm2k', 'PM', '', '완료', 'SOP-PM-21 2,000 h 점검. PS1 0 bar 확인 후 배관 개방', 'P-PMP-SEAL 1, P-RTN-FLT 1', '2,008', 'PS1 182 bar, FS1 9.2 l/min, VS1 0.58 mm/s', done=1)
    add(190, 'HYD-02', 'pm2k', 'PM', '', '완료', '2000h PM 씰 키트/필터 교체. 야간 시간 부족으로 시운전은 다음날 주간', 'P-PMP-SEAL 1, P-RTN-FLT 1', '2,236', '', done=1)
    add(62, 'HYD-02', 'pm4k', 'PM', '', '완료', '4000h PM - SOP-PM-21 1~6 + 어큐뮬레이터 프리차지 + 작동유 시료', 'P-PMP-SEAL 1, P-RTN-FLT 1', '1,987', 'ACC 96 bar / PS1 176 bar / FS1 8.7 / VS1 0.7', done=0)
    add(281, 'HYD-03', 'pm2k', 'PM', '', '완료', '2,000h 정기 - 축 씰, 리턴필터', '씰킷1 필터1', '1,940', 'PS1 183 FS1 9.3 VS1 0.55', done=1)
    add(150, 'HYD-03', 'pm4k', 'PM', '', '완료', 'SOP-PM-22 4,000 h. ACC 프리차지 1,180 psi → 재충전 1,450 psi', 'P-PMP-SEAL 1, P-RTN-FLT 1', '2,012', 'PS1 181 / FS1 9.0 / VS1 0.6', done=0)
    add(-6, 'HYD-03', 'pm2k', 'PM', '', '부품 대기', '2000h PM 예정 (SOP-PM-21). 씰 키트 2개 예약, PS1 하락 추세로 펌프 씰 같이 봄', 'P-PMP-SEAL 2 (예약)', '1,951', '', crew='보전1조')
    # 프리차지 후속 점검(OEM T-4.1). 재충전 뒤 2주/100 h 첫 점검, 변화량에 따라 다음 주기.
    add(136, 'HYD-03', 'acc', 'PM', '', '완료', 'ACC 프리차지 첫 점검 (OEM T-4.1, 재충전 2주 후)', '', '', '1,240 psi (보정 전), 20 ℃ 보정 1,262 psi', done=0)
    add(129, 'HYD-03', 'acc', 'PM', '', '완료', '어큐뮬레이터 N2 점검 - 매주', '', '', '1,235 psi', done=0)
    add(122, 'HYD-03', 'acc', 'CM', '', '완료', 'ACC 블래더 의심, 프리차지 계속 떨어짐. 재충전', '', '', '1,150 psi → 1,450 psi', done=1)
    add(48, 'HYD-02', 'acc', 'PM', '', '완료', 'ACC 프리차지 점검 OEM 4절', '', '', '1,402 psi', done=0)
    add(20, 'HYD-02', 'acc', 'PM', '', '완료', '어큐 프리차지 4주 점검', '', '', '96.1 bar', done=0)
    add(-9, 'HYD-03', 'acc', 'PM', '', '열림', 'ACC 블래더 교체 예정 - 부품 입고 대기 (HI-AB-04)', 'P-ACC-BLD 1 (입고 예정)', '', '', crew='외주(유압)')
    # 지시기로 바꾼 필터(고장 수리인데 PM으로 찍힌 것 포함)
    add(170, 'HYD-01', 'flt', 'PM', '', '완료', 'RTN FLT 지시기 적색 → 엘리먼트 교체 (OEM T-3.1)', 'HI-RF-10 1', '', '차압 8 psi (운전 온도)', done=0)
    add(77, 'HYD-03', 'flt', 'PM', '', '완료', '리턴 필터 막힘 지시 - 교체, 구 엘리먼트에 금속분 있음', 'P-RTN-FLT 1', '', '', done=0)
    add(33, 'HYD-02', 'flt', 'CM', '', '완료', 'Return filter 교체 per OEM T-3.1. 지시기 아침 냉간때 적색 → 운전온도 재확인 후에도 적색', 'P-RTN-FLT 1', '', 'dP 9 psi', done=1)
    add(5, 'HYD-01', 'flt', 'PM', '', '열림', 'RTN FLT 지시기 적색 (냉간). 운전 온도에서 재확인 요청', '', '', '', crew='운전 B조')
    # 팬 벨트·베어링
    add(260, 'HYD-02', 'fan', 'CM', 'Y', '완료', '송풍기 진동 VS1 1.1 → 벨트 처짐 18mm, 벨트 교체 SOP-FAN-12', '', '', '처짐 12 mm, 30분 시운전 CE 84 %', done=0)
    add(160, 'HYD-03', 'fan', 'PM', '', '완료', '팬 점검 SOP-FAN-11 벨트 처짐 13mm 베어링 OK', '', '', 'VS1 0.6', done=0)
    add(90, 'HYD-01', 'fan', 'CM', '', '완료', 'fan brg 소음 → 베어링 교체 (P-FAN-BRG)', 'P-FAN-BRG 1', '', 'VS1 0.5', done=1)
    add(14, 'HYD-02', 'fan', 'PM', '', '완료', 'SOP-FAN-11 팬 점검, 벨트 장력 OK', '', '', '', done=0)
    # 누유·호스·기타 고장 수리
    add(355, 'HYD-03', 'leak', 'CM', '', '완료', '토출 호스 피팅 누유 - 피팅 재체결', '', '', '', done=0)
    add(300, 'HYD-01', 'leak', 'PM', '', '완료', 'Repair leaking hose at PMP outlet', '호스 1', '', '', done=1)
    add(272, 'HYD-02', 'leak', 'CM', 'Y', '완료', '탱크 수위 낮음 - 리턴 라인 클램프 누유 수리', '', '', '수위 정상', done=0)
    add(211, 'HYD-03', 'leak', 'CM', '', '완료', 'Pmp not workin g 알람 후 재기동 OK, 원인 미상', '', '', '', done=0)
    add(184, 'HYD-01', 'leak', 'CM', '', '완료', '작동유 우윳빛 - 열교환기 점검, 수분 유입 의심 → 오일 시료', '', '', '수분 0.08 % (시험소)', done=2)
    add(140, 'HYD-02', 'leak', 'CM', '', '취소', '중복 등록 (WO 재발행)', '', '', '', done=0)
    add(110, 'HYD-03', 'leak', 'CM', '', '완료', 'PS1 하락 165 bar 아래 - 축씰 마모 의심, 씰 교체는 정기 PM 때로', '', '', 'PS1 163 bar', done=0)
    add(66, 'HYD-01', 'leak', 'CM', '', '완료', '흡입 스트레이너 세척 (소음)', '', '', '', done=0)
    add(40, 'HYD-03', 'leak', 'PM', '', '완료', 'vlv 누유 per proc 343', '', '', '', done=0)
    add(9, 'HYD-02', 'leak', 'CM', '', '열림', '펌프 토출부 미세 누유 관찰. 다음 PM때 확인', '', '', '', crew='운전 A조')
    # 같은 라인의 후속형(HPP-45B, 수냉 열교환기). 이름이 비슷한 작업이 섞인다.
    add(230, 'HYD-04', 'hx', 'PM', '', '완료', '4호기 수냉 열교환기 플레이트 세척 (스케일)', '', '', '냉각수 차압 정상', done=1)
    add(46, 'HYD-04', 'hx', 'PM', '', '완료', '열교환기 청소 - 냉각수측 스케일 제거', '', '', '', done=0)
    add(120, 'HYD-04', 'pm2k', 'PM', '', '완료', '2000h PM 씰킷(고온형)/필터 교체', 'P-PMP-SEAL-HT 1, P-RTN-FLT 1', '1,988', 'PS1 186 bar / FS1 11.2', done=1)
    # 원격 팬 최대 운전(운전원 기록)
    add(23, 'HYD-01', 'op', '운전', '', '완료', '원격 팬 100 % (SOP-COOL-11) 15분 재관측 회복', '', '', 'TS1 53.8 ℃', crew=r.choice(OPS))
    add(22, 'HYD-01', 'op', '운전', '', '완료', '팬 최대 운전 지속 - 누적 26 h, 야간 세척 대기', '', '', '', crew=r.choice(OPS))
    add(70, 'HYD-02', 'op', '운전', '', '완료', 'COOL-02 팬100+부하80, 회복', '', '', 'TS1 54.1', crew=r.choice(OPS))
    add(132, 'HYD-01', 'op', '운전', '', '완료', 'SOP-COOL-01 팬 증속, 30분 뒤 회복', '', '', '', crew=r.choice(OPS))
    # 월간 작동유 상태 점검(OEM 월 1회 또는 150 h). 빠진 달이 있다.
    for asset, skip in [('HYD-01', {4, 9}), ('HYD-02', {6}), ('HYD-03', {2, 3, 10})]:
        for m in range(13):
            if m in skip:
                continue
            look = r.choices(['맑음', '맑음', '맑음', '약간 탁함', '색 진함'], k=1)[0]
            text = r.choice(['월간 작동유 상태 점검', '작동유 색/냄새 점검 (월1회)', 'oil 상태 체크', '작동유 육안·냄새 점검'])
            add(m * 30 + r.randint(2, 9), asset, 'oil', r.choice(['PM', 'PM', '점검']), '', '완료', text, '', '', look, crew=r.choice(OPS + CREW))
    return ev


# 냉각 경보 조치 판단 묶음의 사건 전날 운전 기록(data_conditions.py 궤적과 같은 날짜 · 설비 · 조치 — 그 설계 조건 검사가 대조한다).
# 아래 이력 뒤에 이어 번호를 붙이고 값을 정해 둔다 — 난수를 쓰지 않아 앞 이력의 번호 · 값이 바뀌지 않는다.
INCIDENT_EVE = [
    dict(days=2, asset='HYD-02', typ='운전', text='원격 팬 100 % (SOP-COOL-11) 15분 재관측 미회복, 경보 계속', crew='운전 C조'),
    dict(days=2, asset='HYD-02', typ='운전', text='주간 계획 부하 80 %로 경보 해제. 팬 100 % 유지, 핀 세척 일정 미정', crew='운전 A조'),
]


def work_orders():
    r = random.Random(SEED)
    rows = []
    for e in sorted(events(r), key=lambda e: (e['day'], e['asset'], e['kind'])):
        rows.append(e)
    out = []
    for n, e in enumerate(rows, 1):
        requested = e['day'] - dt.timedelta(days=r.choice([0, 0, 1, 2]))
        planned = e['day'].isoformat() if e['status'] in ('열림', '부품 대기') else ''
        if requested >= BASE:
            requested = BASE - dt.timedelta(days=r.choice([1, 2, 3]))
        finished = '' if e['status'] in ('열림', '부품 대기', '취소') else (e['day'] + dt.timedelta(days=e['done'])).isoformat()
        alias = r.choice(ALIAS[e['asset']])
        broke = e['broke'] if e['broke'] else r.choice(['', '', '', 'N'])
        out.append([f'WO-{requested.year}-{4100 + n:05d}', alias, requested.isoformat(), planned, finished, e['typ'], broke,
                    e['status'], e['text'], e['parts'], e['hours'], e['record'], e['crew']])
    for n, e in enumerate(INCIDENT_EVE, len(rows) + 1):   # 운전원이 그날 남긴 기록 — 요청일 · 완료일 = 사건 날
        day = d(e['days']).isoformat()
        out.append([f'WO-{d(e["days"]).year}-{4100 + n:05d}', e['asset'], day, '', day, e['typ'], '', '완료', e['text'], '', '', '', e['crew']])
    return out


def work_order_text():
    """CMMS 작업지시 내보내기 CSV 글(문서 지식 묶음 · 냉각 경보 조치 판단 묶음이 함께 쓰는 한 벌)."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow([f'# CMMS 작업지시 내보내기 {BASE.isoformat()} 07:30 — {DOC_NOTICE}'])
    w.writerow(['작업지시', '설비', '요청일', '예정일', '완료일', '작업유형', '고장', '상태', '작업 내용', '사용 부품', '운전시간(h)', '측정·시운전 기록', '작업자'])
    rows = work_orders()
    w.writerows(rows)
    return buf.getvalue(), len(rows)


STOCK = [
    # 품번, 품명, 제조사 품번, 단위, 현재고, 예약, 예약 근거, 입고 예정, 입고 예정일, 발주 상태
    ('P-PMP-SEAL', '펌프 축 씰 키트', 'HI-SK-45A', '개', 3, 2, 'HYD-03 2,000 h PM 예약', 6, '2026-11-03', '발주 확정(B-OEM)'),
    ('P-PMP-SEAL-HT', '펌프 축 씰 키트(고온형 FKM)', 'HI-SK-45B', '개', 2, 0, '', 0, '', ''),
    ('P-RTN-FLT', '리턴 필터 엘리먼트 10µm', 'HI-RF-10', '개', 1, 1, 'HYD-02 다음 정기 정비 예약', 4, '2026-10-31', '발주 확정(B-OEM), 공급사 납기 회신 없음'),
    ('P-FAN-BRG', '팬 베어링', '6205-2RS', '개', 3, 0, '', 0, '', ''),
    ('P-CLR-CORE', '쿨러 코어', 'HI-CC-45A', '개', 2, 0, '', 0, '', ''),
    ('P-ACC-BLD', '어큐뮬레이터 블래더 4L', 'HI-AB-04', '개', 0, 0, '', 1, '2026-11-12', '발주 확정(B-OEM)'),
    ('P-HYD-OIL', '작동유 ISO VG46 (20 L)', 'VG46-20L', '통', 12, 0, '', 0, '', ''),
    ('', '건조 질소 실린더 (충전용)', '', '병', '', '', '', '', '', 'ERP 재고 아님 — 공구실 대장 관리'),
]


def stock_text():
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow([f'# ERP 재고 내보내기 {BASE.isoformat()} 07:00 — {DOC_NOTICE}'])
    w.writerow(['품번', '품명', '제조사 품번', '단위', '현재고(on_hand)', '예약(reserved)', '예약 근거', '입고 예정(on_order)', '입고 예정일', '발주 상태'])
    w.writerows(STOCK)
    return buf.getvalue()


if __name__ == '__main__':
    one, two = bundle(), bundle()
    same = one == two
    for name, data in one.items():
        print(f'{name}: {data.count(b"\n")}줄 {ENCODINGS.get(name, "utf-8")} {hashlib.sha256(data).hexdigest()[:12]}')
    print(f'문서 {len(one) - 1}개 + 문서 목록, 줄 합 {sum(v.count(b"\n") for k, v in one.items() if k != REGISTER_FILE)}. 설계 조건 검사 통과.')
    print('두 번 생성 결과 동일' if same else '두 번 생성 결과 다름')
    sys.exit(0 if same else 1)
