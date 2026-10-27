"""온라인 2회차 실습3·4(두 반) 원자료 생성기 — 교육용 가상 사례(실제 HYD 시스템 구조 기반).

근거: 문서/교재/근거/2026-10-28_현업데이터_현실성_조사.md §2·§4.1·§4.2.
- 태그·정상값·표본 주기·수집 방식: ot/plant-sim/plantsim/plant.py tags(), thermal.py UnitState, hydcommon/daq_contract.py
- 품번·공급·재고 기준값: it/enterprise-sim/entsim/data.py (_PART_QUOTES·_SUPPLIERS·SPARE_BASE), PR-07
- 실라버스 고정 대상: P-PMP-SEAL → HYD-01·02·03, 유효 공급 조건 3행(A정밀 35/0.12/2, B-OEM 55/0.02/5, C트레이딩 비승인 20/0.30/1)

이 파일은 두 가지를 낸다.
1. write_sources(): 학생이 읽는 원자료 CSV·현장 메모(사람이 만든 기록처럼 표기가 섞여 있음)
2. TRUTH: 생성에 쓴 정답 구조(강사 참조의 독립 대조용). 학생 폴더에는 들어가지 않는다.
고정 시드라 몇 번을 실행해도 같은 바이트가 나온다.
"""
from pathlib import Path
import csv
import io
import random

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'산출물/통합반/실습/02회차/랩/02일차_실습3_온톨로지설계/자료'
REF_DATE = '2026-10-15'   # 자료 추출 기준일
CHANGE_DATE = '2026-10-20'
SEED = 20261015
NOTICE = '교육용 가상 사례(실제 HYD 시스템 구조 기반). 회사·사람·일련번호·금액은 수업용으로 만든 값이다.'

# ───────────── 설비 ─────────────
ASSETS = [
    # code, 설비명, 구분, 기능위치, 제조사, 모델, 일련번호, 설치일, 상태, 비고
    ('HYD-01', 'HYD-01 유압 파워팩', '유압 파워팩', 'CW1-L2-HPU-01', '한일유압', 'HPP-45A', 'HP45A-19-0112', '2019-04-22', '가동', ''),
    ('HYD-02', 'HYD-02 유압 파워팩', '유압 파워팩', 'CW1-L2-HPU-02', '한일유압', 'HPP-45A', 'HP45A-19-0113', '2019-04-22', '가동', 'HYD-01과 같은 모델'),
    ('HYD-03', 'HYD-03 유압 파워팩', '유압 파워팩', 'CW1-L2-HPU-03', '한일유압', 'HPP-45A', 'HP45A-20-0207', '2020-02-17', '가동', 'HYD-01과 같은 모델'),
    ('HYD-04', 'HYD-04 유압 파워팩', '유압 파워팩', 'CW1-L2-HPU-04', '한일유압', 'HPP-45B', 'HP45B-24-0031', '2024-07-08', '가동', 'HPP-45A 후속형. 수냉식 열교환기'),
    ('HYD-05', '3라인 프레스 파워유닛 1호', '유압 파워유닛', 'CW1-L3-HPU-01', '대원하이드로', 'DPU-30', 'DW30-2101-77', '2021-01-25', '가동', '3라인 증설 때 도입'),
    ('HYD-06', '3라인 프레스 파워유닛 2호', '유압 파워유닛', 'CW1-L3-HPU-02', '대원하이드로', 'DPU-30', 'DW30-2101-78', '2021-01-25', '가동', ''),
    ('HYD-07', '이동식 예비 파워팩', '유압 파워팩(이동식)', 'CW1-MNT-SPARE-01', '한일유압', 'HPP-22M', 'HP22M-17-0009', '2017-09-11', '예비(보관)', '정비 중 대체 투입용. 통신 없음'),
]
LEGACY_ASSET = ('HPU-L2-01', '2라인 1호 유압유닛', '유압 파워팩', 'CW1-L2-HPU-01', '한일유압', 'HPP-45A', 'HP45A-19-0112', '2019-04-22', '코드 통합', '2024-03 설비코드 체계 변경 전 코드')
ASSET_COLS = ['설비코드', '설비명', '구분', '기능위치', '제조사', '모델', '일련번호', '설치일', '상태', '비고']

