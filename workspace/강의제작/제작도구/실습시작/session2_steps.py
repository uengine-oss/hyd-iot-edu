"""2회차 네 랩의 lab_steps.py 원문(학생 폴더에 넣는 제공 파일 — 답 0). build_labs.py가 랩마다 하나를 고른다.

lab_steps.py 계약(lab_frame · show_result): TITLE, STEPS = [dict(no, name, slots, run)]. run(previous) → 블록 목록.
여기의 글은 학생 파일 · 제공 흐름의 출력만 그린다 — 기대 답은 학생이 `결과/기대_답.csv`에 적은 것만 쓴다.
"""

COMMON = '''
from pathlib import Path
import re
import subprocess
import sys
import show_result as R

HERE = Path(__file__).resolve().parent


def norm(text):
    """답 글자 견주기: 「·」 · 쉼표 · 공백으로 나눈 조각을 정렬해 다시 잇는다(순서 · 띄어쓰기 차이는 같게 본다)."""
    return ' · '.join(sorted(x for x in re.split(r'[·,\\s]+', str(text or '')) if x))


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
    path = HERE / '결과/기대_답.csv'
    rows = R.read_table(path)
    text, _ = R.read_text(path)
    lines = [i for i, x in enumerate(text.splitlines(), 1) if x.strip() and not x.lstrip().startswith('#')][1:]   # 데이터 행의 편집기 줄 번호
    seen = {{}}
    for line, r in zip(lines, rows):
        empty = [c for c in columns if not r.get(c)]
        if empty:
            raise R.Stop(f'결과/기대_답.csv:{{line}}: 빈 칸 ' + ', '.join(empty))
        k = tuple(r.get(c, '') for c in key)
        if k in seen:
            raise R.Stop(f'결과/기대_답.csv:{{seen[k]}} · {{line}}: 같은 ({{" · ".join(key)}}) 「{{" · ".join(k)}}」가 두 줄입니다 — 한 짝에 한 줄만 씁니다(여러 값은 한 칸에 「 · 」로).')
        seen[k] = line
    return rows


def need_decided(points):
    """이 기능이 쓰는 결정이 결과/정한_것.csv에 정해졌는가(빈 틀에 지점 줄이 미리 있다). 고른_것 · 근거가 비었거나 미결이면 그 줄을 짚고 멈춘다 — 고른 것이 맞는지는 보지 않는다."""
    path = HERE / '결과/정한_것.csv'
    text, _ = R.read_text(path)
    lines = [i for i, x in enumerate(text.splitlines(), 1) if x.strip() and not x.lstrip().startswith('#')][1:]
    rows = {{(r.get('지점') or '').strip(): (line, r) for line, r in zip(lines, R.read_table(path))}}
    for point in points:
        if point not in rows:
            raise R.Stop(f'결과/정한_것.csv: 지점 「{{point}}」 줄이 없습니다 — 받은 빈 틀의 지점 줄을 지우지 않습니다.')
        line, r = rows[point]
        if not (r.get('고른_것') or '').strip() or r['고른_것'].strip() == '미결' or not (r.get('근거') or '').strip():
            raise R.Stop(f'결과/정한_것.csv:{{line}}: 「{{point}}」의 고른_것 · 근거가 아직 비어 있습니다(미결 포함). 이 기능은 이 결정대로 결과를 냅니다 — '
                         '원자료를 보고 고른 것과 근거 줄을 적은 뒤 다시 실행합니다. AI가 대신 고르지 않습니다.')


def run_check():
    p = subprocess.run([sys.executable, 'check.py'], cwd=HERE, capture_output=True, text=True, encoding='utf-8', errors='replace')
    text = (p.stdout + p.stderr).strip()
    return [R.note('python check.py\\n' + text)] if p.returncode == 0 else [R.error('python check.py — 구조 확인 필요', text)]
'''

