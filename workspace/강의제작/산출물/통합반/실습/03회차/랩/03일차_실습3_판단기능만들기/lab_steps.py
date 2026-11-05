"""설비 조건별 최적의 조치를 비교하는 판단 기능 만들기 — 결과 화면의 단계(제공 — 고치지 않는다). python show_result.py가 이 파일의 STEPS를 차례로 돌린다.
단계마다 정할 자리(slots)가 채워졌으면 제공 코드를 돌려 그 단계의 결과를 표 · 대조 · 개수로 돌려준다. 판단의 답은 이 파일에 없다.
"""
from pathlib import Path
import csv
import io
import subprocess
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from show_result import compare, counts, error, note, read_table, table  # noqa: E402
import condition_tools as C  # noqa: E402

TITLE = '설비 조건별 최적의 조치를 비교하는 판단 기능 만들기'
NAMES = ['폴더와 출발점 확인 · 결과 화면 열기', '파일을 바꾸지 않고 자료 파악', '기대 판정 먼저 적기', '계획 검토', '빈 값의 뜻 — 끊긴 카운터 기록', '쓰는 사람에 따라 갈리는 답 — 견줄 후보', '비교 기준 문장과 결과 쓰기', '사례 대조', '검사 · 저장하고 다시 열기']


def guarded(fn):
    """제공 코드가 알린 멈춤(정할 자리 비어 있음 · 계약 어긋남)을 빨간 칸으로 — 파일 · 줄과 까닭 그대로."""
    def run(previous):
        try:
            return fn(previous)
        except (C.ContractError, *EXTRA_STOP) as e:
            return [error('멈춤', str(e))]
    return run


EXPECT_COLUMNS = ['사례', '후보', '기대_판정', '근거']


def expected_rows():
    """결과/기대_판정.csv → 표 줄. 꼴이 계약과 다르면 파일:줄을 대고 멈춘다(맞지 않는 줄을 「실제 없음」으로 조용히 두지 않음)."""
    p = HERE/'결과/기대_판정.csv'
    if not p.is_file():
        return []
    body, skip = C.csv_body(p)
    reader = csv.DictReader(io.StringIO(body, newline=''))
    if reader.fieldnames != EXPECT_COLUMNS:
        raise C.ContractError(f'결과/기대_판정.csv:{skip + 1} 열 이름이 {",".join(EXPECT_COLUMNS)}가 아님')
    cases, sops = case_ids(), [r['sop_id'] for r in C.read_csv(HERE/'자료/targets.csv')]
    out, seen = [], {}
    for line, r in enumerate(reader, start=skip + 2):
        where = f'결과/기대_판정.csv:{line}'
        if None in r or any(v is None for v in r.values()):
            raise C.ContractError(f'{where} 칸 수가 열 이름과 다릅니다 — 쉼표가 빠졌거나 더 있는지 봅니다(쉼표가 든 글은 큰따옴표로 감쌉니다).')
        if not any(v.strip() for v in r.values()):
            continue
        c, s, v = r['사례'].strip(), r['후보'].strip(), r['기대_판정'].strip()
        if c not in cases:
            raise C.ContractError(f'{where} 사례 「{c}」 — 사례 칸은 {CASE_FROM}')
        if s not in sops:
            raise C.ContractError(f'{where} 후보 「{s}」 — 후보 칸은 자료/targets.csv의 SOP ID({" · ".join(sops)})')
        if v not in ('유지', '제외', '보류'):
            raise C.ContractError(f'{where} 기대_판정 「{v}」 — 유지 · 제외 · 보류 가운데 하나')
        if (c, s) in seen:
            raise C.ContractError(f'{where} {c} / {s} 줄이 {seen[(c, s)]}줄에도 있습니다 — 사례 · 후보마다 한 줄')
        seen[(c, s)] = line
        out.append({'사례 / 후보': f'{c} / {s}', '판정': v, '근거': r['근거'].strip()})
    return out


def against_expected(title, judged):
    """judged = {(사례, 후보): 판정} — 기대_판정.csv에 적은 줄만 견준다."""
    exp = expected_rows()
    keys = {e['사례 / 후보'] for e in exp}
    act = [{'사례 / 후보': f'{c} / {s}', '판정': v} for (c, s), v in judged.items() if f'{c} / {s}' in keys]
    return compare(title, '사례 / 후보', exp, act, ['판정'], '기대는 실행 전에 손으로 적은 값입니다. 다른 줄은 기대 · 조건표 · 원문 가운데 어느 쪽이 원문과 다른지 찾아 고칩니다.')


