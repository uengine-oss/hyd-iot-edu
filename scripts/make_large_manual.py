"""A092 — a realistic-size maintenance manual (thousands of lines) to measure ingestion at product scale.

    .venv314/Scripts/python scripts/make_large_manual.py tests/fixtures/manuals/HM-FULL_powerpack-manual.md

Twelve chapters of a hydraulic power unit manual (운전 · 유압 회로 · 펌프 · 쿨러 · 팬 · 작동유 · 전장 · 계측 · 보호 · 정비 ·
예비품 · 부록) in the HM-x.y section style the structured parser and the agent prompt already understand. Every
chapter has descriptive sections, parameter tables, numbered SOP procedures, conditions and prohibitions. Content is
교육용 가상 (header says so) but plausible: the numbers are the plant model's set-points and interlocks."""
import sys
from pathlib import Path

CHAPTERS = [
    (1, '개요와 안전', '유압 파워팩', ['설비 개요', '안전 수칙', '잠금 · 표지(LOTO)', '운전 모드', '문서 사용법']),
    (2, '운전', '운전 패널', ['기동 전 점검', '정상 기동', '정상 정지', '비상 정지', '원격 제어 권한', '운전 기록']),
    (3, '유압 회로', '회로', ['회로 구성', '압력 설정', '압력 상승 금지 조건', '릴리프 밸브 점검', '배관 누유 점검', '축압기']),
    (4, '펌프', '주 펌프 A', ['펌프 구조', '체적 효율 저하 징후', '예비 펌프 전환', '축 씰 교체', '커플링 정렬', '흡입 필터']),
    (5, '쿨러', '오일 쿨러', ['쿨러 구조', '냉각 효율 판정', '핀 세척', '팬 증속 운전', '냉각 회복 판정', '캐비닛 환기']),
    (6, '냉각 팬', '팬 유닛', ['팬 진동 점검', '베어링 교체', '벨트 점검', '팬 인버터 설정', '소음 점검']),
    (7, '작동유', '저유조', ['작동유 규격', '유온 관리', '열화 판정', '교환 절차', '필터 차압', '수분 관리']),
    (8, '전장과 제어', '제어반', ['제어반 구성', '인버터 보호', '비상 정지 회로', '원격 신호', '접지 점검']),
    (9, '계측', '센서', ['유온 센서 TS1', '토출 압력 PS1', '유량 FS1', '진동 VS1', '냉각 효율 CE', '교정 주기']),
    (10, '보호와 인터록', 'PLC', ['과열 인터록', '저압 인터록', '고진동 인터록', '트립 후 재기동', '리셋 권한']),
    (11, '정기 정비', '정비 계획', ['일일 점검', '주간 점검', '월간 점검', '연간 정비', '정비 기록'] ),
    (12, '예비품과 부록', '부록', ['예비품 목록', '승인 공급사', '토크 표', '용어', '개정 이력']),
]
PARTS = {4: ('P-PMP-SEAL', '펌프 축 씰 키트'), 5: ('P-CLR-CORE', '쿨러 코어'), 6: ('P-FAN-BRG', '팬 베어링')}
SETPOINTS = [('유온 TS1 정상', '48 ℃'), ('유온 경보', '55 ℃'), ('과열 인터록', '65 ℃'), ('토출 압력 정상', '182 bar'), ('저압 인터록', '130 bar'),
             ('누설 의심', '165 bar 미만 · 유량 8.0 l/min 미만'), ('팬 진동 정상', '0.6 mm/s'), ('팬 진동 경보', '1.2 mm/s'), ('고진동 인터록', '2.0 mm/s'),
             ('냉각 효율 정상', '84 %'), ('냉각 효율 경보', '70 % 미만'), ('펌프 최소 부하', '60 %'), ('팬 100 % 연속 운전 한도', '24 시간')]
VERBS = ['확인한다', '기록한다', '측정한다', '점검한다', '교체한다', '조정한다', '세척한다', '전환한다', '승인을 받는다', '보고한다']


def para(ch, title, comp, k):
    lines = [
        f"{comp}의 {title}은(는) 설비 가동률과 작동유 수명에 직접 영향을 준다. 이 절은 {title}의 목적, 판정 기준, 담당 역할을 정한다.",
        f"판정 기준은 9장 계측 항목의 현재 값을 기준으로 하며, 값이 없거나 센서가 오래된 값을 보고하면 판정을 보류하고 계측 담당에게 확인을 요청한다.",
        f"이 절의 조치는 운전 모드가 REMOTE_AUTO일 때만 원격으로 승인할 수 있다. LOCAL 또는 REMOTE_MANUAL에서는 현장 패널에서 수행한다.",
        f"기록은 CMMS 작업지시에 남기며, 작업지시 번호 없이 수행한 조치는 정비 이력으로 인정하지 않는다.",
    ]
    return lines[k % len(lines)] if k >= 0 else '\n'.join(lines)


def table(ch, i):
    rows = SETPOINTS[(ch + i) % len(SETPOINTS):][:4] or SETPOINTS[:4]
    out = ['| 항목 | 기준값 | 비고 |', '|---|---|---|']
    for n, v in rows:
        out.append(f'| {n} | {v} | 교육용 가상 설비 기준 |')
    return '\n'.join(out)


