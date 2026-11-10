"""판정·성과 비교를 조치 검토 결과로 완성하기 — 기능마다 결과 화면에 보일 표를 만든다(제공 — 고치지 않는다). 판단의 답은 이 파일에 없다."""
from pathlib import Path
import csv
import io
import subprocess
import sys

import json

HERE = Path(__file__).resolve().parents[2]
from app.utils.results import compare, counts, error, note, read_table, table  # noqa: E402
from app.utils import condition_tools as C  # noqa: E402

TITLE = '판정·성과 비교를 조치 검토 결과로 완성하기'


def guarded(fn):
    """제공 코드가 알린 멈춤(정할 지점 비어 있음 · 계약 어긋남)을 빨간 칸으로 — 파일 · 줄과 까닭 그대로."""
    def run(previous):
        try:
            return fn(previous)
        except (C.ContractError, *EXTRA_STOP) as e:
            return [error('멈춤', str(e))]
    return run


EXPECT_COLUMNS = ['사례', '후보', '기대_판정', '근거']


def expected_rows():
    """app/features/expected.csv → 표 줄. 꼴이 계약과 다르면 파일:줄을 대고 멈춘다(맞지 않는 줄을 「실제 없음」으로 조용히 두지 않음)."""
    p = HERE/'app/features/expected.csv'
    if not p.is_file():
        return []
    body, skip = C.csv_body(p)
    reader = csv.DictReader(io.StringIO(body, newline=''))
    if reader.fieldnames != EXPECT_COLUMNS:
        raise C.ContractError(f'app/features/expected.csv:{skip + 1} 열 이름이 {",".join(EXPECT_COLUMNS)}가 아님')
    cases, sops = case_ids(), [r['sop_id'] for r in C.read_csv(HERE/'data/targets.csv')]
    out, seen = [], {}
    for line, r in enumerate(reader, start=skip + 2):
        where = f'app/features/expected.csv:{line}'
        if None in r or any(v is None for v in r.values()):
            raise C.ContractError(f'{where} 칸 수가 열 이름과 다릅니다 — 쉼표가 빠졌거나 더 있는지 봅니다(쉼표가 든 글은 큰따옴표로 감쌉니다).')
        if not any(v.strip() for v in r.values()):
            continue
        c, s, v = r['사례'].strip(), r['후보'].strip(), r['기대_판정'].strip()
        if c not in cases:
            raise C.ContractError(f'{where} 사례 「{c}」 — 사례 칸은 {CASE_FROM}')
        if s not in sops:
            raise C.ContractError(f'{where} 후보 「{s}」 — 후보 칸은 data/targets.csv의 SOP ID({" · ".join(sops)})')
        if v not in ('유지', '제외', '보류'):
            raise C.ContractError(f'{where} 기대_판정 「{v}」 — 유지 · 제외 · 보류 가운데 하나')
        if (c, s) in seen:
            raise C.ContractError(f'{where} {c} / {s} 줄이 {seen[(c, s)]}줄에도 있습니다 — 사례 · 후보마다 한 줄')
        seen[(c, s)] = line
        out.append({'사례 / 후보': f'{c} / {s}', '판정': v, '근거': r['근거'].strip()})
    return out


def against_expected(title, judged):
    """judged = {(사례, 후보): 판정} — expected.csv에 적은 줄만 견준다."""
    exp = expected_rows()
    keys = {e['사례 / 후보'] for e in exp}
    act = [{'사례 / 후보': f'{c} / {s}', '판정': v} for (c, s), v in judged.items() if f'{c} / {s}' in keys]
    return compare(title, '사례 / 후보', exp, act, ['판정'], '기대는 실행 전에 손으로 적은 값입니다. 다른 줄은 기대 · 조건표 · 원문 가운데 어느 쪽이 원문과 다른지 찾아 고칩니다.')


