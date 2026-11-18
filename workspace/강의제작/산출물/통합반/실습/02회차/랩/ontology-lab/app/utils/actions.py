from pathlib import Path
import re
import subprocess
import sys
from app.utils import results as R

HERE = Path(__file__).resolve().parents[2]


def norm(text):
    """답 글자 견주기: 「·」 · 쉼표 · 공백으로 나눈 조각을 정렬해 다시 잇는다(순서 · 띄어쓰기 차이는 같게 본다)."""
    return ' · '.join(sorted(x for x in re.split(r'[·,\s]+', str(text or '')) if x))


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
    """대조 화면은 적은 글을 그대로 보이고, 같음 여부는 조각의 순서와 숫자 표기(35 = 35.0)를 떼고 견준다 — 그 사실은 대조 표 아래 SAME_NOTE로 밝힌다."""
    return norm(numbers(expected)) == norm(numbers(actual))


SAME_NOTE = '값은 「 · 」로 나눈 조각의 순서와 숫자 표기(35와 35.0, 0.30과 0.3)를 떼고 견줍니다. 줄 순서도 보지 않습니다.'


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
                         '선택지와 그 결과를 따져 보고 내가 고른 것과 근거를 적은 뒤 다시 실행합니다.')


def run_check():
    p = subprocess.run([sys.executable, '-m', 'app.utils.check'], cwd=HERE, capture_output=True, text=True, encoding='utf-8', errors='replace')
    text = (p.stdout + p.stderr).strip()
    return [R.note('python run.py check\n' + text)] if p.returncode == 0 else [R.error('python run.py check — 구조 확인 필요', text)]

from app.utils import model as M

TITLE = '현장 정보를 체계화하는 온톨로지 직접 설계하기'
KEY = ['질문', '물을_값', '항목']   # 기대 답 한 줄을 가리키는 열


def guarded(fn, *a):
    try:
        return fn(*a)
    except M.Stop as e:
        raise R.Stop(str(e))


def sources(previous):
    rows = [(p.name, len(R.read_table(p))) for p in sorted((HERE / 'data').glob('*.csv'))]
    out = [R.counts('원자료 파일마다 행 수(머리줄 뺌)', rows)]
    drawing = HERE / 'data/relationships.json'
    if drawing.is_file():   # 그림 도구 JSON은 편집기로 열면 그림이 아니라 글이라, 연결만 표로 보인다
        import json
        g = json.loads(drawing.read_text(encoding='utf-8-sig'))
        g = g.get('graph', g)
        cap = {n['id']: (n.get('caption') or '') + (' (' + ' · '.join(n.get('labels', [])) + ')' if n.get('labels') else '') for n in g.get('nodes', [])}
        out.append(R.table('출발 그림(data/relationships.json)의 연결 — 시작 → 끝', ['시작', '관계', '끝'],
                           [(cap.get(r['fromId'], r['fromId']), r.get('type', ''), cap.get(r['toId'], r['toId'])) for r in g.get('relationships', [])]))
    out.append(R.note('원자료는 설비 대장 · 구성 요소 · 센서 · 예비품 · 품번 교차표와 현장 메모입니다. 실행한 기능의 결과를 이 화면에서 확인합니다.'))
    return out


def expected(previous):
    rows = expected_rows(['질문', '물을_값', '기대_답', '근거'], KEY)
    return [R.table('내가 정한 기대 답', ['질문', '물을_값', '항목', '기대_답', '근거'], rows)]


def design(previous):
    ids, links, prev = guarded(M.preview_ids)
    out = [R.table('종류와 식별자 만드는 법(app/features/design.csv)', ['대상', 'ID_만드는_법'], [(k, v) for k, v in ids.items()],
                   note=('실물 행이 있어 구성 요소(자리)와 일련번호가 붙은 실물을 따로 둡니다.' if '실물' in ids else
                         '실물 행이 없어 일련번호는 구성 요소의 속성으로 둡니다.')),
           R.table('관계와 방향 · 카디널리티(app/features/relations.csv)', ['연결', '관계 이름', '시작 → 끝', '카디널리티'], [(k, v[0], f'{v[1]} → {v[2]}', v[3]) for k, v in links.items()],
                   note='카디널리티는 시작 쪽 수:끝 쪽 수이고 1은 많아야 하나입니다. 만든 연결이 적은 수를 넘으면 그 단계에서 멈추고 relations.csv 줄과 원자료 줄을 짚습니다.')]
    out.append(R.counts('원자료 행마다 내 식별자를 지으면 — 서로 다른 식별자 수', [(k, v['개수']) for k, v in prev.items()]))
    clash = [(k, i, ', '.join(f"{v['파일']}:{n}" for n in lines)) for k, v in prev.items() for i, lines in v['겹침'].items()]
    out.append(R.table('식별자가 겹치는 원자료 행(이름 묶기 전)', ['대상', '식별자', '행'], clash,
                       note='겹친 식별자 하나는 대상 하나가 됩니다. 같은 대상의 겹침인지, 다른 대상을 한 식별자로 짓는 것인지는 그 원자료 줄로 봅니다.'))
    return out


