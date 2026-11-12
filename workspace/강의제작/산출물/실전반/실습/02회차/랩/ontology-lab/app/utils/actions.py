from pathlib import Path
import re
import subprocess
import sys
from app.utils import results as R

HERE = Path(__file__).resolve().parents[2]


def norm(text):
    """답 글자 견주기: 「·」 · 쉼표 · 공백으로 나눈 조각을 정렬해 다시 잇는다(순서 · 띄어쓰기 차이는 같게 본다)."""
    return ' · '.join(sorted(x for x in re.split(r'[·,\s]+', str(text or '')) if x))


def same(expected, actual):
    """대조 화면은 적은 글을 그대로 보이고, 같음 여부만 norm으로 견준다."""
    return norm(expected) == norm(actual)


def shown(value):
    """조회 결과 칸을 화면 글로: 값 없음은 「없음」, 목록은 「 · 」로 잇는다."""
    if value is None:
        return '없음'
    if isinstance(value, list):
        return ' · '.join(shown(v) for v in value) or '없음'
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def expected_rows(columns, key):
    """기대 답 표의 행. key = 한 행을 가리키는 열들 — 같은 짝이 두 줄이면 결과 화면이 한 줄을 조용히 덮으므로 두 줄 번호를 대고 멈춘다."""
    path = HERE / 'app/features/expected.csv'
    rows = R.read_table(path)
    text, _ = R.read_text(path)
    lines = [i for i, x in enumerate(text.splitlines(), 1) if x.strip() and not x.lstrip().startswith('#')][1:]   # 데이터 행의 편집기 줄 번호
    seen = {}
    for line, r in zip(lines, rows):
        empty = [c for c in columns if not r.get(c)]
        if empty:
            raise R.Stop(f'app/features/expected.csv:{line}: 빈 칸 ' + ', '.join(empty))
        k = tuple(r.get(c, '') for c in key)
        if k in seen:
            raise R.Stop(f'app/features/expected.csv:{seen[k]} · {line}: 같은 ({" · ".join(key)}) 「{" · ".join(k)}」가 두 줄입니다 — 한 짝에 한 줄만 씁니다(여러 값은 한 칸에 「 · 」로).')
        seen[k] = line
    return rows


def need_decided(points):
    """이 기능이 쓰는 결정이 app/features/decisions.csv에 정해졌는가(빈 틀에 지점 줄이 미리 있다). 고른_것 · 근거가 비었거나 미결이면 그 줄을 짚고 멈춘다 — 고른 것이 맞는지는 보지 않는다."""
    path = HERE / 'app/features/decisions.csv'
    text, _ = R.read_text(path)
    lines = [i for i, x in enumerate(text.splitlines(), 1) if x.strip() and not x.lstrip().startswith('#')][1:]
    rows = {(r.get('지점') or '').strip(): (line, r) for line, r in zip(lines, R.read_table(path))}
    for point in points:
        if point not in rows:
            raise R.Stop(f'app/features/decisions.csv: 지점 「{point}」 줄이 없습니다 — 받은 빈 틀의 지점 줄을 지우지 않습니다.')
        line, r = rows[point]
        if not (r.get('고른_것') or '').strip() or r['고른_것'].strip() == '미결' or not (r.get('근거') or '').strip():
            raise R.Stop(f'app/features/decisions.csv:{line}: 「{point}」의 고른_것 · 근거가 아직 비어 있습니다(미결 포함). 이 기능은 이 결정대로 결과를 냅니다 — '
                         '원자료를 보고 고른 것과 근거 줄을 적은 뒤 다시 실행합니다. AI가 대신 고르지 않습니다.')


def run_check():
    p = subprocess.run([sys.executable, '-m', 'app.utils.check'], cwd=HERE, capture_output=True, text=True, encoding='utf-8', errors='replace')
    text = (p.stdout + p.stderr).strip()
    return [R.note('python run.py check\n' + text)] if p.returncode == 0 else [R.error('python run.py check — 구조 확인 필요', text)]