def run_check(previous):
    p = subprocess.run([sys.executable, '-m', 'app.utils.check'], cwd=HERE, capture_output=True, text=True, encoding='utf-8')
    lines = [[x] for x in (p.stdout + p.stderr).splitlines()]
    return [note('구조 검사 통과' if p.returncode == 0 else '구조 확인 필요 — 아래 줄마다 결과 파일의 어느 항목인지 찾아 고친 뒤 다시 실행합니다(아직 채우지 않은 파일이 있으면 그 파일이 짚힙니다).'),
            table('python run.py check 출력', ['줄'], lines)]



def expected_view(previous):
    exp = expected_rows()
    return [table('기대 판정(실행 전에 적은 값)과 근거 줄', ['사례 / 후보', '판정', '근거'], exp)]

from app.utils import judge_tools as T  # noqa: E402
EXTRA_STOP = (T.Unfilled,)
CASE_FROM = 'data/alarms.csv의 RAISE 행 경보_ID'


def case_ids():
    return {r['경보_ID'] for r in C.read_csv(HERE/'data/alarms.csv') if r['구분'] == 'RAISE'}


def num(x):
    """화면 표시용 수 — 원천 값은 소수 한두 자리라 계산 값(16.717499999999998)도 소수 둘째 자리로 둥글린다. 판정 · 결과 파일은 원값 그대로."""
    return round(x, 2) if isinstance(x, float) else x


REVIEW = True


def overview(previous):
    return [table('경보마다 판정 요청 직전 원천 기록(사실만 — 판정 없음)', ['경보', '설비', '판정 요청(UTC)', 'PLC 마지막 수신', '카운터 마지막 기록', '예측 행'], T.source_facts(HERE))]


def judged_all(events, groups):
    return {(e['id'], c['sop']): C.evaluate(c['sop'], c['inputs'], groups) for e in events for c in e['candidates']}


def inputs_view(previous):
    gap = T.load_function(HERE, T.GAP_FILE, 'fan_hours_when_gap')
    events, _ = T.prepare(HERE, gap)
    groups = C.load_table(T.pick(HERE, 'condition_table.csv'))
    rows = []
    for e in events:
        if not e['counter_gap']:
            continue
        c = e['candidates'][0]
        rows.append([e['id'], e['asset'], num(c['inputs']['fan100_hours']) if c['inputs']['fan100_hours'] is not None else '값 없음', c['missing_reasons'].get('fan100_hours', '')])
    j = judged_all(events, groups)
    st = [v['status'] for v in j.values()]
    return [table('카운터 기록이 끊긴 경보 — 내 함수가 낸 팬 100 % 연속 시간(h)', ['경보', '설비', '팬 100 % 연속 시간(h)', '값이 없는 까닭'], rows),
            counts('판정(경보 × 후보)', [('유지', st.count('유지')), ('제외', st.count('제외')), ('보류', st.count('보류'))]),
            against_expected('기대 판정 ↔ 판정', {k: v['status'] for k, v in j.items()})]


