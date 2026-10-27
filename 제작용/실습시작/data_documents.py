"""실전반 온라인3 문서 지식화 랩(실습3·4·5)의 현업형 자료 묶음 생성 — 교육용 가상 자료.

근거: 문서/교재/근거/2026-10-28_현업데이터_현실성_조사.md §4.4·4.5(문제 유형 E1·E2·E3·E6·E8·B1~B5·D3·D6).
승인 원문(HM-8 1.1·PM-02·PR-07·HI-01)은 바꾸지 않고 복사만 한다. 이 파일이 만드는 것:
  - HM-8 1.0판(폐기, 시드 절 번호 HM-3.x·HM-7.x·HM-9.x와 SOP-COOL-01~05 체계)
  - 제조사 정비 지침 영한 발췌(OEM-HPP45A-MM, psi·µm·°C, 이중·적응 주기, 압력 0 확인)
  - CMMS 작업지시 서술 내보내기(약어·별칭·오분류·고장 칸 빈값·절차 참조·구 절차 ID)
  - ERP 재고 내보내기(현재고·예약·입고 예정 분리, 제조사 품번, ERP 밖 소모품)
  - 문서 목록(판·상태·시행일·해시)
고정 시드라 몇 번을 실행해도 같은 바이트가 나온다(`python data_documents.py --check`로 확인).
"""
from pathlib import Path
import csv
import datetime as dt
import hashlib
import io
import random
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / '문서/시스템/참조/수업_문서_원문'
SEED = 20261028
BASE = dt.date(2026, 10, 28)          # 수업일. 작업지시·재고 내보내기의 기준일
EDU = '교육용 가상 자료(공개 현업 문제 유형을 따라 생성). 실제 회사·제조사·설비의 기록이 아니다.'

HM8_OLD_FILE = 'HM-8_rev1.0_cooler-fan-manual.md'
OEM_FILE = 'OEM-HPP45A-MM_maintenance-excerpt.md'

HM8_OLD = f'''# 유압 파워유닛 쿨러 팬 정비 매뉴얼 (HM-8, 교육용 예시)

판: 1.0 / 시행 2025-03-10 / 현장 정비실 게시본을 전사함
{EDU}
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

## HM-9.1 펌프 부하 하한
펌프 부하는 60 % 아래로 내리지 않는다(최소 부하 인터록).

## HM-9.2 금지와 제한
- 원격 조치(SOP-COOL-01~03)는 REMOTE_AUTO가 아닐 때 쓰지 않는다.
- 팬 100 % 연속 운전이 24시간을 넘으면 팬 수명이 줄어든다.
'''

OEM = f'''# HPP-45A Hydraulic Power Pack — Maintenance Manual (Excerpt) / HPP-45A 유압 파워팩 정비 지침 (발췌)

Hanil Hydraulics, Document OEM-HPP45A-MM, Rev. C (2024-06) / 한일유압 문서 OEM-HPP45A-MM, C판(2024-06)
{EDU} 수치는 교육용이다.

이 발췌는 제조사 영문 원본(EN)과 설비보전팀 사내 번역(KO)을 함께 적었다. 번역은 참고이며 뜻이 다르면 영문 원본을 따른다.
회사 기준과의 관계: PM-02와 같은 항목을 다르게 정하면 PM-02(회사 기준)를 따르고, PM-02가 정하지 않은 항목은 이 발췌를 따른다.
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
'''