DESIGN_INTEGRATED = '''"""{title} — 결과 화면의 단계(START.md 「진행 단계」와 같은 번호 · 이름). 제공 파일 — 바꾸지 않는다."""
''' + COMMON + '''
import model_tool as M

TITLE = {title!r}
KEY = ['질문', '물을_값', '항목']   # 기대 답 한 줄을 가리키는 열


def guarded(fn, *a):
    try:
        return fn(*a)
    except M.Stop as e:
        raise R.Stop(str(e))


def sources(previous):
    rows = [(p.name, len(R.read_table(p))) for p in sorted((HERE / '자료').glob('*.csv'))]
    out = [R.counts('원자료 파일마다 행 수(머리줄 뺌)', rows)]
    drawing = HERE / '자료/관계그림.json'
    if drawing.is_file():   # 그림 도구 JSON은 편집기로 열면 그림이 아니라 글이라, 연결만 표로 보인다
        import json
        g = json.loads(drawing.read_text(encoding='utf-8-sig'))
        g = g.get('graph', g)
        cap = {{n['id']: (n.get('caption') or '') + (' (' + ' · '.join(n.get('labels', [])) + ')' if n.get('labels') else '') for n in g.get('nodes', [])}}
        out.append(R.table('출발 그림(자료/관계그림.json)의 연결 — 시작 → 끝', ['시작', '관계', '끝'],
                           [(cap.get(r['fromId'], r['fromId']), r.get('type', ''), cap.get(r['toId'], r['toId'])) for r in g.get('relationships', [])]))
    out.append(R.note('이번 질문에 쓰는 것은 설비 대장 · 구성 요소 · 센서 · 예비품 · 품번 교차표입니다. 줄은 VS Code에서 열어 보고, 결과 화면은 단계마다 다시 씁니다.'))
    return out


def expected(previous):
    rows = expected_rows(['질문', '물을_값', '기대_답', '근거'], KEY)
    return [R.table('내가 원자료에서 먼저 적은 기대 답', ['질문', '물을_값', '항목', '기대_답', '근거'], rows)]


def design(previous):
    ids, links, prev = guarded(M.preview_ids)
    out = [R.table('종류와 ID 만드는 법(결과/설계.csv)', ['대상', 'ID_만드는_법'], [(k, v) for k, v in ids.items()],
                   note=('실물 행이 있어 구성 요소(자리)와 일련번호가 붙은 실물을 따로 둡니다.' if '실물' in ids else
                         '실물 행이 없어 일련번호는 구성 요소의 속성으로 둡니다.')),
           R.table('관계와 방향 · 카디널리티(결과/관계.csv)', ['연결', '관계 이름', '시작 → 끝', '카디널리티'], [(k, v[0], f'{{v[1]}} → {{v[2]}}', v[3]) for k, v in links.items()],
                   note='카디널리티는 시작 쪽 수:끝 쪽 수이고 1은 많아야 하나입니다. 만든 연결이 적은 수를 넘으면 그 단계에서 멈추고 관계.csv 줄과 원자료 줄을 짚습니다.')]
    out.append(R.counts('원자료 행마다 내 ID를 지으면 — 서로 다른 ID 수', [(k, v['개수']) for k, v in prev.items()]))
    clash = [(k, i, ', '.join(f"{{v['파일']}}:{{n}}" for n in lines)) for k, v in prev.items() for i, lines in v['겹침'].items()]
    out.append(R.table('ID가 겹치는 원자료 행(이름 묶기 전)', ['대상', 'ID', '행'], clash,
                       note='겹친 ID 하나는 대상 하나가 됩니다. 같은 대상의 겹침인지, 다른 대상을 한 ID로 짓는 것인지는 원자료 줄을 열어 봅니다.'))
    return out


def names(previous):
    info, _ = guarded(M.build, '이름')
    rows = [(code, made_from, made) for code, (made_from, made) in info['구성 요소'].items()]
    n = info['이름']
    out = [R.table('내 규칙(same_device · group_name)으로 묶인 이름', ['이름', '행 수', '원자료 이름(설비)'], n['묶음'],
                   note='묶음마다 원자료 이름과 설비를 보고, 같은 장치가 아닌 것이 섞였는지 원자료 줄로 봅니다.'),
           R.table('결과/이름.csv로 바꾼 이름', ['이름표 행', '원자료 이름', '모델', '규칙대로면', '바꾼 이름'], n['이름표']),
           R.table('다른 이름과 묶이지 않은 원자료 이름(그대로 씀)', ['원자료 행', '설비', '계통', '원자료 이름'], n['그대로'],
                   note='같은 장치인데 규칙이 묶지 못한 이름이면 결과/이름.csv에 근거와 함께 한 줄을 적습니다.'),
           R.table('설비별 구성 요소 — 원자료 행 수와 만든 대상 수', ['설비', '원자료 행', '만든 구성 요소'], rows)]
    if info['실물'] is not None:
        out.append(R.table('구성 요소 자리마다 실물(일련번호)', ['구성 요소 ID', '일련번호', '지금 · 지난', '원자료 행'], info['실물'],
                           note='일련번호가 적힌 구성 요소 행마다 실물 하나입니다. 지난 실물은 결과/행_처리.csv의 「지난 실물」 행이고, 이 모델에서 그 실물의 자리와 이력을 물을 수 있습니다.'))
    else:
        out.append(R.note('실물을 따로 두지 않았습니다. 일련번호는 구성 요소의 속성(지금 달린 것 하나)이고, 결과/행_처리.csv에서 뺀 행의 실물(철거된 장치 등)은 이 모델에서 물을 수 없습니다.'))
    out.append(R.table('결과/행_처리.csv · 결과/이름.csv에 적었지만 쓰이지 않은 행', ['파일', '행'], info['unused'] + [(x, '') for x in n['안_쓴_이름표']]))
    return out


def sensors(previous):
    info, _ = guarded(M.build, '센서')
    groups = {{}}
    for sid, code, tag, q, kind in info['센서']:
        groups.setdefault(q, []).append(f'{{code}}:{{tag}}')
    kinds = {{}}
    for *_, kind in info['센서']:
        kinds[kind] = kinds.get(kind, 0) + 1
    q = info['물리량']
    return [R.counts('센서 수와 종류(kind_of)', [('센서', len(info['센서'])), *sorted(kinds.items())]),
            R.table('물리량마다 묶인 센서(same_quantity · quantity_name)', ['물리량', '센서 수', '설비:태그'], [(k, len(v), ' · '.join(sorted(v))) for k, v in sorted(groups.items())]),
            R.table('결과/물리량.csv로 바꾼 센서', ['이름표 행', '원자료 행', '설비:태그', '재는것', '규칙대로면', '바꾼 것'], q['이름표']),
            R.table('결과/물리량.csv에 적었지만 쓰이지 않은 행', ['행'], [(x,) for x in q['안_쓴_이름표']])]


def units(previous):
    info, _ = guarded(M.build, '단위')
    u = info['단위']
    return [R.table('물리량마다 기준 단위(base_unit)', ['물리량', '원자료에 적힌 단위', '기준 단위', '정한 곳'], u['기준']),
            R.table('단위를 바꾸거나 빈 칸을 채운 센서 행(blank_unit)', ['원자료 행', '센서 ID', '원래 단위', '쓴 단위', '모델의 단위', '원래 정상값 / 한계', '바꾼 정상값 / 한계'], info['변환']),
            R.table('값 칸에 숫자 말고 글이 섞인 행(제공 코드는 앞의 숫자만 읽음)', ['원자료 행', '센서 ID', '칸', '원래 글', '읽은 숫자', '단위 칸'], info['섞인 값'],
                    note='섞인 글이 단위 칸과 같은 단위인지 원자료 줄로 봅니다. 다르면 그 행의 단위를 결과/단위.csv로 정합니다.'),
            R.table('결과/단위.csv에 적었지만 쓰이지 않은 행', ['행'], [(x,) for x in u['안_쓴_이름표']])]


def parts(previous):
    info, _ = guarded(M.build, '부품')
    usage = {{}}
    for code, cname, pid, how in info['이은_부품']:
        usage.setdefault(pid, set()).add(code)
    linked = [x for x in info['물은_행'] if x[4] not in ('잇지 않음', '확인 필요')]
    left = [x for x in info['물은_행'] if x[4] == '잇지 않음']
    return [R.table('부품마다 쓰는 설비(확인 필요는 빼고)', ['사내 품번', '설비 수', '설비'], [(p, len(v), ' · '.join(sorted(v))) for p, v in sorted(usage.items())]),
            R.table('내 판단 함수(find_part)가 이은 행', ['원자료 행', '설비', '구성 요소', '교체부품 칸', '이은 품번'], linked),
            R.counts('내 판단 함수(find_part)가 정한 것', [('확인 필요로 남긴 행', len(info['확인_필요'])), ('잇지 않은 빈칸 행', sum(1 for x in left if x[3] == '(빈칸)')),
                                                    ('잇지 않은 글 있는 행', sum(1 for x in left if x[3] != '(빈칸)'))]),
            R.table('확인 필요로 남긴 행', ['원자료 행', '설비', '구성 요소', '교체부품 칸', '후보 품번'], info['확인_필요'],
                    note='확인 필요는 「없음」과 다릅니다. 후보를 그래프에 따로 남겨 누가 무엇을 확인할지 보이게 합니다.'),
            R.table('잇지 않은 행', ['원자료 행', '설비', '구성 요소', '교체부품 칸', '정한 것'], left,
                    note='교체부품 칸에 글이 있는데 잇지 않은 행은 그 글과 예비품 목록을 함께 열어 까닭을 봅니다.'),
            R.table('같은 제조사 품번으로 등록된 사내 품번(same_item)', ['제조사 품번', '사내 품번', '한 물품으로'], [(c, ' · '.join(m), '예' if v else '아니오') for c, m, v in info['같은_규격']]),
            R.table('관계마다 적은 카디널리티와 만든 연결', ['연결', '관계', '적은 것', '시작 하나에 이어진 끝(최대)', '끝 하나에 이어진 시작(최대)', '견줌'], info['카디널리티']),
            R.note('결과/schema.json · 결과/graph.json을 새로 썼습니다.')]


def ask(previous):
    rows = expected_rows(['질문', '물을_값', '기대_답'], KEY)
    got = guarded(M.answers, list(dict.fromkeys((r['질문'], r['물을_값']) for r in rows)))   # 같은 설비를 여러 줄에 적어도 한 번만 묻는다
    key = lambda r: f"{{r['질문']}} | {{r['물을_값']}} | {{r.get('항목', '')}}"
    picked = {{}}      # 질문 1 · 2는 기대 답에 적은 항목만 견준다(모델이 더 돌려준 구성 요소 · 센서는 표에 넣지 않음)
    for r in rows:
        if str(r['질문']).strip() in ('1', '2'):
            picked.setdefault((str(r['질문']).strip(), r['물을_값']), set()).add(r.get('항목', ''))
    keep = [r for r in got if (str(r['질문']), r['물을_값']) not in picked or r['항목'] in picked[(str(r['질문']), r['물을_값'])]]
    value = lambda r: str(r['질문']).strip() == '2' and bool(r.get('항목'))   # 질문 2 센서 값은 차례까지 같아야 한다
    exact = lambda e, a: [x.strip() for x in str(e).split('·')] == [x.strip() for x in str(a).split('·')]
    note = (f'기대 답에 적은 항목만 견줍니다(모델이 더 돌려준 {{len(got) - len(keep)}}줄은 표에 넣지 않음). '
            '「실제 없음」은 기대 답의 항목 이름이 모델의 이름과 다르거나 모델에 없는 것입니다. 「기대 밖」은 모델이 더 돌려준 항목입니다. '
            '모델의 답 「없음」은 물은 품번 · 표기 · 설비 · 물리량이 모델에 없다는 뜻이고, 「쓰는 설비 없음」은 부품은 모델에 있지만 그 부품에 이은 구성 요소가 없다는 뜻입니다. '
            '「(확인 필요)」 항목은 확인이 필요한 후보로만 이은 설비입니다.')
    out = [R.compare('기대 답 ↔ 모델에 물은 답(질문 | 물을 값 | 항목)', '짝', [{{'짝': key(r), '답': r['기대_답']}} for r in rows if not value(r)],
                     [{{'짝': key(r), '답': r['답']}} for r in keep if not value(r)], ['답'], same=same, note=note)]
    if any(value(r) for r in rows):
        out.append(R.compare('질문 2 센서 값 — 단위 · 정상값 · 한계 · 한계구분 차례', '짝', [{{'짝': key(r), '답': r['기대_답']}} for r in rows if value(r)],
                             [{{'짝': key(r), '답': r['답']}} for r in keep if value(r)], ['답'], same=exact,
                             note='값은 차례까지 견줍니다. 단위를 바꾼 센서는 바꾼 단위의 값, 값이 없는 칸은 「없음」, 단위를 정하지 못했으면 「미확인」입니다.'))
    return out


def check(previous):
    return run_check()


STEPS = [
    dict(no=1, name={s1!r}, slots=[], run=sources),
    dict(no=2, name={s2!r}, slots=[], run=None),
    dict(no=3, name={s3!r}, slots=['결과/기대_답.csv'], run=expected),
    dict(no=4, name={s4!r}, slots=['결과/설계.csv', '결과/관계.csv'], run=design),
    dict(no=5, name={s5!r}, slots=['결과/name_rules.py', '결과/행_처리.csv'], run=names),
    dict(no=6, name={s6!r}, slots=['결과/quantity_rules.py'], run=sensors),
    dict(no=7, name={s7!r}, slots=['결과/unit_rules.py'], run=units),
    dict(no=8, name={s8!r}, slots=['결과/part_rules.py'], run=parts),
    dict(no=9, name={s9!r}, slots=[], run=ask),
    dict(no=10, name={s10!r}, slots=[], run=check),
    dict(no=11, name={s11!r}, slots=[], run=None),
]
'''