def compare_view(previous):
    gap = T.load_function(HERE, T.GAP_FILE, 'fan_hours_when_gap')
    cmp_ = T.load_function(HERE, T.COMPARE_FILE, 'choose_compared')
    choices = T.load_choices(HERE)
    res = T.run(HERE, T.pick(HERE, 'condition_table.csv'), gap, cmp_, choices, '')
    rows = [[e['id'], ', '.join(f"{r['rank']}위 {r['sop']} {r['total']:.2f}" for r in e['ranking']) or '순위 없음',
             '; '.join(f"{c['sop']}: {' · '.join(c['no_comparison_reason'])}" for c in e['candidates'] if c.get('no_comparison_reason'))] for e in res['events']]
    m = (HERE/'data/metrics/metric_definitions.md').read_text(encoding='utf-8')
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
            table(f'metric_definitions.md 손계산 예({cid} SOP-COOL-12) ↔ 제공 코드', ['손실', '문서', '프로그램'], hand)]


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
    res = T.run(HERE, T.pick(HERE, 'condition_table.csv'), gap, cmp_, T.load_choices(HERE), '')
    groups = C.load_table(T.pick(HERE, 'condition_table.csv'))
    thresholds = sorted({(r['input'], float(r['value'])) for r in C.read_csv(T.pick(HERE, 'condition_table.csv')) if r['input'] in C.NUMERIC})
    near = []
    for name, v in thresholds:
        vals = sorted({c['inputs'][name] for e in res['events'] for c in e['candidates'] if c['inputs'][name] is not None})
        below = [x for x in vals if x < v][-1:]
        above = [x for x in vals if x > v][:1]
        for x in [*below, *([v] if v in vals else []), *above]:
            hits = [f"{e['id']} {c['sop']}" for e in res['events'] for c in e['candidates'] if c['inputs'][name] == x]
            near.append([LABEL.get(name, name), num(v), num(x), ', '.join(hits[:6]) + (' …' if len(hits) > 6 else '')])
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
    if REVIEW and (HERE/'output/action_review.md').is_file():
        md = (HERE/'output/action_review.md').read_text(encoding='utf-8')
        first = INCIDENT
        if first and f'## {first}' in md:
            part = f'## {first}' + md.split(f'## {first}', 1)[1].split('\n## ', 1)[0]
            out.append(table(f'action_review.md — {first} 절', ['줄'], [[x] for x in part.splitlines() if x.strip()]))
    return out


def compare_and_write(previous):
    return compare_view(previous) + written(previous)



def short(j):
    # 판정 한 칸 — 「제외(R1 · 미확인 R4)」 · 「유지(경고 R3 · 감점 R2)」. 판정과 같은 이름의 사유 낱말은 되풀이하지 않는다.
    parts = [('' if k == j['status'] else k + ' ') + ','.join(h['rule_id'] for h in j[key]) for k, key in (('경고', 'warnings'), ('감점', 'penalties'), ('제외', 'exclusions')) if j[key]]
    if j['unknown']:
        parts.append('미확인 ' + ','.join(u['rule_id'] for u in j['unknown']))
    return j['status'] + ('(' + ' · '.join(parts) + ')' if parts else '')

INCIDENT = 'ALT-hyd02-0172-54a5'
LABEL = {'forecast_ts1': '조치 후 예측 유온(℃)', 'forecast_ps1': '조치 후 예측 토출 압력(bar)', 'fan100_hours': '팬 100 % 연속 시간(h)'}


def keep_previous(fn):
    """개수 칸 옆에 직전 실행(output/result.json)의 같은 이름 값을 붙인다 — 결정을 바꾼 뒤 무엇이 바뀌었는지 본다."""
    def run(previous):
        blocks = fn(previous)
        p = HERE/'output/result.json'
        try:
            before = json.loads(p.read_text(encoding='utf-8')).get('blocks', []) if p.is_file() else []
        except ValueError:
            before = []
        old = {(b.get('title'), k): v for b in before if b.get('kind') == 'counts' for k, v in b.get('items', [])}
        for b in blocks:
            if b['kind'] == 'counts':
                b['items'] = [(k, v if (b['title'], k) not in old or str(old[(b['title'], k)]).split(' ')[0] == str(v) else f"{v} (직전 실행 {str(old[(b['title'], k)]).split(' ')[0]})")
                              for k, v in b['items']]
        return blocks
    return run


COMMANDS = {
    'sources': ('판정 요청 직전 원천 기록', guarded(keep_previous(overview))),
    'expected': ('기대 판정', guarded(keep_previous(expected_view))),
    'inputs': ('끊긴 카운터 기록과 판정', guarded(keep_previous(inputs_view))),
    'compare': ('견줄 후보 · 순위와 조치 검토 결과', guarded(keep_previous(compare_and_write))),
    'cases': ('검토 결과와 사례 대조', guarded(keep_previous(cases_view))),
    'check': ('구조 검사', guarded(keep_previous(run_check))),
}