def names(previous):
    info, _ = guarded(M.build, '이름')
    rows = [(code, made_from, made) for code, (made_from, made) in info['구성 요소'].items()]
    n = info['이름']
    out = [R.table('내 규칙(same_device · group_name)으로 묶인 이름', ['이름', '행 수', '원자료 이름(설비)'], n['묶음'],
                   note='묶음마다 원자료 이름과 설비를 보고, 같은 장치가 아닌 것이 섞였는지 봅니다.'),
           R.table('다른 행과 묶이지 않은 원자료 이름(그대로 씀)', ['원자료 행', '설비', '계통', '원자료 이름'], n['그대로'],
                   note='같은 장치인데 규칙이 묶지 못한 이름이 여기 있으면 app/features/name_rules.py의 기준을 고칩니다.'),
           R.table('설비별 구성 요소 — 원자료 행 수와 만든 대상 수', ['설비', '원자료 행', '만든 구성 요소'], rows)]
    if info['실물'] is not None:
        out.append(R.table('구성 요소 자리마다 실물(일련번호)', ['구성 요소 식별자', '일련번호', '지금 · 지난', '원자료 행'], info['실물'],
                           note='일련번호가 적힌 구성 요소 행마다 실물 하나입니다. 지난 실물은 app/features/row_rules.csv의 「지난 실물」 행이고, 이 모델에서 그 실물의 자리와 이력을 물을 수 있습니다.'))
    else:
        out.append(R.note('실물을 따로 두지 않았습니다. 일련번호는 구성 요소의 속성(지금 달린 것 하나)이고, app/features/row_rules.csv에서 뺀 행의 실물(철거된 장치)은 이 모델에서 물을 수 없습니다.'))
    out.append(R.table('app/features/row_rules.csv에 적었지만 쓰이지 않은 행', ['파일', '행'], info['unused']))
    return out


def sensors(previous):
    info, _ = guarded(M.build, '센서')
    groups = {}
    for sid, code, tag, q in info['센서']:
        groups.setdefault(q, []).append(f'{code}:{tag}')
    base = {q: unit for q, _, unit in info['단위']}
    return [R.counts('센서와 물리량', [('센서', len(info['센서'])), ('물리량', len(groups))]),
            R.table('물리량마다 묶인 센서(same_quantity · quantity_name)', ['물리량', '센서 수', '설비:태그', '기준 단위'], [(k, len(v), ' · '.join(sorted(v)), base[k]) for k, v in sorted(groups.items())]),
            R.table('물리량마다 원자료에 적힌 단위와 기준 단위(제공 코드)', ['물리량', '원자료에 적힌 단위', '기준 단위'], info['단위'],
                    note='기준 단위는 그 물리량의 센서 행이 가장 많이 쓴 단위입니다. 단위가 다른 값을 그대로 견주면 어긋나므로 제공 코드가 기준 단위로 바꿉니다.'),
            R.table('단위를 기준 단위로 바꾼 센서 행(제공 코드)', ['원자료 행', '센서 식별자', '물리량', '원래 단위', '모델의 단위', '원래 정상값 / 한계', '바꾼 정상값 / 한계'], info['변환'],
                    note='원래 값과 바꾼 값을 그 원자료 줄로 견줍니다. 값이 없는 칸은 0이 아니라 「없음」입니다.')]