DESIGN_PRACTICAL = '''"""{title} — 결과 화면의 단계(START.md 「진행 단계」와 같은 번호 · 이름). 제공 파일 — 바꾸지 않는다."""
''' + COMMON + '''
import supply_tool as M

TITLE = {title!r}
KEY = ['질문', '물을_값', '항목']   # 기대 답 한 줄을 가리키는 열


def guarded(fn, *a):
    try:
        return fn(*a)
    except M.Stop as e:
        raise R.Stop(str(e))


def sources(previous):
    _, graph = M.base_model()
    labels = {{}}
    for n in graph['nodes']:
        labels[n['labels'][0]] = labels.get(n['labels'][0], 0) + 1
    rows = [(p.name, len(R.read_table(p))) for p in sorted((HERE / '자료').glob('*.csv'))]
    return [R.counts('제공된 설비 · 부품 모델(입력/graph.json)', sorted(labels.items()) + [('관계', len(graph['rels']))]),
            R.counts('원자료 파일마다 행 수(머리줄 뺌)', rows)]


def expected(previous):
    rows = expected_rows(['질문', '물을_값', '기대_답', '근거'], KEY)
    return [R.table('내가 원자료에서 먼저 적은 기대 답', ['질문', '물을_값', '항목', '기대_답', '근거'], rows)]


def quotes(previous):
    pairs, used, found = guarded(M.pairs, '견적')
    split = {{}}
    for v in used.values():
        split[v] = split.get(v, 0) + 1
    return [R.counts('견적 줄 — 씀 · 기준일에 안 씀', sorted(split.items()) + [('공급사 · 부품 쌍', len(pairs))]),
            R.table('공급사 · 부품 쌍마다 쓴 견적(단위를 맞춘 값과 원래 표기)', ['공급사', '사내 품번', '단가(만원)', '불량률', '불량률 원래', '납기(일)', '납기 원래', '견적일', '출처'],
                    [(p['supplier'], p['part'], p['price_manwon'], p['defect_rate'], p['defect_rate_original'] or '', p['lead_days'], p['lead_days_original'] or '', p['quote_date'], p['quote_source']) for p in pairs]),
            R.table('견적 줄마다 간 곳', ['자료/공급_조건.csv 행', '간 곳'], sorted(used.items())),
            R.table('품번 칸이 사내 품번이 아니어서 찾은 줄', ['행', '원래 글', '사내 품번', '찾은 법'], found)]


def approval(previous):
    need_decided(['조건이 붙은 승인', '빈 값의 뜻', '쓰는 사람에 따라 갈리는 답'])
    pairs, used, found = guarded(M.pairs, '승인')
    extra = sorted({{k for p in pairs for k in p}} - {{'supplier', 'part', 'price_manwon', 'defect_rate', 'defect_rate_original', 'lead_days', 'lead_days_original',
                                                     'min_order_qty', 'supplier_part_no', 'quote_date', 'valid_until', 'quote_source', 'as_of', 'approved', 'approval_source'}})
    guarded(M.write_model, pairs)
    cols = ['공급사', '사내 품번', 'approved', '승인 출처'] + extra
    return [R.counts('승인(approved)', [('참', sum(p['approved'] for p in pairs)), ('거짓', sum(not p['approved'] for p in pairs))]),
            R.table('쌍마다 승인과 내가 남긴 속성', cols, [[p['supplier'], p['part'], p['approved'], p.get('approval_source') or ''] + [p.get(k, '') for k in extra] for p in pairs]),
            R.note('결과/schema.json · 결과/graph.json을 새로 썼습니다.')]


def ask(previous):
    rows = expected_rows(['질문', '물을_값', '기대_답'], KEY)
    got = guarded(M.answers, list(dict.fromkeys((r['질문'], r['물을_값']) for r in rows)))   # 같은 품번을 여러 줄에 적어도 한 번만 묻는다
    key = lambda r: f"{{r['질문']}} | {{r['물을_값']}} | {{r.get('항목', '')}}"
    exp = [{{'짝': key(r), '답': r['기대_답']}} for r in rows]
    act = [{{'짝': key(r), '답': r['답']}} for r in got]
    return [R.compare('기대 답 ↔ 모델에 물은 답(질문 | 물을 값 | 항목)', '짝', exp, act, ['답'], same=same)] + run_check()


STEPS = [
    dict(no=1, name={s1!r}, slots=[], run=sources),
    dict(no=2, name={s2!r}, slots=[], run=None),
    dict(no=3, name={s3!r}, slots=['결과/기대_답.csv'], run=expected),
    dict(no=4, name={s4!r}, slots=['결과/quote_rule.py'], run=quotes),
    dict(no=5, name={s5!r}, slots=['결과/approval_rule.py'], run=approval),
    dict(no=6, name={s6!r}, slots=[], run=ask),
    dict(no=7, name={s7!r}, slots=[], run=None),
]
'''