def run_check(previous):
    p = subprocess.run([sys.executable, 'check.py'], cwd=HERE, capture_output=True, text=True, encoding='utf-8')
    lines = [[x] for x in (p.stdout + p.stderr).splitlines()]
    return [note('구조 검사 통과' if p.returncode == 0 else '구조 확인 필요 — 아래 줄마다 결과 파일의 어느 항목인지 찾아 고친 뒤 다시 실행합니다(앞 단계를 아직 채우는 중이면 그 단계의 자리가 짚힙니다).'),
            table('python check.py 출력', ['줄'], lines)]


def step(no, slots=(), run=None):
    return dict(no=no, name=NAMES[no - 1], slots=list(slots), run=guarded(run) if run else None)


def expected_view(previous):
    exp = expected_rows()
    return [table('기대 판정(실행 전에 적은 값)과 근거 줄', ['사례 / 후보', '판정', '근거'], exp)]

import judge_tools as T  # noqa: E402
EXTRA_STOP = (T.Unfilled,)
CASE_FROM = '자료/경보_목록.csv의 RAISE 행 경보_ID'


def case_ids():
    return {r['경보_ID'] for r in C.read_csv(HERE/'자료/경보_목록.csv') if r['구분'] == 'RAISE'}


def num(x):
    """화면 표시용 수 — 원천 값은 소수 한두 자리라 계산 값(16.717499999999998)도 소수 둘째 자리로 둥글린다. 판정 · 결과 파일은 원값 그대로."""
    return round(x, 2) if isinstance(x, float) else x


REVIEW = False


def overview(previous):
    return [table('경보마다 판정 요청 직전 원천 기록(사실만 — 판정 없음)', ['경보', '설비', '판정 요청(UTC)', 'PLC 마지막 수신', '카운터 마지막 기록', '예측 행'], T.source_facts(HERE))]


def judged_all(events, groups):
    return {(e['id'], c['sop']): C.evaluate(c['sop'], c['inputs'], groups) for e in events for c in e['candidates']}


def inputs_view(previous):
    gap = T.load_function(HERE, T.GAP_FILE, 'fan_hours_when_gap')
    events, _ = T.prepare(HERE, gap)
    groups = C.load_table(T.pick(HERE, '조건표.csv'))
    rows = []
    for e in events:
        if not e['counter_gap']:
            continue
        c = e['candidates'][0]
        rows.append([e['id'], e['asset'], num(c['inputs']['fan100_hours']) if c['inputs']['fan100_hours'] is not None else '값 없음', c['missing_reasons'].get('fan100_hours', '')])
    j = judged_all(events, groups)
    st = [v['status'] for v in j.values()]
    return [table('카운터 기록이 끊긴 경보 — 내 함수가 낸 팬 100 % 연속 시간(h)', ['경보', '설비', 'fan100_hours', '값이 없는 까닭'], rows),
            counts('판정(경보 × 후보)', [('유지', st.count('유지')), ('제외', st.count('제외')), ('보류', st.count('보류'))]),
            against_expected('기대 판정 ↔ 판정', {k: v['status'] for k, v in j.items()})]


def compare_view(previous):
    gap = T.load_function(HERE, T.GAP_FILE, 'fan_hours_when_gap')
    cmp_ = T.load_function(HERE, T.COMPARE_FILE, 'choose_compared')
    choices = T.load_choices(HERE)
    res = T.run(HERE, T.pick(HERE, '조건표.csv'), gap, cmp_, choices, '')
    rows = [[e['id'], ', '.join(f"{r['rank']}위 {r['sop']} {r['total']:.2f}" for r in e['ranking']) or '순위 없음',
             '; '.join(f"{c['sop']}: {' · '.join(c['no_comparison_reason'])}" for c in e['candidates'] if c.get('no_comparison_reason'))] for e in res['events']]
    m = (HERE/'자료/metrics/지표_정의.md').read_text(encoding='utf-8')
    import re
    cid = re.search(r'사례 (\S+)의 SOP-COOL-12', m).group(1)
    ex = next(c for e in res['events'] if e['id'] == cid for c in e['candidates'] if c['sop'] == 'SOP-COOL-12')
    hand = [[k, v, (ex['comparison'] or {}).get({'비용': 'cost', '생산': 'production', '품질': 'quality', '에너지': 'energy'}[k], '비교값 없음')]
            for k, v in re.findall(r'^\| (비용|생산|품질|에너지) \| .* \| ([0-9.]+) \|$', m, re.M)]
    ranked = sum(1 for e in res['events'] if e['ranking'])
    mine = sum(len(T.call_compare(cmp_, [c for c in e['candidates'] if c['status'] == '유지'])) for e in res['events'])
    skipped = sum(1 for e in res['events'] for c in e['candidates'] if c.get('no_comparison_reason'))
    return [counts('순위', [('순위가 있는 경보', ranked), ('내 함수(compare_rule)가 뺀 유지 후보', mine),
                           ('비교값이 없어 견주지 못한 유지 후보(까닭은 아래 표)', skipped - mine)]),
            table('경보마다 순위와 견주지 않은 후보', ['경보', '순위(합계, 만원)', '견주지 않은 유지 후보와 까닭'], rows),
            table(f'지표_정의.md 손계산 예({cid} SOP-COOL-12) ↔ 제공 코드', ['손실', '문서', '프로그램'], hand)]


