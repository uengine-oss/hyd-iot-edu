"""설비·부품·공급 정보를 연결하는 온톨로지 설계하기 — 결과 화면의 단계(START.md 「진행 단계」와 같은 번호 · 이름). 제공 파일 — 바꾸지 않는다."""

from pathlib import Path
import re
import subprocess
import sys
import show_result as R

HERE = Path(__file__).resolve().parent


def norm(text):
    """답 글자 견주기: 「·」 · 쉼표 · 공백으로 나눈 조각을 정렬해 다시 잇는다(순서 · 띄어쓰기 차이는 같게 본다)."""
    return ' · '.join(sorted(x for x in re.split(r'[·,\s]+', str(text or '')) if x))


def expected_rows(columns, key):
    """기대 답 표의 행. key = 한 행을 가리키는 열들 — 같은 짝이 두 줄이면 결과 화면이 한 줄을 조용히 덮으므로 두 줄 번호를 대고 멈춘다."""
    path = HERE / '결과/기대_답.csv'
    rows = R.read_table(path)
    text, _ = R.read_text(path)
    lines = [i for i, x in enumerate(text.splitlines(), 1) if x.strip() and not x.lstrip().startswith('#')][1:]   # 데이터 행의 편집기 줄 번호
    seen = {}
    for line, r in zip(lines, rows):
        empty = [c for c in columns if not r.get(c)]
        if empty:
            raise R.Stop(f'결과/기대_답.csv:{line}: 빈 칸 ' + ', '.join(empty))
        k = tuple(r.get(c, '') for c in key)
        if k in seen:
            raise R.Stop(f'결과/기대_답.csv:{seen[k]} · {line}: 같은 ({" · ".join(key)}) 「{" · ".join(k)}」가 두 줄입니다 — 한 짝에 한 줄만 씁니다(여러 값은 한 칸에 「 · 」로).')
        seen[k] = line
    return rows


def run_check():
    p = subprocess.run([sys.executable, 'check.py'], cwd=HERE, capture_output=True, text=True, encoding='utf-8', errors='replace')
    text = (p.stdout + p.stderr).strip()
    return [R.note('python check.py\n' + text)] if p.returncode == 0 else [R.error('python check.py — 구조 확인 필요', text)]

import supply_tool as M

TITLE = '설비·부품·공급 정보를 연결하는 온톨로지 설계하기'
KEY = ['질문', '물을_값', '항목']   # 기대 답 한 줄을 가리키는 열


def guarded(fn, *a):
    try:
        return fn(*a)
    except M.Stop as e:
        raise R.Stop(str(e))


def sources(previous):
    _, graph = M.base_model()
    labels = {}
    for n in graph['nodes']:
        labels[n['labels'][0]] = labels.get(n['labels'][0], 0) + 1
    rows = [(p.name, len(R.read_table(p))) for p in sorted((HERE / '자료').glob('*.csv'))]
    return [R.counts('제공된 설비 · 부품 모델(입력/graph.json)', sorted(labels.items()) + [('관계', len(graph['rels']))]),
            R.table('원자료 파일과 행 수(머리줄 뺌)', ['파일', '행'], rows)]


def expected(previous):
    rows = expected_rows(['질문', '물을_값', '기대_답', '근거'], KEY)
    return [R.table('내가 원자료에서 먼저 적은 기대 답', ['질문', '물을_값', '항목', '기대_답', '근거'], rows)]


def quotes(previous):
    pairs, used, found = guarded(M.pairs, '견적')
    split = {}
    for v in used.values():
        split[v] = split.get(v, 0) + 1
    return [R.counts('견적 줄 — 씀 · 기준일에 안 씀', sorted(split.items()) + [('공급사 · 부품 쌍', len(pairs))]),
            R.table('공급사 · 부품 쌍마다 쓴 견적(단위를 맞춘 값과 원래 표기)', ['공급사', '사내 품번', '단가(만원)', '불량률', '불량률 원래', '납기(일)', '납기 원래', '견적일', '출처'],
                    [(p['supplier'], p['part'], p['price_manwon'], p['defect_rate'], p['defect_rate_original'] or '', p['lead_days'], p['lead_days_original'] or '', p['quote_date'], p['quote_source']) for p in pairs]),
            R.table('견적 줄마다 간 곳', ['자료/공급_조건.csv 행', '간 곳'], sorted(used.items())),
            R.table('품번 칸이 사내 품번이 아니어서 찾은 줄', ['행', '원래 글', '사내 품번', '찾은 법'], found)]


def approval(previous):
    pairs, used, found = guarded(M.pairs, '승인')
    extra = sorted({k for p in pairs for k in p} - {'supplier', 'part', 'price_manwon', 'defect_rate', 'defect_rate_original', 'lead_days', 'lead_days_original',
                                                     'min_order_qty', 'supplier_part_no', 'quote_date', 'valid_until', 'quote_source', 'as_of', 'approved', 'approval_source'})
    guarded(M.write_model, pairs)
    cols = ['공급사', '사내 품번', 'approved', '승인 출처'] + extra
    return [R.counts('승인(approved)', [('참', sum(p['approved'] for p in pairs)), ('거짓', sum(not p['approved'] for p in pairs))]),
            R.table('쌍마다 승인과 내가 남긴 속성', cols, [[p['supplier'], p['part'], p['approved'], p.get('approval_source') or ''] + [p.get(k, '') for k in extra] for p in pairs]),
            R.note('결과/schema.json · 결과/graph.json을 새로 썼습니다.')]


def ask(previous):
    rows = expected_rows(['질문', '물을_값', '기대_답'], KEY)
    got = guarded(M.answers, list(dict.fromkeys((r['질문'], r['물을_값']) for r in rows)))   # 같은 품번을 여러 줄에 적어도 한 번만 묻는다
    key = lambda r: f"{r['질문']} | {r['물을_값']} | {r.get('항목', '')}"
    exp = [{'짝': key(r), '답': norm(r['기대_답'])} for r in rows]
    act = [{'짝': key(r), '답': norm(r['답'])} for r in got]
    return [R.compare('기대 답 ↔ 모델에 물은 답(질문 | 물을 값 | 항목)', '짝', exp, act, ['답'])] + run_check()


STEPS = [
    dict(no=1, name='폴더와 출발점 확인', slots=[], run=sources),
    dict(no=2, name='파일을 바꾸지 않고 자료 파악', slots=[], run=None),
    dict(no=3, name='요구와 기대 답 정하기', slots=['결과/기대_답.csv'], run=expected),
    dict(no=4, name='판단① 기준일에 쓸 견적 정하기', slots=['결과/quote_rule.py'], run=quotes),
    dict(no=5, name='판단② 승인과 함께 볼 것 정하기', slots=['결과/approval_rule.py'], run=approval),
    dict(no=6, name='물어보고 대조 · 구조 검사', slots=[], run=ask),
    dict(no=7, name='저장하고 다시 열기', slots=[], run=None),
]