from app.utils import supply as M

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
    rows = [(p.name, len(R.read_table(p))) for p in sorted((HERE / 'data').glob('*.csv'))]
    return [R.counts('제공된 설비 · 부품 모델(data/model/graph.json)', sorted(labels.items()) + [('관계', len(graph['rels']))]),
            R.counts('원자료 파일마다 행 수(머리줄 뺌)', rows)]


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
            R.table('견적 줄마다 간 곳', ['data/supply_terms.csv 행', '간 곳'], sorted(used.items())),
            R.table('품번 칸이 사내 품번이 아니어서 찾은 줄', ['행', '원래 글', '사내 품번', '찾은 법'], found)]


def approval(previous):
    need_decided(['조건이 붙은 승인', '빈 값의 뜻', '쓰는 사람에 따라 갈리는 답'])
    pairs, used, found = guarded(M.pairs, '승인')
    extra = sorted({k for p in pairs for k in p} - {'supplier', 'part', 'price_manwon', 'defect_rate', 'defect_rate_original', 'lead_days', 'lead_days_original',
                                                     'min_order_qty', 'supplier_part_no', 'quote_date', 'valid_until', 'quote_source', 'as_of', 'approved', 'approval_source'})
    guarded(M.write_model, pairs)
    cols = ['공급사', '사내 품번', 'approved', '승인 출처'] + extra
    return [R.counts('승인(approved)', [('참', sum(p['approved'] for p in pairs)), ('거짓', sum(not p['approved'] for p in pairs))]),
            R.table('쌍마다 승인과 내가 남긴 속성', cols, [[p['supplier'], p['part'], p['approved'], p.get('approval_source') or ''] + [p.get(k, '') for k in extra] for p in pairs]),
            R.note('output/schema.json · output/graph.json을 새로 썼습니다.')]


def ask(previous):
    rows = expected_rows(['질문', '물을_값', '기대_답'], KEY)
    got = guarded(M.answers, list(dict.fromkeys((r['질문'], r['물을_값']) for r in rows)))   # 같은 품번을 여러 줄에 적어도 한 번만 묻는다
    key = lambda r: f"{r['질문']} | {r['물을_값']} | {item(r.get('항목', ''))}"
    exp = [{'짝': key(r), '답': r['기대_답']} for r in rows]
    act = [{'짝': key(r), '답': r['답']} for r in got]
    return [R.compare('기대 답 ↔ 모델에 물은 답(질문 | 물을 값 | 항목)', '짝', exp, act, ['답'], same=same)] + run_check()

def item(text):
    """항목 칸 견주기: 없는 품번의 「없음」은 빈칸과 같고, 공급사는 견적표 괄호 앞 이름(승인 목록의 이름)으로 맞춘다."""
    text = str(text or '').strip()
    if text == '없음':
        return ''
    if '/' in text:
        part, supplier = text.split('/', 1)
        return part.strip() + '/' + M.supplier_name(supplier)
    return text


def numbers(text):
    """같은 값의 숫자는 같은 글로 견준다(0.30 = 0.3, 35.0 = 35)."""
    out = []
    for piece in re.split(r'([·,\s]+)', str(text or '')):
        try:
            out.append(f'{float(piece):g}' if piece.strip() and piece.lower() not in ('nan', 'inf', '-inf') else piece)
        except ValueError:
            out.append(piece)
    return ''.join(out)


def same(expected, actual):
    """숫자 표기 차이(0.30 = 0.3)까지 같게 견준다. 화면에는 적은 글을 그대로 보인다."""
    return norm(numbers(expected)) == norm(numbers(actual))


def check(previous):
    return run_check()


COMMANDS = {
    'sources': ('원자료와 제공 모델', sources),
    'expected': ('기대 답', expected),
    'quotes': ('기준일에 쓸 견적', quotes),
    'approval': ('승인과 함께 볼 정보', approval),
    'query': ('질문별 대조와 구조 검사', ask),
    'check': ('구조 검사', check),
}