GRAPH = '''"""{title} — 결과 화면의 단계(START.md 「진행 단계」와 같은 번호 · 이름). 제공 파일 — 바꾸지 않는다."""
''' + COMMON + '''
import json
import lab_cypher as C

TITLE = {title!r}
CHANGE = {change!r}
DECIDE = {decide!r}   # 기능마다 쓰는 결정 지점(질문 번호 · update)


def db(fn, *a):
    try:
        return fn(*a)
    except C.LabDbOff as e:
        raise R.Stop(str(e))
    except RuntimeError as e:
        raise R.Stop(str(e))


def graph_counts():
    path, graph = C.model_graph()
    out = {{'노드': len(graph['nodes']), '관계': len(graph['rels'])}}
    for n in graph['nodes']:
        out['종류 ' + n['labels'][0]] = out.get('종류 ' + n['labels'][0], 0) + 1
    for r in graph['rels']:
        out['관계 ' + r['type']] = out.get('관계 ' + r['type'], 0) + 1
    return path, out


def start(previous):
    path, model = graph_counts()
    have = db(C.counts)
    rows = [(k, v, have.get(k, 0)) for k, v in sorted(model.items())]
    return [R.table(f'모델 파일({{R.rel(path)}})과 지금 랩 DB의 개수', ['항목', '모델 파일', '랩 DB'], rows),
            R.note('처음 켠 랩 DB는 비어 있습니다(0). 적재한 뒤에는 두 칸이 같아야 합니다.')]


def expected(previous):
    rows = expected_rows(['질문', '물을_값', '볼_열', '기대_답', '근거'], ['질문', '물을_값'])
    return [R.table('내가 원자료에서 먼저 적은 기대 답', ['질문', '물을_값', '볼_열', '기대_답', '근거'], rows)]


def load_once():
    out = db(C.load_file, HERE / '결과/load.cypher')
    return [(R.rel(HERE / '결과/load.cypher') + f':{{line}}', target, n, ', '.join(f'{{k}} {{v}}' for k, v in res.get('stats', {{}}).items() if isinstance(v, int) and v)) for line, target, n, res in out]


def load(previous):
    done = load_once()
    _, model = graph_counts()
    have = db(C.counts)
    rows = [(k, v, have.get(k, 0), '같음' if v == have.get(k, 0) else '다름') for k, v in sorted(model.items())]
    return [R.table('적재 문장마다 넘긴 행과 바뀐 것', ['문장', '넣을 것', '넘긴 행', '바뀐 것'], done),
            R.table('모델 파일 ↔ 랩 DB 개수', ['항목', '모델 파일', '랩 DB', '견줌'], rows)]


def again(previous):
    before = db(C.counts)
    load_once()
    after = db(C.counts)
    return [R.before_after('같은 적재를 한 번 더 — 개수 전후', before, after,
                           note='늘어남이 있으면 같은 대상을 알아보는 열쇠(MERGE)가 다시 실행할 때 새로 만들고 있는 것입니다.')]


def load_and_again(previous):
    return load(previous) + again(previous)


def ask_question(number):
    need_decided(DECIDE.get(str(number), []))
    rows = [r for r in expected_rows(['질문', '물을_값', '볼_열', '기대_답'], ['질문', '물을_값']) if r['질문'] == str(number)]
    path = HERE / '결과/query.cypher'
    try:
        qs = C.questions(path)
    except RuntimeError as e:
        raise R.Stop(str(e))
    if str(number) not in qs:
        raise R.Blank(f'결과/query.cypher에 「// 질문 {{number}}」 조회가 아직 없습니다.')
    line, text = qs[str(number)]
    names = sorted(set(C.PARAM.findall(text)))
    if len(names) > 1:
        raise R.Stop(f'결과/query.cypher:{{line}}: 질문 {{number}}의 $ 자리가 {{len(names)}}개({{", ".join(names)}}) — 물을 값 하나를 $ 자리 하나로 받습니다.')
    blocks, exp, act, blanks = [], [], [], 0
    for r in rows or [{{'물을_값': '', '볼_열': ''}}]:
        params = {{names[0]: r['물을_값']}} if names else {{}}
        (_, _, cols, data), = db(C.query, path, str(number), params)
        blocks.append(R.table(f'질문 {{number}} — 물은 값 「{{r["물을_값"]}}」', cols, [[shown(v) for v in row] for row in data]))
        if r.get('볼_열'):
            if r['볼_열'] not in cols:
                raise R.Stop(f'결과/기대_답.csv: 볼_열 「{{r["볼_열"]}}」이 질문 {{number}} 결과의 열({{", ".join(cols)}})에 없습니다.')
            i = cols.index(r['볼_열'])
            exp.append({{'짝': r['물을_값'], '답': r['기대_답']}})
            act.append({{'짝': r['물을_값'], '답': ' · '.join('없음' if row[i] in (None, '') else str(row[i]) for row in data) or '0줄'}})
            blanks += sum(1 for row in data if row[i] == '')
    if exp:
        blocks.insert(0, R.compare(f'질문 {{number}} 기대 답 ↔ 조회 결과(볼_열의 값)', '짝', exp, act, ['답'], same=same,
                                   note=(f'볼_열에서 빈 글자 {{blanks}}칸을 값 없음(null)과 같은 「없음」으로 견줬습니다. 조회가 값이 없는 칸을 빈 글자로 바꾸고 있습니다 — 값 없음은 null로 돌려주는 편이 다른 조회와 섞이지 않습니다.' if blanks else '')))
    return blocks


def q1(previous):
    return ask_question(1)


def q2(previous):
    return ask_question(2)


def q3(previous):
    return ask_question(3)


def change(previous):
    need_decided(DECIDE.get('update', []))
    before = db(C.export_graph)
    first = db(C.run_file, HERE / '결과/update.cypher')
    after = db(C.export_graph)
    db(C.run_file, HERE / '결과/update.cypher')
    again = db(C.export_graph)
    d = C.diff_graphs(before, after)
    d2 = C.diff_graphs(after, again)
    rows = [(k, len(v), ' · '.join(str(x if not isinstance(x, tuple) else f'{{x[0]}} {{x[1]}}: {{x[2]}} → {{x[3]}}') for x in v[:12]) + (' …' if len(v) > 12 else '')) for k, v in d.items()]
    same = all(not v for v in d2.values())
    return [R.table('수정 전 → 수정 뒤(적재 직후와 견줌)', ['바뀜', '개수', '대상'], rows),
            R.counts('수정 뒤 개수', [('노드', len(after['nodes'])), ('관계', len(after['rels']))]),
            R.note('같은 수정을 한 번 더 실행: ' + ('더 바뀐 것 없음' if same else '또 바뀜 — ' + '; '.join(f'{{k}} {{len(v)}}' for k, v in d2.items() if v)))] + ask_question(3)


def portal(previous):
    graph = db(C.export_graph)
    label = {{n['props']['id']: n['labels'][0] for n in graph['nodes']}}
    hit = [i for i, l in label.items() if l == 'Asset' and i.endswith('HYD-01')] or [i for i, l in label.items() if l == 'Asset' and 'HYD-01' in i]
    if not hit:
        raise R.Stop('랩 DB에서 HYD-01 설비를 찾지 못했습니다 — 적재부터 다시 실행합니다.')
    rows = []
    for r in graph['rels']:
        if hit[0] in (r['a'], r['b']) or any(x in (r['a'], r['b']) for x in [r2['b'] for r2 in graph['rels'] if r2['a'] == hit[0]]):
            rows.append((r['a'], r['type'], r['b']))
    rows = [x for x in rows if '쿨러' in ' '.join(x) or 'cooler' in ' '.join(x) or x[0] == hit[0]]
    return [R.table('내 그래프 — HYD-01에서 시작하는 관계(시작 → 끝)', ['시작 id', '관계', '끝 id'], sorted(set(rows)),
                    note='가이드 이 단계의 포털 기준 지도 표와 나란히 놓고 식별자와 방향을 견줍니다.')]


STEPS = {steps}
'''

