"""강사 참조 — 판정 랩 두 결정 지점의 갈래 구현과, 그 갈래로 제공 흐름(judgement_tools/judge_tools.py)을 돌리는 입구. 학생 폴더 · ZIP에 넣지 않는다.

일반 로직(판단 입력 · 판정 · 비교 · 결과 쓰기)은 학생 폴더에 제공하는 judge_tools.py 한 벌이다 — 여기에는 사본을 두지 않는다.
여기에 있는 것은 학생이 `결과/gap_rule.py` · `결과/compare_rule.py`에 채우는 두 자리의 갈래 답과, 학생이 `결과/정한_것.csv`에 적는 고른 것의 강사 문장이다.
- 지점3 빈 값의 뜻(--gap): carry = 판정 요청 때 PLC 팬 설정이 100 %면 끊긴 구간을 잇고 마지막 기록에 경과를 더한다 / unknown = 잇지 않고 값 없음
- 지점4 쓰는 사람에 따라 갈리는 답(--warned): compare = 경고 후보도 견준다 / skip = 경고 후보는 견주지 않는다
사용: python judge_actions.py <실습 폴더> <결과 폴더> [--table 조건표] [--sop sop.json] [--gap carry|unknown] [--warned compare|skip] [--review]
"""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'judgement_tools'))
import judge_tools as T  # noqa: E402
from judge_tools import (GRACE_S, HEARTBEAT_S, LOSS_NAME, student_view, review, review_md, ts)  # noqa: E402,F401
from condition_tools import INPUTS, NUMERIC, evaluate, load_table, load_targets, write_text  # noqa: E402,F401

BASIS = ('비교값은 지표_정의.md의 네 손실(비용 · 생산 · 품질 · 에너지)과 조건표 감점의 합계(만원, 작을수록 유리)로 후보를 견주는 계산이다. '
         '포털 성과 지표의 정책 점수(성과 득실 · 예측 여유 · 선례 · 납기 긴급도 · 품질 위험을 더한 점수)와 다른 값이며, 순위는 실행 승인이 아니다.')
GAP_TEXT = {'carry': '끊긴 구간을 잇는다 — 판정 요청 때 PLC 팬 설정이 100 %면 그 사이 100 % 운전이 이어졌다고 보고 마지막 기록에 경과를 더한다',
            'unknown': '끊긴 구간을 잇지 않는다 — 그 사이 연속 운전을 확인할 수 없으므로 값 없음으로 둔다'}
WARN_TEXT = {'compare': '경고가 붙은 후보도 비교 합계로 견주어 순위에 둔다', 'skip': '경고가 붙은 후보는 견주지 않고 경고 없는 후보끼리 순위를 낸다'}
BASE_POLICY = ('carry', 'compare')          # (--gap, --warned)

# ───────────── 정할 자리 갈래 답(결과/gap_rule.py · compare_rule.py의 함수 본문) — 정답 토글 · 완성본은 build_judgement_labs가 이 원문으로 파일을 만든다 ─────────────
GAP_CODE = {
    'carry': '''def fan_hours_when_gap(ctx):
    # 판정 요청 때 PLC가 정상 수신(품질 good, 하트비트 안)이고 팬 설정이 100 %면 그 사이 100 % 운전이 이어졌다고 본다
    # 근거: 자료/수집_설명.md 26줄(행 사이에도 센다 — 이어졌을 때 누적 분 + 지난 시간), PLC_상태_수신.csv 팬_설정_pct
    if ctx.plc_reason is None and ctx.plc_last is not None and float(ctx.plc_last['팬_설정_pct']) == 100.0:
        return (float(ctx.counter_last['팬100_연속_분']) + ctx.counter_age_min) / 60, None
    return None, 'PLC 팬 설정으로도 100 %를 확인하지 못함'
''',
    'unknown': '''def fan_hours_when_gap(ctx):
    # 정해진 주기 기록이 빠진 구간은 그 사이 연속 운전을 확인할 수 없다 — 0이나 앞 값으로 채우지 않는다(자료/작업기준.md 20줄)
    return None, '그 사이 연속 운전을 확인할 수 없음'
''',
}
WARN_CODE = {
    'compare': '''def choose_compared(kept):
    # 경고는 견줄 때 남겨 두는 사유다 — 경고가 붙은 유지 후보도 견준다(자료/HM-8_매뉴얼.md 71줄 「다른 조치와 비교한다」)
    return {}
''',
    'skip': '''def choose_compared(kept):
    # 경고가 붙은 유지 후보는 견주지 않는다 — 경보 해제에 실패할 수 있는 후보를 순위에서 뺀다
    return {c['sop']: '경고 ' + ', '.join(h['rule_id'] for h in c['warnings']) + ' — 경고가 붙은 후보는 견주지 않고 경고 없는 후보끼리 순위를 낸다'
            for c in kept if c['warnings']}
''',
}
CHOICE_BASIS = {   # 정한_것.csv의 근거 · 바뀌는 답(강사 문장)
    'gap': '자료/수집_설명.md:26; 자료/작업기준.md:20; 자료/팬_운전_카운터.csv 사건 마지막 기록 뒤 주기 기록 없음',
    'warn': '자료/HM-8_매뉴얼.md:71; 자료/작업기준.md:25; 자료/metrics/지표_정의.md 품질 손실',
    'basis': '자료/metrics/지표_정의.md:18-22; 자료/작업기준.md:31',
}