# ───────────── 구성요소(정비 가능 품목 수준) ─────────────
# key, 대장 이름, 계통, 정답 부품
MODEL_COMPONENTS = {
    'HPP-45A': [('cooler', '오일 쿨러', '냉각', 'P-CLR-CORE'), ('fan', '쿨러 팬', '냉각', 'P-FAN-BRG'),
                ('pump-a', '주 펌프 (A)', '동력', 'P-PMP-SEAL'), ('pump-b', '예비 펌프 (B)', '동력', None),
                ('motor', '구동 모터', '동력', None), ('coupling', '커플링', '동력', 'P-CPL-ELM'),
                ('tank', '작동유 탱크', '저장·여과', 'P-HYD-OIL'), ('rtn-filter', '리턴 필터', '저장·여과', 'P-RTN-FLT'),
                ('strainer', '흡입 스트레이너', '저장·여과', 'P-SUC-STR'), ('valve', '전환 밸브', '제어', 'P-VLV-COIL'),
                ('accumulator', '어큐뮬레이터', '제어', 'P-ACC-BLD'), ('cabinet', '제어반', '제어', None)],
    'HPP-45B': [('cooler', '수냉 열교환기', '냉각', 'P-CLR-PLT'), ('pump-a', '주 펌프 (A)', '동력', 'P-PMP-SEAL-HT'),
                ('pump-b', '예비 펌프 (B)', '동력', None), ('motor', '구동 모터', '동력', None),
                ('coupling', '커플링', '동력', 'P-CPL-ELM'), ('tank', '작동유 탱크', '저장·여과', 'P-HYD-OIL'),
                ('rtn-filter', '리턴 필터', '저장·여과', 'P-RTN-FLT'), ('strainer', '흡입 스트레이너', '저장·여과', 'P-SUC-STR'),
                ('valve', '전환 밸브', '제어', 'P-VLV-COIL'), ('accumulator', '어큐뮬레이터', '제어', 'P-ACC-BLD'),
                ('cabinet', '제어반', '제어', None)],
    'DPU-30': [('cooler', '오일 쿨러', '냉각', None), ('fan', '쿨러 팬', '냉각', 'P-BRG-6205'),
               ('pump', '메인 펌프', '동력', 'P-DPU-SEAL'), ('motor', '구동 모터', '동력', None),
               ('tank', '작동유 탱크', '저장·여과', 'P-HYD-OIL'), ('rtn-filter', '리턴 필터', '저장·여과', 'P-DPU-FLT'),
               ('valve', '전환 밸브', '제어', 'P-VLV-COIL'), ('cabinet', '제어반', '제어', None)],
    'HPP-22M': [('pump', '펌프', '동력', 'P-PMP-SEAL-22'), ('motor', '구동 모터', '동력', None),
                ('coupling', '커플링', '동력', 'P-CPL-ELM'), ('tank', '작동유 탱크', '저장·여과', 'P-HYD-OIL'),
                ('rtn-filter', '리턴 필터', '저장·여과', 'P-RTN-FLT')],
}
WRITER = {'HYD-01': '한서윤', 'HYD-02': '문태오', 'HYD-03': '남궁현', 'HYD-04': '한서윤', 'HYD-05': '오지환', 'HYD-06': '오지환', 'HYD-07': '문태오'}
# 작성자가 쓴 이름(현장에서 실제로 섞어 쓰는 말)
NAMES = {
    'HYD-02': {'cooler': '쿨러', 'fan': '팬', 'pump-a': '유압 펌프', 'pump-b': '스탠바이 펌프', 'motor': '모터', 'coupling': '커플링',
               'tank': '탱크', 'rtn-filter': '리턴 필터', 'strainer': '석션 스트레이너', 'valve': '방향 전환 밸브', 'accumulator': '어큐뮬레이터', 'cabinet': '제어 판넬'},
    'HYD-03': {'cooler': '열교환기', 'fan': '송풍기', 'pump-a': '주 펌프 A', 'pump-b': '예비 펌프 (B)', 'motor': '구동 모터', 'coupling': '축 커플링',
               'tank': '리저버', 'rtn-filter': '리턴 필터', 'strainer': '흡입 스트레이너', 'valve': '솔레노이드 밸브', 'accumulator': '축압기', 'cabinet': '제어반'},
    'HYD-05': {'cooler': '오일 쿨러(공랭)', 'fan': '쿨러 팬', 'pump': '메인 펌프', 'motor': '구동 모터', 'tank': '오일 탱크', 'rtn-filter': '리턴 필터', 'valve': '방향 제어 밸브', 'cabinet': '제어반'},
    'HYD-07': {'pump': '펌프', 'motor': '모터', 'coupling': '커플링', 'tank': '탱크', 'rtn-filter': '리턴 필터'},
}
NAMES['HYD-06'] = NAMES['HYD-05']
# 교체부품 칸에 실제로 적힌 글(품명만·품번만·변형 표기·제조사 품번·빈칸)
PART_TEXT = {
    'HYD-01': {'cooler': '쿨러 코어 (P-CLR-CORE)', 'fan': '팬 베어링 (P-FAN-BRG)', 'pump-a': '펌프 축 씰 키트 (P-PMP-SEAL)', 'coupling': '커플링 탄성체 (P-CPL-ELM)',
               'tank': '작동유 VG46 (P-HYD-OIL)', 'rtn-filter': '리턴 필터 엘리먼트 (P-RTN-FLT)', 'strainer': '흡입 스트레이너 (P-SUC-STR)',
               'valve': '솔레노이드 코일 (P-VLV-COIL)', 'accumulator': '블래더 (P-ACC-BLD)'},
    'HYD-02': {'cooler': 'P-CLR-CORE', 'fan': 'P-FAN-BRG', 'pump-a': 'PMP-SEAL', 'coupling': 'P-CPL-ELM', 'tank': 'P-HYD-OIL', 'rtn-filter': 'RF-10',
               'strainer': 'P-SUC-STR', 'valve': 'P-VLV-COIL', 'accumulator': 'P-ACC-BLD'},
    'HYD-03': {'cooler': '쿨러 코어', 'fan': '팬 베어링', 'pump-a': '', 'coupling': '커플링 고무', 'tank': '작동유', 'rtn-filter': '리턴 필터',
               'strainer': '스트레이너', 'valve': '코일', 'accumulator': '블래더'},
    'HYD-04': {'cooler': '수냉 플레이트 팩 (P-CLR-PLT)', 'pump-a': '고온형 축 씰 키트 (P-PMP-SEAL-HT)', 'coupling': 'P-CPL-ELM', 'tank': 'P-HYD-OIL',
               'rtn-filter': 'P-RTN-FLT', 'strainer': 'P-SUC-STR', 'valve': 'P-VLV-COIL', 'accumulator': 'P-ACC-BLD'},
    'HYD-05': {'fan': 'P-BRG-6205', 'pump': 'P-DPU-SEAL', 'tank': 'P-HYD-OIL', 'rtn-filter': 'P-DPU-FLT', 'valve': 'P-VLV-COIL'},
    'HYD-06': {'fan': '6205 베어링', 'pump': 'DW-PS-30', 'tank': '작동유', 'rtn-filter': 'P-DPU-FLT', 'valve': 'P-VLV-COIL'},
    'HYD-07': {'pump': 'P-PMP-SEAL-22', 'coupling': 'P-CPL-ELM', 'tank': 'P-HYD-OIL', 'rtn-filter': 'P-RTN-FLT'},
}
COMP_NOTE = {('HYD-01', 'pump-b'): '센서 없음', ('HYD-02', 'pump-a'): 'A 펌프', ('HYD-03', 'pump-a'): '교체부품 칸 확인 못 함',
             ('HYD-04', 'cooler'): '냉각수 회로(공장 냉각탑) 연결', ('HYD-05', 'cooler'): '예비품 지정 없음(코어 일체형)',
             ('HYD-06', 'cooler'): '예비품 지정 없음(코어 일체형)', ('HYD-07', 'pump'): '기어 펌프 1대(예비 펌프 없음)'}
SERIALS = {('HYD-01', 'pump-a'): 'KP-1904-221', ('HYD-02', 'pump-a'): 'KP-2603-114', ('HYD-03', 'pump-a'): 'KP-2002-087', ('HYD-04', 'pump-a'): 'KP-2407-310',
           ('HYD-05', 'pump'): 'DWP-2101-12', ('HYD-06', 'pump'): 'DWP-2101-13', ('HYD-07', 'pump'): 'GP-1709-004'}
REMOVED_PUMP = ('HYD-02', 'pump-a', 'KP-1902-551', '2026-03-11 펌프 교체로 철거(구 일련번호)')
COMP_COLS = ['설비코드', '계통', '구성요소', '교체부품', '일련번호', '작성자', '비고']