def written(previous):
    try:
        res, files = T.run_folder(HERE, review_mode=REVIEW)
    except T.Unfilled as e:
        return [note(f'아직 결과 파일을 쓰지 않았습니다 — {e}')]
    exp_ids = {r['사례 / 후보'].split(' / ')[0] for r in expected_rows()}
    sel = [[e['id'], e['selection']['reason'], ' / '.join(e['selection']['checks']) or '—'] for e in res['events'] if e['id'] in exp_ids]
    return [note('쓴 파일: ' + ', '.join(files) + '\ncomparison_basis: ' + res['comparison_basis']),
            table('기대를 적은 경보의 선택 이유와 추가로 확인할 사항', ['경보', '선택 이유', '추가로 확인할 사항'], sel)]


def cases_view(previous):
    gap = T.load_function(HERE, T.GAP_FILE, 'fan_hours_when_gap')
    cmp_ = T.load_function(HERE, T.COMPARE_FILE, 'choose_compared')
    res = T.run(HERE, T.pick(HERE, '조건표.csv'), gap, cmp_, T.load_choices(HERE), '')
    groups = C.load_table(T.pick(HERE, '조건표.csv'))
    thresholds = sorted({(r['input'], float(r['value'])) for r in C.read_csv(T.pick(HERE, '조건표.csv')) if r['input'] in C.NUMERIC})
    near = []
    for name, v in thresholds:
        vals = sorted({c['inputs'][name] for e in res['events'] for c in e['candidates'] if c['inputs'][name] is not None})
        below = [x for x in vals if x < v][-1:]
        above = [x for x in vals if x > v][:1]
        for x in [*below, *([v] if v in vals else []), *above]:
            hits = [f"{e['id']} {c['sop']}" for e in res['events'] for c in e['candidates'] if c['inputs'][name] == x]
            near.append([name, num(v), num(x), ', '.join(hits[:6]) + (' …' if len(hits) > 6 else '')])
    allx = [e['id'] for e in res['events'] if all(c['status'] == '제외' for c in e['candidates'])]
    ids = lambda hs: ' · '.join(h['rule_id'] for h in hs) or '—'
    per = [[e['id'], c['sop'], c['status'], ids(c['warnings']), ids(c['penalties']), ids(c['exclusions']), ids(c['unknown']),
            ' · '.join(f"{m}({c['missing_reasons'].get(m, '')})" for m in sorted({m for u in c['unknown'] for m in u['missing']})) or '—']
           for e in res['events'] for c in e['candidates']]
    out = [table('후보마다 판정 내용 — 사례 종류를 고를 때 거르기 칸에 경보 ID · 규칙 ID · 판정 낱말을 넣습니다',
                 ['경보', '후보', '판정', '경고', '감점', '제외', '미확인', '빠진 입력(까닭)'], per),
           table('조건표 기준값마다 같은 값 · 바로 아래 · 바로 위의 후보(사실)', ['입력', '기준값', '값', '경보 · 후보'], near),
           note('모든 후보가 제외된 경보: ' + (', '.join(allx) or '없음')),
           against_expected('기대 판정 ↔ 판정', {(e['id'], c['sop']): c['status'] for e in res['events'] for c in e['candidates']})]
    if REVIEW and (HERE/'결과/조치검토결과.md').is_file():
        md = (HERE/'결과/조치검토결과.md').read_text(encoding='utf-8')
        first = next(iter(sorted({r['사례 / 후보'].split(' / ')[0] for r in expected_rows()})), None)
        if first and f'## {first}' in md:
            part = md.split(f'## {first}', 1)[1].split('\n## ', 1)[0]
            out.append(table(f'조치검토결과.md — {first} 절', ['줄'], [[x] for x in part.splitlines() if x.strip()]))
    return out


STEPS = [step(1, run=overview), step(2), step(3, ['결과/기대_판정.csv'], expected_view), step(4),
         step(5, ['결과/gap_rule.py'], inputs_view), step(6, ['결과/compare_rule.py'], compare_view), step(7, run=written),
         step(8, run=cases_view), step(9, run=run_check)]