# 문서 목록: (식별자, 판, 상태, 시행일, 파일 또는 None, 제목, 비고). 파일 None은 등록만 있고 문서가 없는 행.
REGISTER = [
    ('HM-8', '1.0', '폐기', '2025-03-10', HM8_OLD_FILE, '유압 파워유닛 쿨러 팬 정비 매뉴얼', '2026-09-01 1.1판으로 대체. 현장 정비실 게시본 전사'),
    ('HM-8', '1.1', '현행', '2026-09-01', 'HM-8_cooler-fan-manual.md', '유압 파워유닛 쿨러 팬 정비 매뉴얼', '절 번호 체계 변경, 안전 조항 보완. 포털 수업용 승인 원문과 같은 판'),
    ('HM-8', '1.2', '개정 요청(미승인)', '', None, '유압 파워유닛 쿨러 팬 정비 매뉴얼', '변경 요청 CR-2026-031 검토 중. 배포 파일 없음'),
    ('PM-02', '2.0', '현행', '2026-01-15', 'PM-02_powerpack-pm-checklist.md', '유압 파워팩 정기 점검표와 시행 기준', '포털 수업용 승인 원문과 같은 판'),
    ('PR-07', '1.3', '현행', '2026-04-01', 'PR-07_spare-parts-standard.md', '예비품 관리 · 구매 기준서', '포털 수업용 승인 원문과 같은 판'),
    ('HI-01', '1.0', '보충', '2026-10-27', 'HI-01_shift-inspection-supplement.md', '설비 점검·이상 확인 보충 매뉴얼', '기존 HM-8·PM-02·PR-07을 대체하지 않는 보충 문서'),
    ('OEM-HPP45A-MM', 'C', '참고(제조사)', '2024-06-01', OEM_FILE, 'HPP-45A 유압 파워팩 정비 지침 발췌(영한)', '영문 원본과 사내 번역. 회사 기준과의 관계는 문서 머리말'),
]


def doc_text(name):
    """자료/원문에 둘 파일의 내용. 승인 원문은 그대로 읽고, 생성 문서는 위 본문을 쓴다."""
    if name == HM8_OLD_FILE:
        return HM8_OLD.encode('utf-8')
    if name == OEM_FILE:
        return OEM.encode('utf-8')
    path = SRC / name
    if not path.is_file():
        raise FileNotFoundError(f'승인 원문이 없습니다: {path}')
    return path.read_bytes()


def write_documents(folder, ids):
    """folder/자료/원문/에 문서를 쓰고 folder/자료/문서_목록.csv를 만든다. ids는 (식별자, 판) 집합."""
    dest = Path(folder) / '자료/원문'
    dest.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(['문서 식별자', '판', '상태', '시행일', '파일', 'SHA-256', '제목', '비고'])
    for doc, rev, status, date, name, title, note in REGISTER:
        if (doc, rev) not in ids:
            continue
        digest = ''
        if name:
            data = doc_text(name)
            (dest / name).write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
        w.writerow([doc, rev, status, date, name or '', digest, title, note])
    (Path(folder) / '자료/문서_목록.csv').write_text(buf.getvalue(), encoding='utf-8')


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
    return out


def write_work_orders(path):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow([f'# CMMS 작업지시 내보내기 {BASE.isoformat()} 07:30 — {EDU}'])
    w.writerow(['작업지시', '설비', '요청일', '예정일', '완료일', '작업유형', '고장', '상태', '작업 내용', '사용 부품', '운전시간(h)', '측정·시운전 기록', '작업자'])
    rows = work_orders()
    w.writerows(rows)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(buf.getvalue(), encoding='utf-8')
    return len(rows)


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


def write_stock(path):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow([f'# ERP 재고 내보내기 {BASE.isoformat()} 07:00 — {EDU}'])
    w.writerow(['품번', '품명', '제조사 품번', '단위', '현재고(on_hand)', '예약(reserved)', '예약 근거', '입고 예정(on_order)', '입고 예정일', '발주 상태'])
    w.writerows(STOCK)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(buf.getvalue(), encoding='utf-8')


def write_all(folder, ids, records=False):
    write_documents(folder, ids)
    if records:
        write_work_orders(Path(folder) / '자료/기록/작업지시_서술.csv')
        write_stock(Path(folder) / '자료/기록/재고_현황.csv')


ALL = {(r[0], r[1]) for r in REGISTER}

if __name__ == '__main__':
    import tempfile
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        for t in (a, b):
            write_all(t, ALL, records=True)
        same = all((Path(a) / p.relative_to(b)).read_bytes() == p.read_bytes() for p in Path(b).rglob('*') if p.is_file())
        files = sorted(p.relative_to(a).as_posix() for p in Path(a).rglob('*') if p.is_file())
        for f in files:
            data = (Path(a) / f).read_bytes()
            print(f'{f}: {data.count(b"\n")}줄 {hashlib.sha256(data).hexdigest()[:12]}')
        print('두 번 생성 결과 동일' if same else '두 번 생성 결과 다름')
        sys.exit(0 if same else 1)