# ───────────── 예비품·품번 ─────────────
PARTS = [
    ('P-PMP-SEAL', '펌프 축 씰 키트', '주 펌프 A', 'HPP-45A', 'HYD-01~03 공용'),
    ('P-PMP-SEAL-HT', '펌프 축 씰 키트(고온형 FKM)', '주 펌프 A', 'HPP-45B', 'P-PMP-SEAL과 끼워 쓰지 않음'),
    ('P-PMP-SEAL-22', '기어 펌프 씰 키트', '펌프', 'HPP-22M', ''),
    ('P-FAN-BRG', '팬 베어링', '쿨러 팬', 'HPP-45A', 'HYD-01~03 공용'),
    ('P-BRG-6205', '볼 베어링 6205-2RS', '쿨러 팬', 'DPU-30', '3라인 자재로 등록'),
    ('P-CLR-CORE', '쿨러 코어', '오일 쿨러', 'HPP-45A', 'HYD-01~03 공용. 세척으로 회복되지 않을 때 교체'),
    ('P-CLR-PLT', '수냉 열교환기 플레이트 팩', '수냉 열교환기', 'HPP-45B', ''),
    ('P-RTN-FLT', '리턴 필터 엘리먼트 10µm', '리턴 필터', 'HPP-45A·45B·22M', ''),
    ('P-DPU-FLT', '리턴 필터 엘리먼트(DPU)', '리턴 필터', 'DPU-30', ''),
    ('P-SUC-STR', '흡입 스트레이너', '흡입 스트레이너', 'HPP-45A·45B', ''),
    ('P-ACC-BLD', '어큐뮬레이터 블래더 4L', '어큐뮬레이터', 'HPP-45A·45B', ''),
    ('P-CPL-ELM', '커플링 탄성체', '커플링', 'HPP-45A·45B·22M', ''),
    ('P-VLV-COIL', '솔레노이드 코일 24VDC', '전환 밸브', '전 모델', 'D03 밸브 공용 규격'),
    ('P-DPU-SEAL', '펌프 씰 키트(DPU)', '메인 펌프', 'DPU-30', ''),
    ('P-HYD-OIL', '작동유 ISO VG46 (20 L)', '작동유 탱크', '전 모델', '소모품'),
]
PART_COLS = ['품번', '품명', '쓰는곳', '적용모델', '비고']
CROSS = [  # 사내 품번, 다른 표기, 표기 종류, 쓰는 곳, 비고
    ('P-PMP-SEAL', 'HI-SK-45A', '제조사 품번', '한일유압 부품표', 'B-OEM 견적도 이 번호'),
    ('P-PMP-SEAL', 'AJ-S4510', '공급사 품번', 'A정밀 견적서', ''),
    ('P-PMP-SEAL', 'CT-PS-0045', '공급사 품번', 'C트레이딩 견적서', ''),
    ('P-PMP-SEAL', 'PS-4510', '구 사내 품번', '구 CMMS·입고 이력', '2024-03 품번 체계 변경 전'),
    ('P-PMP-SEAL', 'PMP-SEAL', '표기 변형', '점검표 수기', ''),
    ('P-PMP-SEAL', 'P_PMP_SEAL', '표기 변형', '구 엑셀 대장', ''),
    ('P-PMP-SEAL-HT', 'HI-SK-45B', '제조사 품번', '한일유압 부품표', ''),
    ('P-PMP-SEAL-HT', 'AJ-S4520', '공급사 품번', 'A정밀 견적서', ''),
    ('P-PMP-SEAL-22', 'HI-GS-22', '제조사 품번', '한일유압 부품표', ''),
    ('P-FAN-BRG', '6205-2RS', '제조사 품번', '베어링 규격', ''),
    ('P-FAN-BRG', 'FB-6205', '구 사내 품번', '구 CMMS', '2024-03 품번 체계 변경 전'),
    ('P-FAN-BRG', 'AJ-B6205', '공급사 품번', 'A정밀 견적서', ''),
    ('P-BRG-6205', '6205-2RS', '제조사 품번', '베어링 규격', '3라인 자재 등록 때 만든 품번'),
    ('P-CLR-CORE', 'HI-CC-45A', '제조사 품번', '한일유압 부품표', ''),
    ('P-CLR-CORE', 'AJ-C4500', '공급사 품번', 'A정밀 견적서', ''),
    ('P-CLR-CORE', 'CT-CC-450', '공급사 품번', 'C트레이딩 견적서', ''),
    ('P-CLR-PLT', 'HI-PHE-45B', '제조사 품번', '한일유압 부품표', ''),
    ('P-RTN-FLT', 'HI-RF-10', '제조사 품번', '한일유압 부품표', ''),
    ('P-RTN-FLT', 'RF-10', '표기 변형', '점검표 수기', ''),
    ('P-DPU-FLT', 'DW-RF-30', '제조사 품번', '대원하이드로 부품표', ''),
    ('P-DPU-SEAL', 'DW-PS-30', '제조사 품번', '대원하이드로 부품표', ''),
    ('P-SUC-STR', 'HI-SS-45', '제조사 품번', '한일유압 부품표', ''),
    ('P-ACC-BLD', 'HI-AB-04', '제조사 품번', '한일유압 부품표', ''),
    ('P-CPL-ELM', 'ROTEX-24-98A', '제조사 품번', '커플링 규격', ''),
    ('P-VLV-COIL', 'D03-24VDC', '제조사 품번', '밸브 규격', ''),
    ('P-HYD-OIL', 'VG46-20L', '제조사 품번', '정유상사 견적서', ''),
]
CROSS_COLS = ['사내품번', '다른표기', '표기종류', '쓰는곳', '비고']

# ───────────── 센서·태그 ─────────────
# plant-sim tags()의 17태그 + 설정값 2. tag: (계장 접두, 센서명, 붙은곳 key(None=설비 전체), 재는것, quantity, 단위, 표본Hz, 수집, 정상, 한계, 방향, kind)
HPP_TAGS = [
    ('TS1', 'TT', '유온 센서', 'cooler', '유온', 'quantity:TS1', '℃', 1, '매초 전송', 48, 65, '상한', 'measured'),
    ('TS2', 'TT', '쿨러 출구 온도 센서', 'cooler', '쿨러 출구 유온', 'quantity:TS2', '℃', 1, '30초 하트비트', 44, None, '', 'measured'),
    ('TS3', 'TT', '탱크 유온 센서', 'tank', '탱크 유온', 'quantity:TS3', '℃', 1, '예외 보고(데드밴드 0.2) · 10초 하트비트', 40, None, '', 'measured'),
    ('TS4', 'TT', '제어반 온도 센서', 'cabinet', '제어반 내부 온도', 'quantity:TS4', '℃', 1, '예외 보고(데드밴드 0.2) · 10초 하트비트', 42, None, '', 'measured'),
    ('PS1', 'PT', '토출 압력 센서', 'pump-a', '토출 압력', 'quantity:PS1', 'bar', 100, '매초 전송(1초 대표값)', 182, 130, '하한', 'measured'),
    ('PS2', 'PT', '시스템 압력 센서', 'valve', '시스템 압력', 'quantity:PS2', 'bar', 100, '30초 하트비트', 150, None, '', 'measured'),
    ('PS3', 'PT', '리턴 압력 센서', 'rtn-filter', '리턴 라인 압력', 'quantity:PS3', 'bar', 100, '30초 하트비트', 2.0, None, '', 'measured'),
    ('PS4', 'PDT', '리턴 필터 차압 센서', 'rtn-filter', '필터 차압', 'quantity:PS4', 'bar', 100, '30초 하트비트', 1.5, None, '', 'measured'),
    ('PS5', 'PT', '파일럿 압력 센서', 'valve', '파일럿 압력', 'quantity:PS5', 'bar', 100, '30초 하트비트', 8.5, None, '', 'measured'),
    ('PS6', 'PT', '파일럿 후단 압력 센서', 'valve', '파일럿 후단 압력', 'quantity:PS6', 'bar', 100, '30초 하트비트', 8.2, None, '', 'measured'),
    ('EPS1', 'JT', '모터 출력 계측', 'motor', '모터 출력', 'quantity:EPS1', 'kW', 100, '예외 보고(데드밴드 0.05) · 10초 하트비트', 2.8, None, '', 'measured'),
    ('FS1', 'FT', '유량 센서', 'pump-a', '유량', 'quantity:FS1', 'l/min', 10, '매초 전송', 9, None, '', 'measured'),
    ('FS2', 'FT', '냉각 회로 유량 센서', 'cooler', '냉각 회로 유량', 'quantity:FS2', 'l/min', 10, '30초 하트비트', 10, None, '', 'measured'),
    ('VS1', 'VT', '팬 진동 센서', 'fan', '팬 진동', 'quantity:VS1', 'mm/s', 1, '매초 전송', 0.6, 2.0, '상한', 'measured'),
    ('CE', '', '냉각 효율 (가상)', 'cooler', '냉각 효율', 'quantity:CE', '%', None, '계산값(매초)', 84, None, '', 'derived'),
    ('CP', '', '냉각 동력 (가상)', 'cooler', '냉각 동력', 'quantity:CP', 'kW', None, '계산값(예외 보고 0.1)', 1.5, None, '', 'derived'),
    ('SE', '', '시스템 효율 (가상)', None, '시스템 효율', 'quantity:SE', '%', None, '계산값(예외 보고 0.5)', 60, None, '', 'derived'),
    ('FanSpeedSP', '', '팬 속도 설정', 'fan', '팬 속도 설정값', 'quantity:FanSpeedSP', '%', None, '설정값(바뀔 때)', 60, None, '', 'setpoint'),
    ('LoadSP', '', '펌프 부하 설정', 'pump-a', '부하 설정값', 'quantity:LoadSP', '%', None, '설정값(매초)', 90, None, '', 'setpoint'),
]
LOOP = {'HYD-01': 21, 'HYD-02': 22, 'HYD-03': 23, 'HYD-04': 24, 'HYD-05': 31, 'HYD-06': 32, 'HYD-07': 91}
INSTR_INDEX = {'TS1': 1, 'TS2': 2, 'TS3': 3, 'TS4': 4, 'PS1': 1, 'PS2': 2, 'PS3': 3, 'PS4': 4, 'PS5': 5, 'PS6': 6, 'EPS1': 1, 'FS1': 1, 'FS2': 2, 'VS1': 1}
# 대원하이드로 DPU-30의 제조사 PLC 태그(3라인 게이트웨이, 5초 주기)
DPU_TAGS = [
    ('T_OIL', 'TT', 1, '오일 온도', 'cooler', '오일 온도', 'quantity:TS1', '℃', 50, 70, '상한'),
    ('T_TANK', 'TT', 3, '탱크 온도', 'tank', '탱크 온도', 'quantity:TS3', '℃', 42, None, ''),
    ('P_MAIN', 'PT', 1, '메인 압력', 'pump', '메인 압력', 'quantity:PS1', 'bar', 140, 100, '하한'),
    ('P_PILOT', 'PT', 5, '파일럿 압력', 'valve', '파일럿 압력', 'quantity:PS5', 'bar', 7.5, None, ''),
    ('Q_MAIN', 'FT', 1, '메인 유량', 'pump', '메인 유량', 'quantity:FS1', 'L/min', 12, None, ''),
    ('I_MOTOR', 'IT', 1, '모터 전류', 'motor', '모터 전류', 'quantity:I_MOTOR', 'A', 18.5, 25, '상한'),
    ('V_FAN', 'VT', 1, '팬 진동', 'fan', '팬 진동', 'quantity:VS1', 'mm/s', 0.8, 2.8, '상한'),
    ('DP_FILTER', 'PDT', 4, '필터 차압', 'rtn-filter', '필터 차압', 'quantity:PS4', 'kPa', 80, None, ''),
    ('LVL_TANK', 'LT', 1, '탱크 레벨', 'tank', '탱크 레벨', 'quantity:LVL', '%', 75, 40, '하한'),
]
QUANTITIES = {  # id: (이름, 기준 단위)
    'quantity:TS1': ('유온', '℃'), 'quantity:TS2': ('쿨러 출구 유온', '℃'), 'quantity:TS3': ('탱크 유온', '℃'), 'quantity:TS4': ('제어반 내부 온도', '℃'),
    'quantity:PS1': ('토출 압력', 'bar'), 'quantity:PS2': ('시스템 압력', 'bar'), 'quantity:PS3': ('리턴 라인 압력', 'bar'), 'quantity:PS4': ('필터 차압', 'bar'),
    'quantity:PS5': ('파일럿 압력', 'bar'), 'quantity:PS6': ('파일럿 후단 압력', 'bar'), 'quantity:EPS1': ('모터 출력', 'kW'),
    'quantity:FS1': ('유량', 'L/min'), 'quantity:FS2': ('냉각 회로 유량', 'L/min'), 'quantity:CW-FLOW': ('냉각수 유량', 'L/min'),
    'quantity:VS1': ('팬 진동', 'mm/s'), 'quantity:CE': ('냉각 효율', '%'), 'quantity:CP': ('냉각 동력', 'kW'), 'quantity:SE': ('시스템 효율', '%'),
    'quantity:FanSpeedSP': ('팬 속도 설정값', '%'), 'quantity:LoadSP': ('부하 설정값', '%'), 'quantity:I_MOTOR': ('모터 전류', 'A'), 'quantity:LVL': ('탱크 레벨', '%'),
}
SENSOR_COLS = ['설비코드', '태그', '계장태그', '센서명', '붙은곳', '재는것', '단위', '표본주기', '수집방식', '정상값', '한계', '한계구분', '비고']