def parts(previous):
    info, _ = guarded(M.build, '부품')
    usage = {}
    for _, code, cname, cell, pid, how in info['이은_부품']:
        usage.setdefault(pid, set()).add(code)
    return [R.table('부품의 식별자(사내 품번)와 다른 표기', ['사내 품번', '품명', '다른 표기'], info['다른_표기'],
                    note='식별자는 사내 품번 하나이고, 예전 품번 · 줄여 쓴 표기 · 제조사 품번은 그 부품을 찾는 다른 이름으로 남깁니다.'),
            R.table('교체부품 칸마다 찾은 사내 품번', ['원자료 행', '설비', '구성 요소', '교체부품 칸', '사내 품번', '찾은 법'], info['이은_부품']),
            R.table('사내 품번을 찾지 못한 교체부품 칸(잇지 않음)', ['원자료 행', '설비', '구성 요소', '교체부품 칸'], info['못_찾은_칸'],
                    note='품번 교차표에 없는 표기는 짐작해 잇지 않습니다. 여기 줄이 있으면 그 칸의 글을 품번 교차표와 견줍니다.'),
            R.table('교체부품 칸이 빈 구성 요소(잇지 않음)', ['원자료 행', '설비', '구성 요소', '교체부품 칸'], info['빈_칸'],
                    note='빈 칸은 부품으로 잇지 않습니다. 교체 부품이 따로 없는 구성 요소인지, 아직 확인하지 못한 칸인지는 현장 메모와 그 원자료 줄로 봅니다.'),
            R.table('부품마다 쓰는 설비', ['사내 품번', '설비 수', '설비'], [(p, len(v), ' · '.join(sorted(v))) for p, v in sorted(usage.items())]),
            R.table('관계마다 적은 카디널리티와 만든 연결', ['연결', '관계', '적은 것', '시작 하나에 이어진 끝(최대)', '끝 하나에 이어진 시작(최대)', '견줌'], info['카디널리티']),
            R.note('output/schema.json · output/graph.json을 새로 썼습니다.')]


def ask(previous):
    rows = expected_rows(['질문', '물을_값', '기대_답'], KEY)
    got = guarded(M.answers, list(dict.fromkeys((r['질문'], r['물을_값']) for r in rows)))   # 같은 설비를 여러 줄에 적어도 한 번만 묻는다
    key = lambda r: f"{r['질문']} | {r['물을_값']} | {r.get('항목', '')}"
    picked = {}      # 질문 1 · 2는 기대 답에 적은 항목만 견준다(모델이 더 돌려준 구성 요소 · 센서는 표에 넣지 않음)
    for r in rows:
        if str(r['질문']).strip() in ('1', '2'):
            picked.setdefault((str(r['질문']).strip(), r['물을_값']), set()).add(r.get('항목', ''))
    keep = [r for r in got if (str(r['질문']), r['물을_값']) not in picked or r['항목'] in picked[(str(r['질문']), r['물을_값'])]]
    value = lambda r: str(r['질문']).strip() == '2' and bool(r.get('항목'))   # 질문 2 센서 값은 차례까지 같아야 한다
    exact = lambda e, a: [x.strip() for x in str(e).split('·')] == [x.strip() for x in str(a).split('·')]
    note = (f'기대 답에 적은 항목만 견줍니다(모델이 더 돌려준 {len(got) - len(keep)}줄은 표에 넣지 않음). '
            '「실제 없음」은 기대 답의 항목 이름이 모델의 이름과 다르거나 모델에 없는 것입니다. 「기대 밖」은 모델이 더 돌려준 항목입니다. '
            '모델의 답 「없음」은 물은 품번 · 표기 · 설비 · 물리량이 모델에 없다는 뜻이고, 「쓰는 설비 없음」은 부품은 모델에 있지만 그 부품에 이은 구성 요소가 없다는 뜻입니다. ' + SAME_NOTE)
    out = [R.compare('기대 답 ↔ 모델에 물은 답(질문 | 물을 값 | 항목)', '짝', [{'짝': key(r), '답': r['기대_답']} for r in rows if not value(r)],
                     [{'짝': key(r), '답': r['답']} for r in keep if not value(r)], ['답'], same=same, note=note)]
    if any(value(r) for r in rows):
        out.append(R.compare('질문 2 센서 값 — 단위 · 정상값 · 한계 · 한계구분 차례', '짝', [{'짝': key(r), '답': r['기대_답']} for r in rows if value(r)],
                             [{'짝': key(r), '답': r['답']} for r in keep if value(r)], ['답'], same=exact,
                             note='값은 차례까지 견줍니다. 단위를 바꾼 센서는 바꾼 단위의 값, 값이 없는 칸은 「없음」, 단위를 정하지 못했으면 「미확인」입니다.'))
    return out


def check(previous):
    return run_check()

COMMANDS = {
    'sources': ('원자료', sources),
    'expected': ('기대 답', expected),
    'design': ('식별자와 관계', design),
    'names': ('같은 장치와 실물', names),
    'quantities': ('물리량과 센서', sensors),
    'parts': ('부품과 모델', parts),
    'query': ('질문별 대조', ask),
    'check': ('구조 검사', check),
}