def decision_module(gap, warned):
    """갈래 답 두 함수를 담은 이름 공간."""
    ns = {}
    exec(GAP_CODE[gap] + '\n' + WARN_CODE[warned], ns)
    return type('DecisionPoints', (), {'fan_hours_when_gap': staticmethod(ns['fan_hours_when_gap']), 'choose_compared': staticmethod(ns['choose_compared'])})


def choice_rows(gap, warned):
    return [['빈 값의 뜻', GAP_TEXT[gap], CHOICE_BASIS['gap'], '사건 SOP-COOL-11 · 12의 팬 연속 시간과 감점 R2(값 없음이면 보류) · 사건 1위'],
            ['쓰는 사람에 따라 갈리는 답', WARN_TEXT[warned], CHOICE_BASIS['warn'], '경고 R3가 붙은 SOP-COOL-11이 순위에 드는지 · 1위가 바뀌는 경보'],
            ['비교 기준 문장', BASIS, CHOICE_BASIS['basis'], '결과의 comparison_basis']]


def choice_csv(gap, warned):
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(T.CHOICE_HEADER)
    w.writerows(choice_rows(gap, warned))
    return buf.getvalue()


def choices(gap, warned):
    return {r[0]: dict(zip(T.CHOICE_HEADER, r)) for r in choice_rows(gap, warned)}


def run(lab, table=None, policy=BASE_POLICY):
    lab = Path(lab)
    table = Path(table) if table else lab/'입력/조건표.csv'
    mod = decision_module(*policy)
    return T.run(lab, table, mod.fan_hours_when_gap, mod.choose_compared, choices(*policy), BASIS)


def main(argv=None):
    ap = argparse.ArgumentParser(description='조건표로 경보마다 후보를 판정하고 견준다(강사 갈래).')
    ap.add_argument('lab')
    ap.add_argument('out')
    ap.add_argument('--table')
    ap.add_argument('--sop')
    ap.add_argument('--gap', choices=sorted(GAP_TEXT), default=BASE_POLICY[0])
    ap.add_argument('--warned', choices=sorted(WARN_TEXT), default=BASE_POLICY[1])
    ap.add_argument('--review', action='store_true')
    a = ap.parse_args(argv)
    lab, out = Path(a.lab), Path(a.out)
    table = Path(a.table) if a.table else lab/'입력/조건표.csv'
    res = run(lab, table, (a.gap, a.warned))
    if a.review:
        sop = json.loads((Path(a.sop) if a.sop else lab/'입력/sop.json').read_text(encoding='utf-8-sig'))
        rv = review(res, sop, load_table(table))
        write_text(out/'조치검토결과.json', json.dumps(rv, ensure_ascii=False, indent=1) + '\n')
        write_text(out/'조치검토결과.md', review_md(rv))
        print(f'사례 {len(rv["events"])}건 → {out/"조치검토결과.json"} · {out/"조치검토결과.md"}')
    else:
        write_text(out/'result.json', json.dumps(student_view(res), ensure_ascii=False, indent=1) + '\n')
        print(f'사례 {len(res["events"])}건 → {out/"result.json"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