# ───────────── 공급 ─────────────
QUOTES = [  # 품번칸 글, 공급사 글, 공급사품번, 승인칸, 단가, 불량률 글, 납기 글, MOQ, 견적일, 유효기한, 비고
    ('P-PMP-SEAL', 'A정밀 (저가)', 'AJ-S4510', '예', '35', '0.12', '2', '1', '2026-10-02', '2026-12-31', ''),
    ('P-PMP-SEAL', 'B-OEM (순정)', 'HI-SK-45A', '예', '55', '0.02', '5', '1', '2026-10-02', '2026-12-31', ''),
    ('P-PMP-SEAL', 'C트레이딩 (최저가 · 비승인)', 'CT-PS-0045', '아니오', '20', '0.30', '1', '5', '2026-10-02', '2026-11-30', ''),
    ('P-PMP-SEAL', 'B-OEM (순정)', 'HI-SK-45A', '예', '58', '0.02', '6', '1', '2026-04-03', '2026-06-30', ''),
    ('P-PMP-SEAL-HT', 'B-OEM (순정)', 'HI-SK-45B', '예', '82', '0.02', '10', '1', '2026-09-15', '2026-12-31', ''),
    ('P-PMP-SEAL-HT', 'A정밀', 'AJ-S4520', '예', '61', '0.09', '7', '2', '2026-09-15', '2026-12-31', ''),
    ('P-FAN-BRG', 'A정밀 (저가)', 'AJ-B6205', '예', '18', '0.10', '1', '1', '2026-07-01', '2026-12-31', ''),
    ('P-FAN-BRG', 'A정밀 (저가)', 'AJ-B6205', '예', '18', '0.10', '1', '1', '2026-10-02', '2026-12-31', ''),
    ('P-FAN-BRG', 'B-OEM (순정)', '6205-2RS', '예', '28', '0.03', '3', '1', '2026-10-02', '2026-12-31', ''),
    ('P-BRG-6205', '대한베어링', 'DB-6205-2RS', '예', '9', '0.04', '2', '10', '2026-08-10', '2027-02-28', ''),
    ('P-CLR-CORE', 'A정밀 (저가)', 'AJ-C4500', '예', '180', '0.12', '3', '1', '2026-10-02', '2026-12-31', ''),
    ('P-CLR-CORE', 'B-OEM (순정)', 'HI-CC-45A', '예', '260', '0.02', '5', '1', '2026-10-02', '2026-12-31', ''),
    ('쿨러 코어', 'C트레이딩', 'CT-CC-450', '아니오', '120', '0.20', '2', '1', '2026-10-05', '2026-11-30', '메일 견적 수기 입력'),
    ('P-CLR-PLT', 'B-OEM (순정)', 'HI-PHE-45B', '예', '140', '0.02', '14', '1', '2026-06-20', '2026-09-30', ''),
    ('P-RTN-FLT', 'A정밀', 'AJ-RF10', '예', '11', '0.04', '2', '4', '2026-10-02', '2026-12-31', ''),
    ('P-RTN-FLT', 'B-OEM(순정)', 'HI-RF-10', '예', '12', '0.01', '3', '1', '2026-10-02', '2026-12-31', ''),
    ('P-RTN-FLT', 'C트레이딩', 'CT-RF-10', '예', '8', '8%', '1', '10', '2026-09-20', '2026-12-31', '메일 견적 수기 입력'),
    ('P-ACC-BLD', 'B-OEM (순정)', 'HI-AB-04', '예', '46', '0.02', '2주', '1', '2026-09-01', '2026-12-31', ''),
    ('P-ACC-BLD', 'A정밀', 'AJ-AB04', '예', '33', '0.11', '6', '1', '2026-09-01', '2026-12-31', ''),
    ('P-DPU-SEAL', '대원하이드로', 'DW-PS-30', '예', '41', '0.03', '12', '1', '2026-08-25', '2027-02-24', ''),
    ('P-DPU-FLT', '대원하이드로', 'DW-RF-30', '예', '14', '0.02', '12', '2', '2026-08-25', '2027-02-24', ''),
    ('P-CPL-ELM', 'A정밀', 'ROTEX-24-98A', '예', '6', '0.02', '2', '2', '2026-10-02', '2026-12-31', ''),
    ('P-VLV-COIL', 'B-OEM (순정)', 'D03-24VDC', '예', '9', '0.01', '4', '1', '2026-10-02', '2026-12-31', ''),
    ('P-HYD-OIL', '정유상사', 'VG46-20L', '예', '7.5', '0', '1', '4', '2026-09-28', '2026-12-31', ''),
]
QUOTE_COLS = ['품번', '공급사', '공급사품번', '승인공급사', '단가(만원)', '불량률', '납기(일)', '최소주문수량', '견적일', '유효기한', '비고']
AVL = [  # 공급사, 품번, 승인상태, 승인일, 유효기한, 조건, 비고
    ('A정밀', 'P-PMP-SEAL', '승인', '2025-01-10', '2027-01-09', '', ''),
    ('B-OEM', 'P-PMP-SEAL', '승인', '2024-03-02', '2027-03-01', '', ''),
    ('C트레이딩', 'P-PMP-SEAL', '비승인', '', '', '', '2025-11 품질 심사 불합격'),
    ('A정밀', 'P-PMP-SEAL-HT', '승인', '2024-08-01', '2026-12-31', '', ''),
    ('B-OEM', 'P-PMP-SEAL-HT', '승인', '2024-07-01', '2027-06-30', '', ''),
    ('A정밀', 'P-FAN-BRG', '승인', '2025-01-10', '2027-01-09', '', ''),
    ('B-OEM', 'P-FAN-BRG', '승인', '2024-03-02', '2027-03-01', '', ''),
    ('대한베어링', 'P-BRG-6205', '승인', '2021-02-01', '2027-01-31', '', ''),
    ('A정밀', 'P-CLR-CORE', '조건부 승인', '2025-06-01', '2027-05-31', '입고 전수 검사', '불량률 10 % 초과 품목(PR-07 7.4)'),
    ('B-OEM', 'P-CLR-CORE', '승인', '2024-03-02', '2027-03-01', '', ''),
    ('C트레이딩', 'P-CLR-CORE', '비승인', '', '', '', ''),
    ('B-OEM', 'P-CLR-PLT', '승인', '2024-07-01', '2027-06-30', '', ''),
    ('A정밀', 'P-RTN-FLT', '승인', '2025-01-10', '2027-01-09', '', ''),
    ('B-OEM', 'P-RTN-FLT', '승인', '2024-03-02', '2027-03-01', '', ''),
    ('C트레이딩', 'P-RTN-FLT', '승인', '2026-02-15', '2027-02-14', '', '소모성 필터만 승인'),
    ('A정밀', 'P-ACC-BLD', '승인', '2024-09-01', '2026-08-31', '', ''),
    ('B-OEM', 'P-ACC-BLD', '승인', '2024-03-02', '2027-03-01', '', ''),
    ('대원하이드로', 'P-DPU-SEAL', '승인', '2021-01-10', '2027-01-09', '', ''),
    ('대원하이드로', 'P-DPU-FLT', '승인', '2021-01-10', '2027-01-09', '', ''),
    ('A정밀', 'P-CPL-ELM', '승인', '2025-01-10', '2027-01-09', '', ''),
    ('B-OEM', 'P-VLV-COIL', '승인', '2024-03-02', '2027-03-01', '', ''),
    ('정유상사', 'P-HYD-OIL', '승인', '2023-05-01', '2027-04-30', '', ''),
]
AVL_COLS = ['공급사', '품번', '승인상태', '승인일', '유효기한', '조건', '비고']
SUPPLIERS = {'A정밀': 'A정밀 (저가)', 'B-OEM': 'B-OEM (순정)', 'C트레이딩': 'C트레이딩 (최저가)', '대한베어링': '대한베어링', '대원하이드로': '대원하이드로', '정유상사': '정유상사'}
RECEIPT_COLS = ['발주번호', '품번', '공급사', '발주일', '약속납기일', '입고일', '발주수량', '입고수량', '로트', '입고검사', '비고']


