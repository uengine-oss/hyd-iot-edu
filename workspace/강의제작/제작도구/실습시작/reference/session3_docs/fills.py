"""강사 참조 — 문서 지식 네 랩의 정할 자리를 갈래마다 채운 판(정답 보기 토글 · 학생용 완성본 · 갈래 실행이 같이 쓴다). 학생 폴더 · ZIP에 넣지 않는다.

추출 랩(통합 04-2 · 실전 03-4): 지점5 조건의 근거(가 · 나 · 다) × 지점6 사내 문서와 제조사 지침(가 · 나). 판단 자리(나누는 단위 · 요청 글)는 강사 추출 실행 run1과 같은 판
(절 머리 + 1,000자, 강사_요청글.md) 하나다 — 이 판이면 제공 코드가 run1의 응답 기록을 그대로 다시 쓴다(다시 보내지 않음).
그래프 랩(통합 04-3 · 실전 03-5): 지점7 다른 문서의 조건(가 · 나). 판단 자리(그래프 모양 · 연결 규칙 · 별칭 · 역할)는 graph_reference.py의 강사 모양 · 연결을 표로 옮긴 판 하나다.
기본 갈래 — 추출 나-가(branches.BASE), 그래프 가(graph_reference.BASE_P7).
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
HM11, OEM, SR = 'HM-8_매뉴얼.md', 'OEM-HPP45A_정비지침_영한.md', 'SR-04_설비안전규정_발췌.txt'
TASK = 'SOP-COOL-14'
P5, P6, P7 = ('가', '나', '다'), ('가', '나'), ('가', '나')
ALL_DOCS = ['HM-8_1.0판_매뉴얼.md', 'HM-8_매뉴얼.md', 'HM-8_1.2판_개정요청.md', 'HM-9장_스캔본.txt', 'SR-04_설비안전규정_발췌.txt',
            'PM-02_정기점검표.md', 'PR-07_예비품기준.md', 'HI-01_보충매뉴얼.md', 'OEM-HPP45A_정비지침_영한.md']
MAIN_DOCS = ['HM-8_1.0판_매뉴얼.md', 'HM-8_매뉴얼.md', 'HM-8_1.2판_개정요청.md', 'HM-9장_스캔본.txt', 'SR-04_설비안전규정_발췌.txt', 'OEM-HPP45A_정비지침_영한.md']


def csv_text(header, rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


# ───────────── 추출 랩 ─────────────
SPLIT = {'단위': '절', '글자_상한': 1000, '시험_조각': f'{HM11}:77', '보낼_문서': ALL_DOCS, '쓸_기록': {}}

EXPECTED = [(HM11, 74, 'precondition'), (HM11, 77, 'step'), (HM11, 78, 'step'), (HM11, 78, 'prohibition'), (HM11, 79, 'step'), (HM11, 79, 'unit_value'),
            (OEM, 105, 'step'), (OEM, 107, 'step'), (OEM, 109, 'step'), (OEM, 109, 'unit_value'), (OEM, 112, 'prohibition'),
            (OEM, 114, 'step'), (OEM, 116, 'completion'), (OEM, 116, 'unit_value')]

UNDEFINED = '사내 기준이 정하지 않은 제조사 항목'
DIFFER = '사내 기준과 다르게 정한 항목은 사내 기준을 따른다'


def decisions(p6, rules=False):
    """검토_결정.csv 행 — (파일, 줄, 종류, 결정, 근거, 까닭, 고친_인용). 지점6: 가 = 사내 기준이 정하지 않은 제조사 항목은 보류, 나 = 까닭을 적고 채택.
    rules=True(실전반)는 판단 규칙 + 규칙 밖 행 — 줄을 비운 행이 그 파일의 기대 줄 가운데 따로 적지 않은 줄 전부에 걸린다(결정은 줄마다 판과 같음)."""
    und = '보류' if p6 == '가' else '채택'
    und_why = (f'{UNDEFINED} — 적용할지 HM-8 소유 부서(설비보전팀)에 묻는다' if p6 == '가' else f'{UNDEFINED} — 출처를 제조사 지침으로 적고 채택(머리말 7줄은 다르게 정한 항목만 사내 기준)')
    if rules:
        return [
            (HM11, '', '', '채택', f'{HM11}:74 · {HM11}:77', '현행 판(1.1) HM-8.7 근본 조치 문장과 SOP-COOL-14 단계 · 기준값 — 원문 그대로', ''),
            (HM11, 78, 'prohibition', '수정', f'{HM11}:78', '금지는 「고압수는 쓰지 않는다」 한 문장 — 단계 문장까지 인용한 것을 금지 문장으로 줄임', '고압수는 쓰지 않는다.'),
            (OEM, '', '', und, f'{OEM}:7', und_why, ''),
            (OEM, 109, 'step', '제외', f'{OEM}:109 · {OEM}:7 · {HM11}:78', DIFFER + ' — 사내는 압축공기만(78줄), 제조사는 30 psi 저압수도 허용', ''),
            (OEM, 109, 'unit_value', '제외', f'{OEM}:109 · {OEM}:7', DIFFER + ' — 30 psi 저압수 기준값', ''),
            (OEM, 112, 'prohibition', '채택', f'{OEM}:112 · {HM11}:78', '사내 기준과 같은 항목(고압수 금지) — 출처를 하나 더한다', '')]
    return [
        (HM11, 74, 'precondition', '채택', f'{HM11}:74', '현행 판(1.1) HM-8.7 — 근본 조치를 CMMS 작업지시로 내고 설비보전팀장이 승인', ''),
        (HM11, 77, 'step', '채택', f'{HM11}:77', '현행 판 SOP-COOL-14 1단계 원문 그대로', ''),
        (HM11, 78, 'step', '채택', f'{HM11}:78', '현행 판 SOP-COOL-14 2단계 원문 그대로', ''),
        (HM11, 78, 'prohibition', '수정', f'{HM11}:78', '금지는 「고압수는 쓰지 않는다」 한 문장 — 단계 문장까지 인용한 것을 금지 문장으로 줄임', '고압수는 쓰지 않는다.'),
        (HM11, 79, 'step', '채택', f'{HM11}:79', '현행 판 SOP-COOL-14 3단계 원문 그대로', ''),
        (HM11, 79, 'unit_value', '채택', f'{HM11}:79', '완료 확인의 기준값 CE 80 % 이상 — 같은 글이 23 · 31줄에도 있어 79줄(SOP-COOL-14)을 고름', ''),
        (OEM, 105, 'step', und, f'{OEM}:105; {OEM}:7', und_why + ' — 팬이 멈출 때까지 기다림', ''),
        (OEM, 107, 'step', und, f'{OEM}:107; {OEM}:7', und_why + ' — 세척 전 코어 막힘 · 휨 기록', ''),
        (OEM, 109, 'step', '제외', f'{OEM}:109; {OEM}:7; {HM11}:78', DIFFER + ' — 사내는 압축공기만(78줄), 제조사는 30 psi 저압수도 허용', ''),
        (OEM, 109, 'unit_value', '제외', f'{OEM}:109; {OEM}:7', DIFFER + ' — 30 psi 저압수 기준값', ''),
        (OEM, 112, 'prohibition', '채택', f'{OEM}:112; {HM11}:78', '사내 기준과 같은 항목(고압수 금지) — 출처를 하나 더한다', ''),
        (OEM, 114, 'step', und, f'{OEM}:114; {OEM}:7', und_why + ' — 막힘 · 휨이 남으면 코어 교체', ''),
        (OEM, 116, 'completion', und, f'{OEM}:116; {OEM}:7', und_why + ' — 30분 운전 뒤 입구 · 출구 유온 차', ''),
        (OEM, 116, 'unit_value', und, f'{OEM}:116; {OEM}:7', und_why + ' — 30분 운전', ''),
    ]


def rules(p5, practical):
    """조건_대조.csv 행 — (rule_id, 근거, match, 까닭, 요청할_것). 지점5: 가 R4 전체 근거 일치 / 나 SOP-COOL-14의 R4는 불일치 / 다 보류."""
    r4 = {'가': ('일치', '제4조 ①② 실측 유온의 인터록과 운전 중 조치 — R4 전체(네 후보)의 근거로 둔다', '없음'),
          '나': ('불일치', '원문은 운전 중 설비의 실측 유온 · 운전 중 조치, R4는 설비를 세우고 하는 작업지시(SOP-COOL-14)에 예측 유온을 건다 — 대상 · 때가 다름', 'SOP-COOL-14에서 R4를 빼 달라고 요청'),
          '다': ('보류', '원문 범위가 운전 중 조치뿐인지 안전관리 담당의 해석을 받기 전까지 정하지 않음', '안전환경팀에 제4조 범위 해석 요청')}[p5]
    out = []
    if not practical:
        out += [('R1', f'{HM11}:45; {HM11}:87', '일치', '원격 조치(SOP-COOL-11~13)를 REMOTE_AUTO에서만 — 조건표의 대상 · 조건과 같음', '없음'),
                ('R2', f'{HM11}:88', '일치', '「넘겼다면」은 초과 · 감점 20만 원 · 팬 최대 운전 조치가 조건표와 같음', '없음'),
                ('R3', f'{HM11}:71', '일치', '「이상」 · 55 ℃ · 다른 조치와 비교(경고)가 조건표와 같음', '없음')]
    out.append(('R4', '' if p5 == '다' else f'{SR}:10; {SR}:11', r4[0], r4[1], r4[2]))
    out.append(('R5', '', '원문 없음', 'HM-9.4 본문이 묶음에 없음(스캔본 목차 15줄 · 9-7쪽 빠짐) — 트립 · RESET 조건의 원문을 확인하지 못함', 'HM-9.4 종이 원본 다시 스캔 요청'))
    return out


def chosen(p5, p6):
    return [('조건의 근거', {'가': 'R4 일치', '나': 'R4 불일치(SOP-COOL-14)', '다': 'R4 보류'}[p5], f'{SR}:10 · {SR}:11 · {HM11}:77',
             {'가': '0171-051f의 SOP-COOL-14 제외가 그대로', '나': 'R4를 빼면 0171-051f의 SOP-COOL-14가 유지로 바뀜', '다': '근거 확인 중 — 판정은 그대로'}[p5]),
            ('사내 문서와 제조사 지침', {'가': '사내 기준이 정하지 않은 제조사 항목은 보류', '나': '사내 기준이 정하지 않은 제조사 항목은 채택'}[p6], f'{OEM}:7 · DC-01_문서관리기준.md:23',
             {'가': '핀 세척 조건에 팬 정지 대기 · 코어 점검 · 코어 교체 · 유온 차가 들어가지 않음', '나': '핀 세척 조건에 팬 정지 대기 · 코어 점검 · 코어 교체 · 유온 차가 들어감'}[p6]),
            ('나누는 단위', '절 머리에서 끊고 1,000자 안에서 묶음', f'{HM11}:73 · {SR}:9 · HM-9장_스캔본.txt:15', '조각 33개 — 핀 세척 절차가 한 조각 안에 남음'),
            ('요청 글', '다섯 종류 · 원문 그대로 · 판단할 것은 경고로', '입출력_계약.md:41', '어느 판을 쓸지 같은 판단은 후보가 아니라 경고로 옴')]


ROLES_EXTRACT = [('step', '잠금', '준비', f'{HM11}:77 — 첫 단계가 작업 전 정지 · 잠금이라 준비(입출력_계약.md 6절)'),
                 ('step', 'wait until the fan has stopped', '준비', f'{OEM}:105 — 작업 전 대기'), ('step', 'before cleaning', '준비', f'{OEM}:107 — 세척 전 점검'),
                 ('step', 'replace the core', '완료', f'{OEM}:114 — 끝나지 않았을 때의 처리(입출력_계약.md 4절 completion)')]


def extract_files(p5='나', p6='가', practical=False):
    """{결과/ 안의 상대 경로: 글} — 그 갈래의 정할 자리."""
    prompt = (HERE / '강사_요청글.md').read_text(encoding='utf-8')
    out = {
        '나누기.json': json.dumps({'제공 빈 틀': '채움', **SPLIT}, ensure_ascii=False, indent=2) + '\n',
        'prompt.md': prompt,
        '기대_항목.csv': csv_text(['파일', '줄', '종류'], EXPECTED),
        '검토_결정.csv': csv_text(['파일', '줄', '종류', '결정', '근거', '까닭', '고친_인용'], decisions(p6, True)),   # 두 반 모두 판단 규칙 + 규칙 밖 행
        '조건_대조.csv': csv_text(['rule_id', '근거', 'match', '까닭', '요청할_것'], rules(p5, practical)),
        '정한_것.csv': csv_text(['지점', '고른_것', '근거', '바뀌는_답'], chosen(p5, p6)),
    }
    if practical:
        out['역할.csv'] = csv_text(['종류', '인용에_든_글자', '항목', '근거'], ROLES_EXTRACT)
    return out


# ───────────── 그래프 랩 ─────────────
SHAPE = {'이름': {'문서': 'Document', '판': 'Revision', '절': 'Section', '지식': 'Knowledge', '문서의_판': 'HAS_REVISION', '판의_절': 'HAS_SECTION',
                  '지식의_출처': 'STATED_IN', '판의_대체': 'REPLACES', '규칙의_근거': 'SUPPORTS'},
         '뜻': {'문서': '회사 문서 하나(문서 목록의 문서 식별자)', '판': '문서의 한 판(문서 목록의 한 행) — 상태는 목록 그대로', '절': '판 안의 절 — 그 문서의 절 표기 그대로',
               '지식': '검토에서 승인한 후보 하나 — 원문 인용 · 줄과 검토 결정', '문서의_판': '문서 → 그 판', '판의_절': '판 → 그 판의 절', '지식의_출처': '지식 → 원문 절',
               '판의_대체': '새 판 → 대체한 옛 판(문서 목록의 대체 관계)', '규칙의_근거': '지식 → 조건표 규칙(검토의 맞는 정도 · 까닭)'},
         '판을_따로_둠': True,
         'ID': {'문서': '{문서}', '판': '{문서}@{판}', '절': '{문서}@{판}#{절}', '지식': '{문서}@{판}:{후보}'}}

LINKS = [('HM-8', '1.1', '', '절차 표기와 같은 조치', 'CONDITION_OF', '', '절차 안의 조건은 그 절차(조치)의 조건', f'{HM11}:76'),
         ('HM-8', '1.1', 'HM-8.3', '정한 대상', 'EVIDENCE_FOR', 'fm:cooler-cooling-loss', '냉각 성능 상실의 판정 근거', f'{HM11}:25'),
         ('HM-8', '1.1', 'HM-8.4', '별칭', 'EVIDENCE_FOR', '', '원인 절 — 본문의 원인 이름으로', f'{HM11}:35'),
         ('HM-8', '1.1', 'HM-8.5', '정한 대상', 'CONDITION_OF', 'SOP-COOL-11 SOP-COOL-12 SOP-COOL-13', '원격 조치의 공통 조건', f'{HM11}:45'),
         ('HM-8', '1.1', 'HM-8.6', '정한 대상', 'CONDITION_OF', 'SOP-COOL-11 SOP-COOL-12 SOP-COOL-13', '원격 조치의 회복 판정', f'{HM11}:71'),
         ('HM-8', '1.1', 'HM-8.8', '정한 대상', 'CONDITION_OF', 'SOP-COOL-11 SOP-COOL-12 SOP-COOL-13', '원격 조치의 금지와 제한', f'{HM11}:87'),
         ('HM-8', '1.1', 'HM-8.7', '정한 대상', 'CONDITION_OF', 'SOP-COOL-14 SOP-COOL-15', '근본 조치의 공통 조건 — CMMS 작업지시 · 설비보전팀장 승인', f'{HM11}:74'),
         ('HM-9', '1.0', '', '잇지 않음', '', '', '옛 판 체계의 스캔본 — 같은 내용이 현행 HM-8에 있어 출처 절에만 둠', 'HM-9장_스캔본.txt:15'),
         ('SR-04', '2024', '', '잇지 않음', '', '', '규칙 근거(검토의 rule_links)로만 잇고 조치에는 직접 잇지 않음', f'{SR}:10'),
         ('PM-02', '2.0', '', '별칭', 'APPLIES_TO', '', '정기 점검표 — 본문의 설비 · 부품 이름으로', 'PM-02_정기점검표.md:10'),
         ('HI-01', '1.0', '', '별칭', 'APPLIES_TO', '', '보충 매뉴얼 — 본문의 설비 이름으로', 'HI-01_보충매뉴얼.md:10'),
         ('OEM-HPP45A-MM', 'C', '', '별칭', 'APPLIES_TO', '', '제조사 지침 — 모델 HPP-45A · 부품 이름으로', f'{OEM}:8'),
         ('OEM-HPP45A-MM', 'C', '7', '정한 대상', 'CONDITION_OF', TASK, '제조사 코어 세척(T-7.1)은 핀 세척 작업의 조건', f'{OEM}:104'),
         ('PR-07', '1.3', '', '별칭', 'APPLIES_TO', '', '예비품 기준 — 본문의 품번 · 부품 이름으로', 'PR-07_예비품기준.md:10')]

# 실전반 카드 랩 — 카드 · 다른 작업 카드 · 공급 정보 · 지점7에 쓰는 문서만 잇는다(같은 연결 방법, 행은 카드 질문에 닿는 것만)
LINKS_CARD = [LINKS[0], LINKS[6],
              ('OEM-HPP45A-MM', 'C', '7', '정한 대상', 'CONDITION_OF', TASK, '제조사 코어 세척(T-7.1)은 핀 세척 작업의 조건', f'{OEM}:104'),
              ('PM-02', '2.0', '', '잇지 않음', '', '', '정기 점검표 — 다른 문서의 조건 표로만 이 작업에 잇는다', 'PM-02_정기점검표.md:10'),
              ('PR-07', '1.3', '', '별칭', 'APPLIES_TO', '', '예비품 기준 — 본문의 부품 이름으로(공급 정보)', 'PR-07_예비품기준.md:10')]
ALIASES_CARD = [('쿨러 코어', 'P-CLR-CORE', 'PR-07_예비품기준.md:16')]

ALIASES = [('핀 오염', 'cause:cooler-fin-fouling', f'{HM11}:38'), ('주변 온도', 'cause:ambient-temperature-rise', f'{HM11}:39'), ('팬 구동 불량', 'cause:fan-drive-fault', f'{HM11}:40'),
           ('HPP-45A', 'HYD-01 HYD-02 HYD-03', f'{OEM}:8'), ('HYD-01, HYD-02, HYD-03', 'HYD-01 HYD-02 HYD-03', 'HI-01_보충매뉴얼.md:10'), ('HYD-01~03', 'HYD-01 HYD-02 HYD-03', 'PR-07_예비품기준.md:10'),
           ('축 씰', 'P-PMP-SEAL', 'PM-02_정기점검표.md:17'), ('리턴 필터', 'P-RTN-FLT', 'PM-02_정기점검표.md:20'), ('팬 베어링', 'P-FAN-BRG', 'PR-07_예비품기준.md:15'),
           ('쿨러 코어', 'P-CLR-CORE', 'PR-07_예비품기준.md:16'), ('P-PMP-SEAL', 'P-PMP-SEAL', 'PR-07_예비품기준.md:14'), ('P-FAN-BRG', 'P-FAN-BRG', 'PR-07_예비품기준.md:15'),
           ('P-CLR-CORE', 'P-CLR-CORE', 'PR-07_예비품기준.md:16')]

ROLES_GRAPH = [('precondition', '승인', '승인', f'{HM11}:74 — 승인 문장'), ('precondition', '', '준비', '입출력_계약.md 1절 precondition'),
               ('prohibition', '', '금지', '입출력_계약.md 1절 prohibition'), ('completion', '', '완료', '입출력_계약.md 1절 completion'),
               ('step', '', '순서', '입출력_계약.md 1절 step'), ('unit_value', '', '완료', f'{HM11}:79 — 조치의 기준값은 완료 확인의 값')]

OTHER = {'가': [('PM-02', '2.0', 'PM-2.4', '예정된 정비 시간', TASK, '예', 'CONDITION_OF', 'PM-02_정기점검표.md:30 · HM-8_매뉴얼.md:66')],
         '나': [('PM-02', '2.0', 'PM-2.4', '예정된 정비 시간', TASK, '아니오', '', 'PM-02_정기점검표.md:10 · PM-02_정기점검표.md:30')]}

NOW = [(TASK, '쿨러 냉각 효율 CE · 유온 TS1(HYD-02)', '시계열(관측값)', f'{HM11}:79'),
       (TASK, 'PLC 운전 모드 · 상태', 'PLC 상태 수신(시계열)', f'{HM11}:77')]
NOW_P7 = {'가': [(TASK, '오늘 밤 생산 오더가 없는 시간', 'MES 생산 계획', 'PM-02_정기점검표.md:30')], '나': []}


def graph_files(p7='가', practical=False):
    values = [('q1', 'asset', 'HYD-02'), ('q3', 'sop', TASK), ('q3', 'asset', 'HYD-02'), ('q4', 'doc', 'OEM-HPP45A-MM'),
              ('q5_target', 'target', 'HYD-04:cooler'), ('q5_section', 'section', 'HM-9.4'),
              ('hold', 'ids', 'HM-9_1.0_검토.json#HM-9-M008 OEM-HPP45A-MM_C_검토.json#OEM-HPP45A-MM-M054')]
    if practical:   # 카드 랩은 카드 · 다른 작업 카드 · 제공되지 않은 것만 묻는다
        values = [('card', 'sop', TASK), ('card_other', 'sop', 'SOP-COOL-11'), ('q5_target', 'target', 'HYD-04:cooler'), ('q5_section', 'section', 'HM-9.4'),
                  ('hold', 'ids', 'HM-9_1.0_검토.json#HM-9-M008 OEM-HPP45A-MM_C_검토.json#OEM-HPP45A-MM-M054')]
    out = {
        '기대_답.csv': EXPECT_CARD if practical else EXPECT_GRAPH,
        '그래프_모양.json': json.dumps({'제공 빈 틀': '채움', **SHAPE}, ensure_ascii=False, indent=2) + '\n',
        '연결_규칙.csv': csv_text(['문서', '판', '절', '잇는_방법', '관계', '대상', '까닭', '근거'], LINKS_CARD if practical else LINKS),
        '별칭.csv': csv_text(['원문_이름', '기존_ID', '근거'], ALIASES_CARD if practical else ALIASES),
        '다른문서_조건.csv': csv_text(['문서', '판', '절', '인용에_든_글자', '작업', '잇는다', '관계', '근거'], OTHER[p7]),
        '역할.csv': csv_text(['종류', '인용에_든_글자', '항목', '근거'], [ROLES_GRAPH[0]] if practical else ROLES_GRAPH),   # 실전: 기본과 다른 것만(승인 문장 · 기준값)
        '현재값_원천.csv': csv_text(['작업', '확인할_값', '읽을_원천', '근거'], NOW + NOW_P7[p7]),
        '질문_값.csv': csv_text(['질문', '이름', '값'], values),
        '정한_것.csv': csv_text(['지점', '고른_것', '근거', '바뀌는_답'],
                               [('다른 문서의 조건', {'가': 'PM-2.4 예정된 정비 시간을 핀 세척 준비로 잇는다', '나': '잇지 않는다(PM-02의 범위는 정기 정비)'}[p7],
                                 'PM-02_정기점검표.md:30 · PM-02_정기점검표.md:10 · HM-8_매뉴얼.md:66',
                                 {'가': '질문 1 · 카드의 SOP-COOL-14 준비에 PM-2.4, 현재 값에 MES 생산 계획', '나': 'SOP-COOL-14 준비에 PM-2.4 없음'}[p7]),
                                ('그래프 모양', '문서 · 판 · 절 · 지식을 따로, ID에 판을 넣음', 'PM-02_정기점검표.md:20 · OEM-HPP45A_정비지침_영한.md:30', '다른 문서의 같은 절 번호가 겹치지 않음'),
                                ('연결 규칙', '절차 표기 = 조치, 절차 밖은 정한 조치 · 본문의 이름', f'{HM11}:76', '원격 조치 공통 절이 세 조치에 걸림')]),
    }
    return out


EXPECT_GRAPH = csv_text(['질문', '기대_답', '근거'], [
    ('질문 1 핀 세척 준비 · 승인', 'HM-8 1.1 HM-8.7 근본 조치 문장(CMMS 작업지시 · 설비보전팀장 승인)', f'{HM11}:74'),
    ('질문 1 핀 세척 단계 · 금지 · 완료', 'HM-8 1.1 SOP-COOL-14 세 단계, 고압수 금지, CE 80 % 이상 확인', f'{HM11}:77 · {HM11}:78 · {HM11}:79'),
    ('질문 1 원격 조치 공통 조건', 'HM-8 1.1 HM-8.5 · 8.6 · 8.8의 조건이 SOP-COOL-11~13에', f'{HM11}:45 · {HM11}:71 · {HM11}:87'),
    ('질문 2 규칙 근거', 'R1~R3 일치(HM-8 1.1), R4 불일치(SR-04 제4조), R5 원문 없음', f'{HM11}:45 · {HM11}:88 · {HM11}:71 · {SR}:10'),
    ('질문 3 현재 값 원천', '냉각 효율 CE · 유온은 시계열, 생산 오더가 없는 시간은 MES', f'{HM11}:79 · PM-02_정기점검표.md:30')])
EXPECT_CARD = csv_text(['질문', '기대_답', '근거'], [
    ('준비 조건', 'CMMS 작업지시(정지 · LOCAL · 잠금은 작업 순서 1단계)', f'{HM11}:74 · {HM11}:77'),
    ('금지 · 제한', '고압수는 쓰지 않는다(사내 · 제조사)', f'{HM11}:78 · {OEM}:112'),
    ('작업 순서', 'SOP-COOL-14 세 단계 — 정지 · LOCAL · 잠금, 압축공기 세척, CE 80 % 확인', f'{HM11}:77 · {HM11}:79'),
    ('완료 기준', '재가동 후 CE 80 % 이상', f'{HM11}:79'),
    ('작업 직전 확인할 현재 값', 'CE · 유온(시계열), PLC 운전 모드', f'{HM11}:79'),
    ('승인', '설비보전팀장', f'{HM11}:74'),
    ('남은 질문', '제조사 항목 보류분 · R4 · HM-9.4', f'{OEM}:107 · {SR}:10')])
