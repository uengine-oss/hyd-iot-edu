"""작업 기준의 복합 조건과 예외를 조치 조건표로 표현하기 — 기능마다 결과 화면에 보일 표를 만든다(제공 — 고치지 않는다). 판단의 답은 이 파일에 없다."""
from pathlib import Path
import csv
import io
import subprocess
import sys

import json

HERE = Path(__file__).resolve().parents[2]
from app.utils.results import compare, counts, error, note, read_table, table  # noqa: E402
from app.utils import condition_tools as C  # noqa: E402

TITLE = '작업 기준의 복합 조건과 예외를 조치 조건표로 표현하기'


def guarded(fn):
    """제공 코드가 알린 멈춤(빈 틀 비어 있음 · 계약 어긋남)을 빨간 칸으로 — 파일 · 줄과 까닭 그대로."""
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

CASE_FROM = 'data/check_cases.csv의 사례 ID(사건 메모의 경보도 그 ID)'


def case_ids():
    return {r['사례'] for r in C.read_csv(HERE/'data/check_cases.csv')}

EXTRA_STOP = ()


def targets():
    return {r['sop_id']: (r['kind'], [x for x in r['codes'].split(';') if x]) for r in C.read_csv(HERE/'data/targets.csv')}


def overview(previous):
    return [counts('받은 자료', [('매뉴얼 원문 문장', len(C.sentences(HERE))), ('판단 시스템 결정표 규칙', len(C.export_rules(HERE/'data/decision_table_export.txt'))),
                                ('확인 사례', len(C.case_inputs(HERE/'data/check_cases.csv', {}))), ('후보', len(targets()))]),
            table('매뉴얼 원문 문장', ['원문', '절', 'SOP', '단계', '글'], C.sentences(HERE))]


def facts(previous):
    return [table('판단 시스템 결정표 규칙 — 출처 칸의 절이 HM-8 매뉴얼 원문에 있는가(사실만)', ['줄', 'id', '조건식', '결과', '대상', '출처', '출처_절'], C.export_facts(HERE))]


def judged():
    groups = C.load_table(HERE/'app/features/condition_table.csv')
    t = targets()
    memo_text = (HERE/'data/incident_hyd02_1027.md').read_text(encoding='utf-8')
    cases = C.case_inputs(HERE/'data/check_cases.csv', t)
    incident = next(cid for cid in cases if cid in memo_text)
    out = {(incident, s): C.evaluate(s, x, groups) for s, x in C.memo_inputs(memo_text, t).items()}
    out.update({(cid, s): C.evaluate(s, x, groups) for cid, cs in cases.items() if cid != incident for s, x in cs.items()})
    return out


def rules(previous):
    j = judged()                                        # 조건표 꼴 검사(파일:줄)가 출처 표보다 먼저
    seen, rows = set(), []
    for r in C.read_csv(HERE/'app/features/condition_table.csv'):
        if (r['rule_id'], r['action']) in seen:
            continue
        seen.add((r['rule_id'], r['action']))
        for part, no, text in C.source_parts(HERE, r['source_section']):
            rows.append([r['rule_id'], r['action'], r['result'], part, no or '—', text])
    return [table('조건표 규칙 — 출처 칸의 원문', ['규칙', '후보', '결과', '출처 조각', '원문 줄', '원문'], rows),
            table('사건 · 확인 사례 — 후보마다 맞은 규칙과 알 수 없는 규칙', ['사례', '후보', '판정'], [[c, s, short(v)] for (c, s), v in j.items()]),
            against_expected('기대 판정 ↔ 조건표를 댄 판정', {k: v['status'] for k, v in j.items()})]


def sources(previous):
    j = judged()
    mine = {x for r in C.read_csv(HERE/'app/features/condition_table.csv') for x in C.RULE_REF.findall(r['source_section'])}
    st = [v['status'] for v in j.values()]
    return [counts('사건 · 확인 사례 판정(후보마다)', [('유지', st.count('유지')), ('제외', st.count('제외')), ('보류', st.count('보류'))],
                   '직전 실행과 견줘 바뀐 개수가 이번 결정으로 바뀐 판정입니다.'),
            table('판단 시스템 결정표 규칙과 내 조건표', ['줄', 'id', '결과', '대상', '출처', '출처_절', '내_조건표'],
                  [dict(r, 내_조건표='출처로 듦' if r['id'] in mine else '—') for r in C.export_facts(HERE)]),
            table('사건 · 확인 사례 판정', ['사례', '후보', '판정'], [[c, s, short(v)] for (c, s), v in j.items()])]


APPROVAL_COLUMNS = ['sop_id', '승인_역할', '원문']


def approval_rows():
    """app/features/approvals.csv → {후보: 행}. 꼴이 계약과 다르면 파일:줄을 대고 멈춘다."""
    p = HERE/'app/features/approvals.csv'
    body, skip = C.csv_body(p)
    reader = csv.DictReader(io.StringIO(body, newline=''))
    if reader.fieldnames != APPROVAL_COLUMNS:
        raise C.ContractError(f'app/features/approvals.csv:{skip + 1} 열 이름이 {",".join(APPROVAL_COLUMNS)}가 아님')
    lines, sops, by = C.manual_lines(HERE), [r['sop_id'] for r in C.read_csv(HERE/'data/targets.csv')], {}
    for line, r in enumerate(reader, start=skip + 2):
        where = f'app/features/approvals.csv:{line}'
        if None in r or any(v is None for v in r.values()):
            raise C.ContractError(f'{where} 칸 수가 열 이름과 다릅니다 — 쉼표가 빠졌거나 더 있는지 봅니다(쉼표가 든 글은 큰따옴표로 감쌉니다).')
        if not any(v.strip() for v in r.values()):
            continue
        s = r['sop_id'].strip()
        if s not in sops:
            raise C.ContractError(f'{where} sop_id 「{s}」 — data/targets.csv의 SOP ID({" · ".join(sops)})')
        if s in by:
            raise C.ContractError(f'{where} {s} 줄이 두 번째입니다 — 후보마다 한 줄')
        for n in [x.strip() for x in r['원문'].split(';') if x.strip()]:
            no = n.rsplit(':', 1)[-1]
            if not no.isdigit() or int(no) not in lines:
                raise C.ContractError(f'{where} 원문 「{n}」 — data/hm8_manual.md의 줄 번호(68 또는 data/hm8_manual.md:68, 여러 개는 ;)')
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
                    r['승인_역할'] if r else '— approvals.csv에 없음', quote])
    return [table('남은 후보와 실행 승인 — 후보가 남은 것은 실행 허가가 아니다', ['사례', '남은 후보', '승인 역할', '원문 승인 줄'], out)]



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
    'sources': ('받은 자료', guarded(keep_previous(overview))),
    'export': ('판단 시스템 결정표 규칙', guarded(keep_previous(facts))),
    'expected': ('기대 판정', guarded(keep_previous(expected_view))),
    'rules': ('조건표 규칙과 사례 판정', guarded(keep_previous(rules))),
    'provenance': ('출처가 확인되지 않는 규칙', guarded(keep_previous(sources))),
    'approvals': ('남은 후보와 실행 승인', guarded(keep_previous(approvals))),
    'check': ('구조 검사', guarded(keep_previous(run_check))),
}