def _csv(cols, rows):
    buf = io.StringIO(newline='')
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(cols)
    for r in rows:
        w.writerow(['' if v is None else v for v in r])
    return buf.getvalue()


def _num(v):
    return ('%g' % v) if isinstance(v, float) else str(v)


def asset_rows():
    rows = [list(a) for a in ASSETS]
    rows.insert(1, list(LEGACY_ASSET))   # 구 코드 행은 HYD-01 바로 아래에 이관 기록으로 남아 있다
    return rows


def model_of(code):
    return next(a[5] for a in ASSETS if a[0] == code)


def component_rows():
    rows = []
    for code, *_ in ASSETS:
        model = model_of(code)
        names = NAMES.get(code, {})
        texts = PART_TEXT[code]
        for key, name, group, _ in MODEL_COMPONENTS[model]:
            if code == REMOVED_PUMP[0] and key == REMOVED_PUMP[1]:
                rows.append([code, group, names.get(key, name), 'PMP-SEAL', REMOVED_PUMP[2], WRITER[code], REMOVED_PUMP[3]])
                rows.append([code, group, names.get(key, name), 'P-PMP-SEAL', SERIALS[(code, key)], WRITER[code], '2026-03-11 교체 설치'])
                continue
            rows.append([code, group, names.get(key, name), texts.get(key, ''), SERIALS.get((code, key), ''), WRITER[code], COMP_NOTE.get((code, key), '')])
    return rows


def _place(code, key):
    """센서 목록의 붙은곳 칸: 작성자가 그 설비에 쓴 이름."""
    if key is None:
        return '설비 전체'
    model = model_of(code)
    canon = dict((k, n) for k, n, *_ in MODEL_COMPONENTS[model])[key]
    return NAMES.get(code, {}).get(key, canon)