GRAPH_STEPS_INTEGRATED = '''[
    dict(no=1, name={s1!r}, slots=[], run=start),
    dict(no=2, name={s2!r}, slots=[], run=None),
    dict(no=3, name={s3!r}, slots=['결과/기대_답.csv'], run=expected),
    dict(no=4, name={s4!r}, slots=['결과/load.cypher'], run=load),
    dict(no=5, name={s5!r}, slots=[], run=again),
    dict(no=6, name={s6!r}, slots=['결과/query.cypher'], run=q1),
    dict(no=7, name={s7!r}, slots=['결과/query.cypher'], run=q2),
    dict(no=8, name={s8!r}, slots=['결과/query.cypher'], run=q3),
    dict(no=9, name={s9!r}, slots=['결과/update.cypher'], run=change),
    dict(no=10, name={s10!r}, slots=[], run=portal),
    dict(no=11, name={s11!r}, slots=[], run=None),
]'''

GRAPH_STEPS_PRACTICAL = '''[
    dict(no=1, name={s1!r}, slots=[], run=start),
    dict(no=2, name={s2!r}, slots=[], run=None),
    dict(no=3, name={s3!r}, slots=['결과/기대_답.csv'], run=expected),
    dict(no=4, name={s4!r}, slots=['결과/load.cypher'], run=load_and_again),
    dict(no=5, name={s5!r}, slots=['결과/query.cypher'], run=q1),
    dict(no=6, name={s6!r}, slots=['결과/query.cypher'], run=q2),
    dict(no=7, name={s7!r}, slots=[], run=None),
]'''


def render(kind, title, names, change=False):
    """kind = design_integrated · design_practical · graph_integrated · graph_practical, names = 단계 이름(START 「진행 단계」 순서)."""
    s = {f's{i}': n for i, n in enumerate(names, 1)}
    if kind == 'design_integrated':
        return DESIGN_INTEGRATED.format(title=title, **s)
    if kind == 'design_practical':
        return DESIGN_PRACTICAL.format(title=title, **s)
    steps = (GRAPH_STEPS_INTEGRATED if kind == 'graph_integrated' else GRAPH_STEPS_PRACTICAL).format(**s)
    decide = {'3': ['시점과 상태'], 'update': ['불용 결정 설비']} if kind == 'graph_integrated' else {'1': ['쓰는 사람에 따라 갈리는 답']}
    return GRAPH.format(title=title, change=change, steps=steps, decide=decide)
