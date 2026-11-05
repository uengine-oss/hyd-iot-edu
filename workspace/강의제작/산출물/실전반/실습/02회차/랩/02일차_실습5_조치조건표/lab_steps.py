"""작업 기준의 복합 조건과 예외를 조치 조건표로 표현하기 — 결과 화면의 단계(제공 — 고치지 않는다). python show_result.py가 이 파일의 STEPS를 차례로 돌린다.
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

TITLE = '작업 기준의 복합 조건과 예외를 조치 조건표로 표현하기'
NAMES = ['폴더와 출발점 확인 · 결과 화면 열기', '파일을 바꾸지 않고 자료 파악', '요구와 기대 판정 정하기', '계획 검토', '조건표 규칙 — 복합 조건과 경계', '출처가 확인되지 않는 규칙', '남은 후보와 실행 승인', '검사 · 저장하고 다시 열기']


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

CASE_FROM = '자료/확인_사례.csv의 사례 ID(사건 메모의 경보도 그 ID)'


def case_ids():
    return {r['사례'] for r in C.read_csv(HERE/'자료/확인_사례.csv')}

EXTRA_STOP = ()


def targets():
    return {r['sop_id']: (r['kind'], [x for x in r['codes'].split(';') if x]) for r in C.read_csv(HERE/'자료/targets.csv')}


def overview(previous):
    return [counts('받은 자료', [('매뉴얼 원문 문장', len(C.sentences(HERE))), ('판단 시스템 결정표 규칙', len(C.export_rules(HERE/'자료/판단시스템_결정표_내보내기.txt'))),
                                ('확인 사례', len(C.case_inputs(HERE/'자료/확인_사례.csv', {}))), ('후보', len(targets()))]),
            table('매뉴얼 원문 문장', ['원문', '절', 'SOP', '단계', '글'], C.sentences(HERE))]


def facts(previous):
    return [table('판단 시스템 결정표 규칙 — 출처 칸의 절이 받은 원문에 있는가(사실만)', ['줄', 'id', '조건식', '결과', '대상', '출처', '출처_절'], C.export_facts(HERE))]


def judged():
    groups = C.load_table(HERE/'결과/조건표.csv')
    t = targets()
    memo_text = (HERE/'자료/사건_기록_HYD-02_1027.md').read_text(encoding='utf-8')
    cases = C.case_inputs(HERE/'자료/확인_사례.csv', t)
    incident = next(cid for cid in cases if cid in memo_text)
    out = {(incident, s): C.evaluate(s, x, groups) for s, x in C.memo_inputs(memo_text, t).items()}
    out.update({(cid, s): C.evaluate(s, x, groups) for cid, cs in cases.items() if cid != incident for s, x in cs.items()})
    return out


def rules(previous):
    j = judged()                                        # 조건표 꼴 검사(파일:줄)가 출처 표보다 먼저
    seen, rows = set(), []
    for r in C.read_csv(HERE/'결과/조건표.csv'):
        if (r['rule_id'], r['action']) in seen:
            continue
        seen.add((r['rule_id'], r['action']))
        for part, no, text in C.source_parts(HERE, r['source_section']):
            rows.append([r['rule_id'], r['action'], r['result'], part, no or '—', text])
    return [table('조건표 규칙 — 출처 칸의 원문', ['규칙', '후보', '결과', '출처 조각', '원문 줄', '원문'], rows),
            table('사건 · 확인 사례 — 후보마다 맞은 규칙과 알 수 없는 규칙', ['사례', '후보', '판정'], [[c, s, C.short(v)] for (c, s), v in j.items()]),
            against_expected('기대 판정 ↔ 조건표를 댄 판정', {k: v['status'] for k, v in j.items()})]


def sources(previous):
    j = judged()
    mine = {x for r in C.read_csv(HERE/'결과/조건표.csv') for x in C.RULE_REF.findall(r['source_section'])}
    st = [v['status'] for v in j.values()]
    return [counts('사건 · 확인 사례 판정(후보마다)', [('유지', st.count('유지')), ('제외', st.count('제외')), ('보류', st.count('보류'))],
                   '직전 실행과 견줘 바뀐 개수가 이번 결정으로 바뀐 판정입니다.'),
            table('판단 시스템 결정표 규칙과 내 조건표', ['줄', 'id', '결과', '대상', '출처', '출처_절', '내_조건표'],
                  [dict(r, 내_조건표='출처로 듦' if r['id'] in mine else '—') for r in C.export_facts(HERE)]),
            table('사건 · 확인 사례 판정', ['사례', '후보', '판정'], [[c, s, C.short(v)] for (c, s), v in j.items()])]


APPROVAL_COLUMNS = ['sop_id', '승인_역할', '원문']


def approval_rows():
    """결과/승인.csv → {후보: 행}. 꼴이 계약과 다르면 파일:줄을 대고 멈춘다."""
    p = HERE/'결과/승인.csv'
    body, skip = C.csv_body(p)
    reader = csv.DictReader(io.StringIO(body, newline=''))
    if reader.fieldnames != APPROVAL_COLUMNS:
        raise C.ContractError(f'결과/승인.csv:{skip + 1} 열 이름이 {",".join(APPROVAL_COLUMNS)}가 아님')
    lines, sops, by = C.manual_lines(HERE), [r['sop_id'] for r in C.read_csv(HERE/'자료/targets.csv')], {}
    for line, r in enumerate(reader, start=skip + 2):
        where = f'결과/승인.csv:{line}'
        if None in r or any(v is None for v in r.values()):
            raise C.ContractError(f'{where} 칸 수가 열 이름과 다릅니다 — 쉼표가 빠졌거나 더 있는지 봅니다(쉼표가 든 글은 큰따옴표로 감쌉니다).')
        if not any(v.strip() for v in r.values()):
            continue
        s = r['sop_id'].strip()
        if s not in sops:
            raise C.ContractError(f'{where} sop_id 「{s}」 — 자료/targets.csv의 SOP ID({" · ".join(sops)})')
        if s in by:
            raise C.ContractError(f'{where} {s} 줄이 두 번째입니다 — 후보마다 한 줄')
        for n in [x.strip() for x in r['원문'].split(';') if x.strip()]:
            no = n.rsplit(':', 1)[-1]
            if not no.isdigit() or int(no) not in lines:
                raise C.ContractError(f'{where} 원문 「{n}」 — 자료/HM-8_매뉴얼.md의 줄 번호(68 또는 자료/HM-8_매뉴얼.md:68, 여러 개는 ;)')
        by[s] = r
    return by


def approvals(previous):
    lines = C.manual_lines(HERE)
    by = approval_rows()
    out = []
    for (c, s), v in judged().items():
        if v['status'] == '제외':
            continue
        r = by.get(s)
        nums = [int(n.strip().rsplit(':', 1)[-1]) for n in (r['원문'].split(';') if r else []) if n.strip().rsplit(':', 1)[-1].isdigit()]
        quote = ' / '.join(lines[n][3] for n in nums if n in lines)
        out.append([c, s + (' (보류: ' + ', '.join(m for u in v['unknown'] for m in u['missing']) + ' 빠짐)' if v['status'] == '보류' else ''),
                    r['승인_역할'] if r else '— 승인.csv에 없음', quote])
    return [table('남은 후보와 실행 승인 — 후보가 남은 것은 실행 허가가 아니다', ['사례', '남은 후보', '승인 역할', '원문 승인 줄'], out)]


STEPS = [step(1, run=overview), step(2, run=facts), step(3, ['결과/기대_판정.csv'], expected_view), step(4),
         step(5, ['결과/조건표.csv'], rules), step(6, run=sources), step(7, ['결과/승인.csv'], approvals), step(8, run=run_check)]