def sensor_rows():
    rows = []
    for code in ['HYD-01', 'HYD-02', 'HYD-03', 'HYD-04']:
        model = model_of(code)
        keys = {k for k, *_ in MODEL_COMPONENTS[model]}
        for tag, pre, name, comp, what, q, unit, hz, how, normal, limit, direc, kind in HPP_TAGS:
            if comp is not None and comp not in keys:
                continue          # HYD-04는 쿨러 팬이 없다(수냉): VS1·FanSpeedSP 없음
            instr = f'{pre}-{LOOP[code]}{INSTR_INDEX[tag]}' if pre else ''
            row = [code, tag, instr, name, _place(code, comp), what, unit, f'{hz} Hz' if hz else '', how, _num(normal), '' if limit is None else _num(limit), direc, '']
            if kind == 'derived':
                row[12] = '계기 없음. 다른 값으로 계산'
            if kind == 'setpoint':
                row[12] = 'PLC 설정값(운전원·자동 조치가 바꿈)'
            if code == 'HYD-02':
                row[5] = {'유온': '오일 온도', '냉각 효율': '쿨러 효율', '토출 압력': '펌프 압력', '유량': '토출 유량', '팬 진동': '진동'}.get(what, what)
                if tag == 'PS1': row[10] = '130 bar'
                if tag == 'FS1': row[6] = 'L/min'
            if code == 'HYD-03' and tag == 'VS1':
                row[6] = ''; row[12] = '단위 칸 비어 있음'
            if code == 'HYD-04':
                if tag == 'TS1': row[9] = '46'
                if tag == 'PS1': row[9] = '190'; row[10] = '140'
                if tag == 'FS1': row[6] = 'L/min'; row[9] = '11'
                if tag == 'CE': row[9] = '88'
                if tag == 'EPS1': row[6] = 'W'; row[9] = '3100'; row[12] = '2024년 PLC는 W로 내보냄'
                if tag == 'FS2': row[3] = '냉각수 유량 센서'; row[5] = '냉각수 유량'; row[6] = 'L/min'; row[9] = '18'; row[12] = '공장 냉각수 회로'
            rows.append(row)
            if code == 'HYD-01' and tag == 'TS1':
                rows.append([code, 'TS1', 'TT-211', 'TS1 오일 온도', '쿨러', '작동유 온도', '℃', '', '', '48', '65', '', '점검표에서 옮겨 적음'])
    for code in ['HYD-05', 'HYD-06']:
        for tag, pre, idx, name, comp, what, q, unit, normal, limit, direc in DPU_TAGS:
            note = ''
            nv = _num(normal)
            if code == 'HYD-06' and tag == 'I_MOTOR':
                nv = ''; note = '시운전 기록 못 찾음'
            rows.append([code, tag, f'{pre}-{LOOP[code]}{idx}', name, _place(code, comp), what, unit, '', '5초 주기(3라인 게이트웨이)', nv,
                         '' if limit is None else _num(limit), direc, note])
    rows.append(['HYD-07', 'TI-1', '', '유온계(현장 지시)', '탱크', '유온', '℃', '', '수기 점검(통신 없음)', '45', '', '', '투입 때만 읽음'])
    rows.append(['HYD-07', 'PI-1', '', '압력계(현장 지시)', '펌프', '토출 압력', 'bar', '', '수기 점검(통신 없음)', '140', '', '', '투입 때만 읽음'])
    return rows


def part_rows():
    return [list(p) for p in PARTS]


def receipts():
    """입고 이력(ERP 입고 화면 내보내기). P-PMP-SEAL은 손으로 고정, 나머지는 고정 시드로 만든다."""
    fixed = [
        # 발주번호, 품번 글, 공급사 글, 발주일, 약속, 입고일, 발주수량, 입고수량, 로트, 검사, 비고
        ('PO-2312-0041', 'PS-4510', 'A정밀', '2023-12-04', '2023-12-06', '2023-12-08', 4, 4, 'AJ231208', '합격', ''),
        ('PO-2402-0017', 'PS-4510', 'B-OEM', '2024-02-13', '2024-02-18', '2024-02-19', 2, 2, 'HI240219', '합격', ''),
        ('PO-2405-0102', 'P-PMP-SEAL', 'A정밀', '2024-05-20', '2024-05-22', '2024-05-24', 3, 3, 'AJ240524', '합격', ''),
        ('PO-2409-0066', 'P-PMP-SEAL', 'B-OEM', '2024-09-02', '2024-09-07', '2024-09-07', 4, 2, 'HI240907', '합격', '분할 입고 1/2'),
        ('PO-2409-0066', 'P-PMP-SEAL', 'B-OEM', '2024-09-02', '2024-09-07', '2024-09-12', 4, 2, 'HI240912', '합격', '분할 입고 2/2'),
        ('PO-2502-0031', 'P-PMP-SEAL', 'A정밀', '2025-02-10', '2025-02-12', '2025-02-13', 4, 4, 'AJ250213', '불합격 1', '불량 1개 반품, 재입고 없음'),
        ('PO-2506-0088', 'P-PMP-SEAL', 'B-OEM', '2025-06-16', '2025-06-21', '2025-06-20', 2, 2, 'HI250620', '합격', ''),
        ('PO-2603-0012', 'P-PMP-SEAL', 'B-OEM', '2026-03-02', '2026-03-07', '2026-03-10', 3, 3, 'HI260310', '합격', 'HYD-02 펌프 교체용'),
        ('PO-2609-0140', 'P-PMP-SEAL', 'A정밀', '2026-09-21', '2026-09-23', '2026-09-26', 2, 2, 'AJ260926', '합격', ''),
        ('PO-2610-0021', 'P-PMP-SEAL', 'B-OEM', '2026-10-06', '2026-10-11', '', 6, 0, '', '', '입고 예정'),
    ]
    rng = random.Random(SEED)
    plan = [('P-FAN-BRG', 'A정밀', 1, 3), ('P-FAN-BRG', 'B-OEM', 3, 2), ('P-CLR-CORE', 'B-OEM', 5, 2), ('P-CLR-CORE', 'A정밀', 3, 1),
            ('P-RTN-FLT', 'A정밀', 2, 3), ('P-RTN-FLT', 'C트레이딩', 1, 2), ('P-PMP-SEAL-HT', 'B-OEM', 10, 1), ('P-DPU-SEAL', '대원하이드로', 12, 2),
            ('P-ACC-BLD', 'B-OEM', 14, 1), ('P-HYD-OIL', '정유상사', 1, 3)]
    import datetime as dt
    rows = [list(r) for r in fixed]
    serial = 200
    for part, sup, lead, n in plan:
        for _ in range(n):
            serial += 7
            order = dt.date(2025, 1, 6) + dt.timedelta(days=rng.randrange(0, 600))
            promised = order + dt.timedelta(days=lead)
            got = promised + dt.timedelta(days=rng.choice([-1, 0, 0, 1, 2, 3]))
            qty = rng.choice([1, 2, 2, 4])
            lot = sup[:1] + got.strftime('%y%m%d')
            rows.append([f'PO-{order:%y%m}-{serial:04d}', part, sup, order.isoformat(), promised.isoformat(), got.isoformat(), qty, qty, lot, '합격', ''])
    rows.sort(key=lambda r: (r[3], r[0], r[5]))
    return rows


