"""작업 절차와 판단 조건을 연결해 조치 기준 만들기 — 결과 화면의 단계(제공 — 고치지 않는다). python show_result.py가 이 파일의 STEPS를 차례로 돌린다.
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

TITLE = '작업 절차와 판단 조건을 연결해 조치 기준 만들기'
NAMES = ['폴더와 출발점 확인 · 결과 화면 열기', '파일을 바꾸지 않고 자료 파악', '요구와 기대 판정 정하기', '계획 검토', '조건 문장 나누기 — SOP 구조', '고장 유형 · 원인 · 조치 잇기', '적용 범위와 설비 모델 ID 잇기', '조건표 규칙 — 복합 조건과 경계', '출처가 확인되지 않는 규칙', '검사 · 저장하고 다시 열기']


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

import sop_tools as S  # noqa: E402
EXTRA_STOP = (S.Unfilled,)
CANDIDATES = ['SOP-COOL-11', 'SOP-COOL-12', 'SOP-COOL-13', 'SOP-COOL-14']


def overview(previous):
    sents = C.sentences(HERE)
    return [counts('받은 자료', [('매뉴얼 원문 문장', len(sents)), ('판단 시스템 결정표 규칙', len(C.export_rules(HERE/'자료/판단시스템_결정표_내보내기.txt'))),
                                ('확인 사례', len(C.case_inputs(HERE/'자료/확인_사례.csv', {}))), ('냉각 계통 SOP', len(C.read_csv(HERE/'자료/targets.csv')))]),
            table('매뉴얼 원문 문장 — 판단 표의 「원문」 칸에 쓰는 번호', ['원문', '절', 'SOP', '단계', '글'], sents)]


def facts(previous):
    return [table('판단 시스템 결정표 규칙 — 출처 칸의 절이 받은 원문에 있는가(사실만)', ['줄', 'id', '조건식', '결과', '대상', '출처', '출처_절'], C.export_facts(HERE))]


def built():
    doc, todo, missing = S.build(HERE)
    return doc, todo, missing


def classify(previous):
    doc, todo, _ = built()
    rows = []
    for s in doc['sops']:
        for key, name in (('apply_conditions', '적용'), ('prohibitions', '금지 · 제한'), ('completion', '완료')):
            for it in s[key]:
                rows.append([s['id'], it.get('type', name), it['text'], it['source'], ' · '.join(it['rules'])])
        rows.append([s['id'], '승인', s['approval']['role'], s['approval']['source'], ''])
        rows.append([s['id'], '종류 · 코드', f"{s['kind']} {' · '.join(s['codes'])}" if s['kind'] else '없음', '', ''])
    out = [counts('SOP 구조', [('SOP', len(doc['sops'])), ('적용 조건', sum(len(s['apply_conditions']) for s in doc['sops'])),
                              ('금지 · 제한', sum(len(s['prohibitions']) for s in doc['sops'])), ('완료 기준', sum(len(s['completion']) for s in doc['sops'])),
                              ('승인 미확인', sum(1 for s in doc['sops'] if s['approval']['role'].startswith('미확인')))]),
           table('결과/sop.json — 칸마다 원문 인용과 출처', ['SOP', '칸', '글(원문 인용)', '출처', '규칙'], rows)]
    left = [t for t in todo if '관계' not in t and '설비_연결' not in t]
    return out + ([error('아직 채우지 않은 곳', '\n'.join(left))] if left else [])


def relations(previous):
    doc, todo, _ = built()
    rel_errors = [t for t in todo if t.startswith('관계.csv')]
    out = [table('관계 — 고장 유형 · 조치 · 원인', ['type', 'from', 'to', '출처'], [[r['type'], r['from'], r['to'], r['source']] for r in doc['relations']]),
           table('원인', ['id', '이름', '출처'], [[c['id'], c['name'], c['source']] for c in doc['causes']])]
    ends = {f['id'] for f in doc['failure_modes']} | {c['id'] for c in doc['causes']} | {s['id'] for s in doc['sops']}
    bad = [f"{r['type']} {r['from']} → {r['to']}" for r in doc['relations'] if r['from'] not in ends or r['to'] not in ends]
    return out + ([error('양 끝이 sop.json에 없는 관계', '\n'.join(bad))] if bad else []) + ([error('관계.csv를 읽지 못한 줄', '\n'.join(rel_errors))] if rel_errors else [])


def models(previous):
    doc, todo, missing = built()
    assets = sorted({a for s in doc['sops'] for a in s['model_refs']['assets']})
    rows = [[s['id'], ' · '.join(s['model_refs']['assets']), ' · '.join(s['model_refs']['components']), ' · '.join(s['model_refs']['sensors']), s['model_refs']['not_linked']] for s in doc['sops']]
    per = [[a, ' · '.join(s['id'] for s in doc['sops'] if a in s['model_refs']['assets'])] for a in assets]
    out = [table('SOP마다 모델 참조', ['SOP', '설비', '구성 요소', '센서', '걸지 않은 대상과 까닭'], rows), table('설비마다 걸린 SOP', ['설비', 'SOP'], per)]
    return out + ([error('모델에서 찾지 못한 ID(걸지 않음)', '\n'.join(missing))] if missing else [])


def kinds(doc):
    by = {s['id']: s for s in doc['sops']}
    return {c: (by[c]['kind'], by[c]['codes']) if c in by else (None, []) for c in CANDIDATES}


def judged_cases(doc):
    groups = C.load_table(HERE/'결과/조건표.csv')
    k = kinds(doc)
    memo = C.memo_inputs((HERE/'자료/사건_기록_HYD-02_1027.md').read_text(encoding='utf-8'), k)
    cases = C.case_inputs(HERE/'자료/확인_사례.csv', k)
    incident = next(cid for cid in cases if cid in (HERE/'자료/사건_기록_HYD-02_1027.md').read_text(encoding='utf-8'))
    out = {(incident, s): C.evaluate(s, x, groups) for s, x in memo.items()}
    out.update({(cid, s): C.evaluate(s, x, groups) for cid, cs in cases.items() if cid != incident for s, x in cs.items()})
    return out, incident


def rules(previous):
    doc, _, _ = built()
    j, incident = judged_cases(doc)                     # 조건표 꼴 검사(파일:줄)가 출처 대조보다 먼저
    trace, miss = S.trace(HERE)
    rows = [r for r in trace if r['항목'].startswith('조건표')]
    inc = [[s, C.short(v)] for (c, s), v in j.items() if c == incident]
    return [table('조건표 규칙 — 출처 칸의 원문', ['항목', '내용', '출처 조각', '원문 줄', '원문'], rows),
            table('사건 네 후보(사건 메모의 값을 조건표에 댄 결과)', ['후보', '판정'], inc),
            against_expected('기대 판정 ↔ 조건표를 댄 판정', {k: v['status'] for k, v in j.items()})]


def sources(previous):
    doc, _, _ = built()
    j, _ = judged_cases(doc)
    mine = {x for r in C.read_csv(HERE/'결과/조건표.csv') for x in C.RULE_REF.findall(r['source_section'])}
    fx = [dict(r, 내_조건표='출처로 듦' if r['id'] in mine else '—') for r in C.export_facts(HERE)]
    trace, miss = S.trace(HERE)
    st = [v['status'] for v in j.values()]
    return [counts('확인 사례 판정(사건 포함, 후보마다)', [('유지', st.count('유지')), ('제외', st.count('제외')), ('보류', st.count('보류'))],
                   '직전 실행과 견줘 바뀐 개수가 이번 결정으로 바뀐 판정입니다.'),
            table('사례 · 후보마다 판정', ['사례', '후보', '판정'], [[c, s, C.short(v)] for (c, s), v in j.items()]),
            table('판단 시스템 결정표 규칙과 내 조건표', ['줄', 'id', '결과', '대상', '출처', '출처_절', '내_조건표'], fx),
            against_expected('기대 판정 ↔ 조건표를 댄 판정', {k: v['status'] for k, v in j.items()}),
            table('출처 대조 — 원문에서 찾지 못한 출처 조각', ['조각'], [[m] for m in miss])]


STEPS = [step(1, run=overview), step(2, run=facts), step(3, ['결과/기대_판정.csv'], expected_view), step(4),
         step(5, ['결과/조건_분류.csv'], classify), step(6, ['결과/관계.csv'], relations), step(7, ['결과/설비_연결_기준.csv'], models),
         step(8, ['결과/조건표.csv'], rules), step(9, run=sources), step(10, run=run_check)]