def sop(ch, i, title, comp):
    sid = f'SOP-HM{ch}-{i + 1:02d}'
    steps = []
    n = 3 + (ch * 7 + i * 3) % 6
    for s in range(1, n + 1):
        v = VERBS[(ch + i + s) % len(VERBS)]
        obj = ['현재 값', '운전 모드', '잠금 상태', '예비품 재고', '작업 구역', '관련 센서 값', '경보 상태', '작업지시 번호'][(s + i) % 8]
        extra = ''
        if s == 1:
            extra = ' (REMOTE_AUTO 확인, 아니면 중단)'
        elif s == n:
            extra = ' — CMMS에 결과를 남기고 작업지시를 닫는다'
        elif s == 2 and ch in PARTS:
            extra = f' — 예비품 {PARTS[ch][0]} {PARTS[ch][1]}은 승인 공급사(AVL) 제품만 사용한다'
        steps.append(f'{s}. {comp} {title} 작업 전 {obj}을(를) {v}{extra}.')
    cond = ['유온이 55 ℃ 이상이면 이 절차를 시작하지 않는다.', '토출 압력이 130 bar 미만이면 먼저 10장 저압 인터록 절차를 따른다.',
            '팬 진동이 2.0 mm/s 이상이면 설비를 정지한 뒤 수행한다.', '예비 펌프가 정비 중이면 전환 절차를 쓰지 않는다.'][(ch + i) % 4]
    return f"### {sid} {title} 절차\n{cond}\n" + '\n'.join(steps) + f"\n승인: {'정비관리자' if ch in (4, 6, 7, 11) else '생산관리자' if ch in (2, 3, 5) else '운전원'}. 소요 약 {15 + (ch * i) % 90}분.\n"


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('tests/fixtures/manuals/HM-FULL_powerpack-manual.md')
    # A093: `scale N` repeats the twelve chapters N times as further 설비군 (chapters 13~24, 25~36 …) with unique section/SOP
    # ids, to measure ingestion on a document two or three times the A092 size. Content realism is that of the base manual.
    scale = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    chapters = [(ch + 12 * r, name + (f' (설비군 {r + 1})' if r else ''), comp, secs) for r in range(scale) for ch, name, comp, secs in CHAPTERS]
    doc = ['# HYD 유압 파워팩 운전 · 정비 매뉴얼 (HM rev.4, 교육용 가상 문서)', '',
           '이 문서는 교육용 가상 설비(HYD-01~03)의 매뉴얼이다. 실제 제품의 사양이 아니며, 수치는 실습용 설비 모델의 설정값이다.', '',
           '## 목차', '']
    for ch, name, comp, secs in chapters:
        doc.append(f'- {ch}장 {name}')
        for j, s in enumerate(secs, 1):
            doc.append(f'  - HM-{ch}.{j} {s}')
    doc.append('')
    sop_count = 0
    for ch, name, comp, secs in chapters:
        doc += [f'# {ch}장 {name}', '', f'{comp}에 관한 장이다. ' + para(ch, name, comp, 1), '']
        for j, s in enumerate(secs, 1):
            doc += [f'## HM-{ch}.{j} {s}', '', para(ch, s, comp, j), '', para(ch, s, comp, j + 1), '', para(ch, s, comp, j + 2), '']
            doc += [f'고장 사례와 관찰 (HM-{ch}.{j})', ''] + [
                f'- 사례 {ch}-{j}-{k}: {comp} {s} 관련 {SETPOINTS[(ch * j + k) % len(SETPOINTS)][0]} 이탈({SETPOINTS[(ch * j + k) % len(SETPOINTS)][1]} 기준) — '
                f'{["원인은 핀 오염", "원인은 씰 마모", "원인은 베어링 마모", "원인은 주변 온도", "원인은 설정 오류"][k % 5]}, 조치 후 {30 + (k * 7) % 60}분 내 회복.' for k in range(1, 6)] + ['']
            if j % 2 == 1:
                doc += [f'표 HM-{ch}.{j}-1 기준값', '', table(ch, j), '']
            if ch >= 2:
                doc += [sop(ch, j - 1, s, comp)]; sop_count += 1
            if ch in (10,) and j <= 3:
                doc += ['경고: 인터록은 자동으로 해제되지 않는다. 원인 조치 없이 리셋하면 같은 트립이 재발한다.', '']
            doc += [f'참고: 관련 절 HM-{max(1, ch - 1)}.{j}, HM-{min(12, ch + 1)}.{max(1, j - 1)}. 개정 rev.4에서 기준값 표를 갱신했다.', '']
            if ch in (7, 11):
                doc += ['| 주기 | 점검 항목 | 기준 | 담당 |', '|---|---|---|---|'] + [
                    f'| {p} | {s} {k} | {v} | {r} |' for p, (k, v), r in zip(['일일', '주간', '월간', '연간'], SETPOINTS[j:j + 4], ['운전원', '운전원', '정비팀', '정비관리자'])] + ['']
    doc += ['# 폐지된 절 (참고용 보존)', '', '### SOP-OLD-01 압력 설정 상향 (구 절차, 폐지)', '누설 의심 시 압력 설정을 올리던 구 절차이며 HM-3.3에 따라 폐지됐다. 새 절차서에 제안하지 않는다.', '1. (폐지) 릴리프 설정을 올린다.', '']
    text = '\n'.join(doc)
    out.write_text(text, encoding='utf-8')
    print(f'{out} lines={text.count(chr(10)) + 1} chars={len(text)} bytes={len(text.encode("utf-8"))} sops={sop_count}')


if __name__ == '__main__':
    main()