def memo():
    return f'''# 설비 자료 정리 메모

> {NOTICE}

작성: 설비보전팀 한서윤 · {REF_DATE}
받는 사람: 설비 지식 정리 담당

창원1공장 2라인·3라인 유압 설비 자료를 시스템별로 내려받아 보냅니다. 대장·점검표·SCADA 태그 목록·ERP·SCM 화면에서 각자 내보낸 것이라 줄마다 적는 방식이 다릅니다. 손으로 다 맞춰 보기는 어려운 양이라 정리하실 때 아래를 참고해 주세요. 기준일은 {REF_DATE}입니다.

## 1. 보낸 파일

| 파일 | 어디서 왔나 | 내용 |
|---|---|---|
| `설비_대장.csv` | CMMS 설비 대장 | 유압 설비 7대와 이관 기록 |
| `구성요소_목록.csv` | 설비별 담당자 작성 | 설비마다 정비하는 품목을 한 줄씩. HYD-01·04는 저, HYD-02·07은 문태오 님, HYD-03은 전기계장 남궁현 님, HYD-05·06은 3라인 오지환 님 |
| `센서_목록.csv` | SCADA 태그 목록 + 점검표 | 설비마다 태그를 한 줄씩 |
| `예비품_목록.csv` | 구매 기준서(PR-07)·ERP 자재 | 관리하는 예비품 |
| `품번_교차표.csv` | 구매팀 | 사내 품번과 제조사·공급사 품번, 예전 품번, 손으로 쓴 표기 |
| `공급_조건.csv` | 구매팀 백승우 님(SCM 견적) | 공급사별 견적 조건 |
| `승인공급사_목록.csv` | SCM 승인 공급사 등록 | 품목별 승인 상태와 유효기한 |
| `입고_이력.csv` | ERP 입고 화면 | 지난 발주와 실제 입고 |

## 2. 설비에 대해
- HYD-01, HYD-02, HYD-03은 같은 모델(HPP-45A)입니다. 구성과 계측 태그가 세 대 모두 같고, 예비품도 함께 씁니다.
- HYD-04는 같은 회사의 후속 모델(HPP-45B)입니다. 열교환기가 수냉식이라 쿨러 팬이 없습니다.
- HYD-05·06은 3라인 프레스용으로 다른 회사(대원하이드로) 제품입니다. 펌프가 한 대이고 PLC 태그 이름도 제조사 방식입니다.
- HYD-07은 정비 때 잠깐 붙여 쓰는 이동식 예비 파워팩입니다. 통신이 없어 계기는 현장 지시계뿐입니다.
- 2024년 3월 설비코드 체계를 바꿨습니다. 그 전 코드로 등록된 줄이 대장에 이관 기록으로 남아 있습니다.
- 기능위치는 설비가 놓인 자리, 일련번호는 그 자리에 지금 달린 실물입니다. HYD-02 주 펌프는 2026-03-11에 교체했습니다.

## 3. 사람마다 다르게 부르는 이름
같은 장치인데 적은 사람에 따라 이름이 다릅니다. 현장에서 실제로 섞어 쓰는 말이라 어느 것도 틀린 말은 아닙니다.

| 대장에 쓰는 이름 | 현장에서 함께 쓰는 말 |
|---|---|
| 오일 쿨러 | 쿨러, 열교환기, 오일 쿨러(공랭) |
| 쿨러 팬 | 팬, 송풍기 |
| 주 펌프 (A) | 펌프, 유압 펌프, 주 펌프 A, A 펌프 |
| 예비 펌프 (B) | 스탠바이 펌프 |
| 메인 펌프 | 펌프(DPU-30은 펌프가 한 대) |
| 구동 모터 | 모터 |
| 커플링 | 축 커플링 |
| 작동유 탱크 | 탱크, 리저버, 오일 탱크 |
| 흡입 스트레이너 | 석션 스트레이너, 스트레이너 |
| 전환 밸브 | 방향 전환 밸브, 방향 제어 밸브, 솔레노이드 밸브 |
| 어큐뮬레이터 | 축압기 |
| 제어반 | 제어 판넬 |

재는 값도 마찬가지입니다.

| 대장에 쓰는 이름 | 현장에서 함께 쓰는 말 |
|---|---|
| 유온 | 오일 온도, 작동유 온도, TS1 |
| 냉각 효율 | 쿨러 효율, CE |
| 토출 압력 | 펌프 압력, 메인 압력, PS1 |
| 유량 | 토출 유량, 메인 유량, FS1 |
| 팬 진동 | 진동, VS1 |
| 탱크 유온 | 탱크 온도 |

「펌프」라고만 적혀 있으면 그 설비의 주 펌프(DPU-30은 메인 펌프)를 가리킵니다. 예비 펌프는 반드시 「예비」나 「스탠바이」를 붙여 부릅니다.

## 4. 센서에 대해
- 태그 이름(TS1, PS1 …)은 한일유압 설비가 모두 같은 이름을 씁니다. 어느 설비의 값인지는 저장할 때 설비 코드로 따로 구분합니다. 계장 도면에는 TT-211처럼 루프 번호가 붙은 계장태그를 씁니다(앞 두 자리가 설비).
- 대원하이드로 설비는 T_OIL, P_MAIN처럼 제조사가 정한 태그 이름을 씁니다.
- CE·CP·SE는 계기가 달려 있지 않습니다. 다른 값으로 계산해서 얻는 값인데, 화면에는 다른 태그와 똑같이 나오므로 목록에 함께 있습니다.
- FanSpeedSP·LoadSP는 재는 값이 아니라 PLC에 넣는 설정값입니다. SCADA 목록에 같이 나와서 그대로 두었습니다.
- 표본주기는 계기가 재는 빠르기이고, 수집방식은 시스템에 저장되는 방식입니다. 「예외 보고」 태그는 값이 데드밴드 안에서 움직이면 저장하지 않고 하트비트 때만 남깁니다. 값이 안 보이는 것이 「변화 없음」인지 「수집 실패」인지는 따로 봐야 합니다.
- 「한계」 칸은 인터록이 걸리는 값이고 「한계구분」은 위로 넘을 때(상한)인지 아래로 떨어질 때(하한)인지입니다. 한계가 없는 태그는 비워 두었습니다.
- HYD-01의 TS1이 두 줄입니다. 점검표에서 옮겨 적다가 한 번 더 들어간 것으로 보입니다. 같은 센서입니다.
- HYD-02의 PS1 한계에 단위가 같이 적혀 있고, HYD-03의 VS1은 단위 칸이 비어 있습니다. HYD-04는 2024년 PLC라 모터 출력을 W로 내보냅니다. 3라인 필터 차압은 kPa입니다. 원본 그대로 두었습니다.
- 예비 펌프 (B)와 구동 모터(한일유압 설비)에 따로 붙은 계측 태그가 없는 것은 빠뜨린 것이 아닙니다.

## 5. 예비품·품번에 대해
- 구성 요소 목록의 「교체부품」 칸은 적은 사람에 따라 품명만 있거나, 품번만 있거나, 손으로 쓴 표기나 제조사 품번으로 적혀 있습니다. HYD-03의 주 펌프 줄은 칸을 채우지 못했습니다.
- 사내 품번은 2024년 3월에 바뀌었습니다. 예전 품번과 공급사·제조사 품번은 `품번_교차표.csv`에서 찾을 수 있습니다.
- 3라인 자재는 도입 때 따로 등록해서 2라인과 같은 규격 부품이 다른 사내 품번으로 있는 경우가 있습니다. 구매팀이 통합 여부를 검토하고 있습니다.

## 6. 공급에 대해
- `공급_조건.csv`는 받은 견적을 쌓아 둔 것입니다. 같은 공급사에서 다시 견적을 받은 줄, 유효기한이 지난 줄도 지우지 않고 남아 있습니다. 메일로 받은 견적 두 건은 백승우 님이 손으로 옮겼습니다.
- 견적표의 「승인공급사」 칸은 견적을 받은 날 담당자가 적은 것입니다. 구매 기준서 PR-07 7.3은 승인 여부를 SCM 등록(`승인공급사_목록.csv`)으로 정합니다.
- `입고_이력.csv`의 입고일은 실제로 물건이 들어온 날입니다. 나눠 들어온 발주는 줄이 여러 개입니다. PR-07 7.2는 리드타임을 견적이 아니라 지난 입고의 실측으로 잡게 되어 있습니다.

## 7. 이 정리로 알고 싶은 것
보전팀·구매팀에서 자주 받는 물음입니다.
- 어느 설비의 어느 구성 요소에 어떤 센서가 붙어 있는가. 같은 것을 재는 태그가 설비마다 이름이 달라도 찾을 수 있는가.
- 그 값의 정상값과 한계는 얼마인가. 지금 값이 한계를 넘었는지 견줄 수 있는가.
- 「쿨러」, 「열교환기」처럼 다른 말로 물어도 같은 장치를 찾을 수 있는가.
- 어느 구성 요소에 어떤 교체 부품이 들어가고, 그 부품을 쓰는 설비는 어디인가.
- 그 부품을 어느 공급사에서 어떤 조건으로 살 수 있는가.
'''


def write_sources(dest=SOURCE):
    dest.mkdir(parents=True, exist_ok=True)
    files = {
        '설비_대장.csv': _csv(ASSET_COLS, asset_rows()),
        '구성요소_목록.csv': _csv(COMP_COLS, component_rows()),
        '센서_목록.csv': _csv(SENSOR_COLS, sensor_rows()),
        '예비품_목록.csv': _csv(PART_COLS, part_rows()),
        '품번_교차표.csv': _csv(CROSS_COLS, CROSS),
        '공급_조건.csv': _csv(QUOTE_COLS, QUOTES),
        '승인공급사_목록.csv': _csv(AVL_COLS, AVL),
        '입고_이력.csv': _csv(RECEIPT_COLS, receipts()),
        '현장_메모.md': memo(),
    }
    for name, text in files.items():
        (dest/name).write_text(text, encoding='utf-8', newline='')
    return {name: text.count('\n') - (1 if name.endswith('.csv') else 0) for name, text in files.items()}


# ───────────── 변경분(실습4: 재적재·부분 수정) ─────────────
CHANGE_COLS = {'설비_대장_변경.csv': ['변경', *ASSET_COLS], '구성요소_변경.csv': ['변경', *COMP_COLS],
               '센서_변경.csv': ['변경', *SENSOR_COLS], '공급_조건_변경.csv': ['변경', *QUOTE_COLS], '승인공급사_변경.csv': ['변경', *AVL_COLS]}


def changes(supply):
    """기준일 뒤 들어온 수정본. 원 행 전체를 다시 적고 맨 앞에 변경 종류를 적는다."""
    a = {r[0]: list(r) for r in ASSETS}
    hyd02 = a['HYD-02'][:]; hyd02[1] = 'HYD-02 2라인 2호 파워팩'; hyd02[9] = '설비명 표준화(2026-10-20)'
    hyd07 = a['HYD-07'][:]; hyd07[8] = '불용(매각 예정)'; hyd07[9] = '2026-10-20 불용 결정. 매각 전까지 대장에 남김'
    out = {'설비_대장_변경.csv': [['수정', *hyd02], ['수정', *hyd07]],
           '구성요소_변경.csv': [['수정', 'HYD-03', '동력', '주 펌프 A', 'P-PMP-SEAL', SERIALS[('HYD-03', 'pump-a')], '남궁현', '교체부품 확인(2026-10-18)']],
           '센서_변경.csv': [['수정', 'HYD-03', 'VS1', 'VT-231', '팬 진동 센서', '송풍기', '팬 진동', 'mm/s', '1 Hz', '매초 전송', '0.6', '2.0', '상한', '단위 보완'],
                            ['수정', 'HYD-06', 'I_MOTOR', 'IT-321', '모터 전류', '구동 모터', '모터 전류', 'A', '', '5초 주기(3라인 게이트웨이)', '18.5', '25', '상한', '시운전 기록 확인'],
                            ['삭제', 'HYD-01', 'TS1', 'TT-211', 'TS1 오일 온도', '쿨러', '작동유 온도', '℃', '', '', '48', '65', '', '중복 행 정리']]}
    if supply:
        out['공급_조건_변경.csv'] = [['추가', 'P-FAN-BRG', 'A정밀 (저가)', 'AJ-B6205', '예', '19', '0.10', '1', '1', '2026-10-18', '2027-01-31', '재견적']]
        out['승인공급사_변경.csv'] = [['수정', 'A정밀', 'P-ACC-BLD', '승인', '2026-10-17', '2028-10-16', '', '재승인']]
    return out


def write_changes(dest, supply):
    dest.mkdir(parents=True, exist_ok=True)
    for name, rows in changes(supply).items():
        (dest/name).write_text(_csv(CHANGE_COLS[name], rows), encoding='utf-8', newline='')
    (dest/'README.md').write_text(f'''# {CHANGE_DATE} 수정본

> {NOTICE}

기준일({REF_DATE}) 뒤 담당자들이 고친 줄만 모은 것입니다. 각 파일은 원본과 같은 열에 맨 앞 「변경」 칸(추가·수정·삭제)이 붙어 있습니다. 「수정」 줄은 고친 뒤의 전체 값입니다.
원본 자료(`../자료/`)는 그대로 두고, 이 수정본은 이미 적재한 그래프에 반영하는 데 씁니다.
''', encoding='utf-8')


# ───────────── 생성 정답(강사 독립 대조용) ─────────────
def truth():
    """생성 규칙 그대로의 정답 구조. CSV를 다시 읽지 않는다(참조 모델과 독립)."""
    t = {'assets': {}, 'parts': {p[0]: p[1] for p in PARTS}, 'quantities': QUANTITIES}
    for code, *_ in ASSETS:
        model = model_of(code)
        comps = {k: part for k, _, _, part in MODEL_COMPONENTS[model]}
        sensors = {}
        if model in ('HPP-45A', 'HPP-45B'):
            for tag, pre, name, comp, what, q, unit, hz, how, normal, limit, direc, kind in HPP_TAGS:
                if comp is not None and comp not in comps:
                    continue
                s = dict(component=comp, quantity=q, unit=QUANTITIES[q][1], normal=float(normal), limit=None if limit is None else float(limit),
                         direction={'상한': 'upper', '하한': 'lower'}.get(direc), kind=kind)
                if code == 'HYD-04':
                    s.update({'TS1': {'normal': 46.0}, 'PS1': {'normal': 190.0, 'limit': 140.0}, 'FS1': {'normal': 11.0}, 'CE': {'normal': 88.0},
                              'EPS1': {'normal': 3.1}, 'FS2': {'quantity': 'quantity:CW-FLOW', 'normal': 18.0}}.get(tag, {}))
                sensors[tag] = s
        elif model == 'DPU-30':
            for tag, pre, idx, name, comp, what, q, unit, normal, limit, direc in DPU_TAGS:
                n = float(normal) / (100 if unit == 'kPa' else 1)
                sensors[tag] = dict(component=comp, quantity=q, unit=QUANTITIES[q][1], normal=None if (code == 'HYD-06' and tag == 'I_MOTOR') else n,
                                    limit=None if limit is None else float(limit), direction={'상한': 'upper', '하한': 'lower'}.get(direc), kind='measured')
        else:
            sensors = {'TI-1': dict(component='tank', quantity='quantity:TS1', unit='℃', normal=45.0, limit=None, direction=None, kind='measured'),
                       'PI-1': dict(component='pump', quantity='quantity:PS1', unit='bar', normal=140.0, limit=None, direction=None, kind='measured')}
        t['assets'][code] = {'model': model, 'components': comps, 'sensors': sensors}
    valid = {}
    for part, sup, _, _, price, fail, lead, *_rest in QUOTES:
        quote_date, until = _rest[1], _rest[2]
        pid = part if part.startswith('P-') else next(p[0] for p in PARTS if p[1] == part)
        sid = next(k for k in SUPPLIERS if sup.startswith(k))
        if until < REF_DATE:
            continue
        f = float(fail.rstrip('%')) / 100 if fail.endswith('%') else float(fail)
        d = int(lead[:-1]) * 7 if lead.endswith('주') else int(lead)
        prev = valid.get((sid, pid))
        if prev is None or quote_date > prev['quote_date']:
            valid[(sid, pid)] = dict(price_manwon=float(price), defect_rate=f, lead_days=d, quote_date=quote_date, valid_until=until)
    for sup, pid, status, _, until, cond, _ in AVL:
        if (sup, pid) in valid:
            ok = status in ('승인', '조건부 승인') and until >= REF_DATE
            valid[(sup, pid)].update(avl_status=status if (not until or until >= REF_DATE) else '유효기한 경과', approved_A=ok,
                                     approved_B=(status == '승인' and until >= REF_DATE), condition=cond)
    t['supply'] = valid
    return t


TRUTH = truth()

if __name__ == '__main__':
    counts = write_sources()
    print('원자료 생성:', SOURCE)
    for k, v in counts.items():
        print(f'  {k}: {v}행')
