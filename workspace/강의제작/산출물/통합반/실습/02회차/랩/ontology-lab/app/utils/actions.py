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


def shown_if(block):
    """볼 행이 있을 때만 펼쳐 두는 표(행이 없으면 「자세히 보기」로 접는다)."""
    return block if block['rows'] else R.folded(block)


def tally(blocks):
    """대조 표들의 견줌을 세어 화면 맨 위 결론 한 줄을 만든다."""
    states = [r['state'] for b in blocks if b['kind'] == 'compare' for r in b['rows']]
    same_rows = states.count('같음')
    if not states:
        return R.verdict('info', '견줄 기대 답이 아직 없습니다')
    if same_rows == len(states):
        return R.verdict('ok', f'기대 답과 같음 {same_rows}/{len(states)}', '모든 줄이 내가 먼저 정한 기대 답과 같습니다.')
    return R.verdict('bad', f'기대 답과 같음 {same_rows}/{len(states)}',
                     ' · '.join(f'{s} {states.count(s)}줄' for s in ('다름', '실제 없음', '기대 밖') if states.count(s)) + ' — 아래 대조 표에서 그 줄을 봅니다.')


def question_cards(rows, asked):
    """기대 답 표를 질문마다 카드 하나로. asked(행) = 그 줄에서 물은 것을 적을 글."""
    by = {}
    for r in rows:
        by.setdefault(str(r['질문']).strip(), []).append(r)
    return R.cards('질문마다 내가 정한 기대 답', [dict(title='질문 ' + q, badge=f'{len(rs)}줄', lines=[(asked(r), r['기대_답']) for r in rs]) for q, rs in by.items()], wide=True)


# 구조 검사기가 맞춰 보는 것과, 걸렸을 때 검사기가 내는 글의 꼴
CHECKS = [('노드마다 글자로 된 식별자가 있다', '문자열 id가 없는'), ('식별자가 겹치는 노드가 없다', '중복 id'), ('노드의 종류가 스키마에 있다', '종류가 없는 노드|스키마에 없는 종류'),
          ('필수 속성이 빠지지 않았다', '필수 속성'), ('속성 값의 자료형과 허용 값이 스키마와 맞다', '이어야 함|허용 값'), ('관계의 양 끝 노드가 실제로 있다', '없는 관계 끝점'),
          ('같은 관계가 두 번 들어가지 않았다', '중복 관계'), ('관계 이름과 시작 · 끝 종류가 스키마와 맞다', '스키마에 없는 관계|시작 종류가 다름|끝 종류가 다름|관계 이름이 없습니다'),
          ('카디널리티를 넘는 연결이 없다', '카디널리티|cardinality'), ('제공 코드가 받은 그대로다', '제공 파일이'), ('결정 기록의 칸이 다 찼다', 'decisions.csv')]


def run_check():
    # 검사는 UTF-8 모드(-X utf8)로 띄워 그 출력을 UTF-8로 읽는다 — 한국어 Windows의 파이썬은 파이프에 cp949로 써서 결과 화면의 한글이 깨진다
    p = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'app.utils.check'], cwd=HERE, capture_output=True, text=True, encoding='utf-8')
    text = (p.stdout + p.stderr).strip()
    ok = p.returncode == 0
    lines = [x.strip() for x in text.splitlines()]
    cards = []
    if ok or any(x.startswith('구조 확인 필요') for x in lines):      # 검사기가 맞춰 본 것마다 걸린 줄이 있는지
        at = next((i for i, x in enumerate(lines) if x.startswith('구조 확인 필요')), len(lines))
        wrong = [x for x in lines[at + 1:] if x and x != '…']
        left, items = list(wrong), []
        for name, pattern in CHECKS:
            hit = [x for x in wrong if re.search(pattern, x)]
            left = [x for x in left if x not in hit]
            items.append(dict(title=name, icon='bad' if hit else 'ok', state='bad' if hit else '', badge=f'{len(hit)}건' if hit else '', lines=hit[:3]))
        if left:
            items.append(dict(title='그 밖에 확인할 것', icon='bad', state='bad', badge=f'{len(left)}건', lines=left[:5]))
        cards = [R.cards('구조 검사가 맞춰 본 것', items)]
    if not ok:
        return [R.error('python run.py check — 구조 확인 필요', text)] + cards
    made = HERE / 'output/graph.json'
    figure = [R.class_map('검사한 그래프 — 종류마다 개수와 관계', R.read_json(made))] if made.is_file() else []
    last = lines[-1] if lines else ''
    return [R.verdict('ok', '구조 검사 통과', last.split(':', 1)[1].strip() if last.startswith('구조 검사 통과') and ':' in last else '')] + cards + figure + [R.raw('터미널 출력 원문', 'python run.py check\n' + text)]

import json
from app.utils import model as M

TITLE = '현장 정보를 체계화하는 온톨로지 직접 설계하기'
KEY = ['질문', '물을_값', '항목']   # 기대 답 한 줄을 가리키는 열
CHECKS = CHECKS[:9] + [('「끝이 적어도 하나」로 정한 관계가 빠진 인스턴스가 없다', '적어도 하나')] + CHECKS[9:]


def guarded(fn, *a):
    try:
        return fn(*a)
    except M.Stop as e:
        raise R.Stop(str(e))


def table_links(tables):
    """표와 표를 잇는 칸. 한 표에서 줄마다 값이 다른 칸(열쇠)의 값이 다른 표의 칸에 그대로 나오거나 그 칸의 글 속에 들어 있는 곳을 찾는다. [(열쇠 표, 쓰는 표, 칸 이름, 이어진 값 수)]."""
    cols = {}
    for name, rows in tables.items():
        for c in (list(rows[0]) if rows else []):
            cols[(name, c)] = [r[c] for r in rows if r[c]]
    best = {}
    for (a, ca), va in cols.items():
        keys = set(va)
        if len(va) < 2 or len(keys) != len(va) or min(len(v) for v in keys) < 3:
            continue
        for (b, cb), vb in cols.items():
            if a == b:
                continue
            same_values = keys & set(vb)
            inside = set(k for k in keys if any(k in v for v in vb)) - same_values
            found = (2, len(same_values), ca if ca == cb else ca + ' = ' + cb) if len(same_values) >= 2 else (1, len(inside), cb + ' 칸의 글 속 ' + ca) if len(inside) >= 2 else None
            if found and found > best.get((a, b), (0, 0, '')):
                best[(a, b)] = found
    return [(a, b, label, n) for (a, b), (_, n, label) in best.items()
            if (b, a) not in best or best[(a, b)] > best[(b, a)] or (best[(a, b)] == best[(b, a)] and a < b)]


def sources(previous):
    tables = dict((p.name, R.read_table(p)) for p in sorted((HERE / 'data').glob('*.csv')))
    rows = [(name, len(t)) for name, t in tables.items()]
    out = [R.verdict('info', f'원자료 표 {len(rows)}개 · {sum(n for _, n in rows)}행을 읽었습니다', '표와 표는 같은 값이 나오는 칸으로 이어집니다.'),
           R.graph('원자료 표가 이어지는 칸', [R.node(name, '원자료 표', sub=f'{len(t)}행', props=dict(열=' · '.join(t[0]) if t else '', 행=len(t))) for name, t in tables.items()],
                   [R.edge(a, b, f'{label} ({n}값)') for a, b, label, n in table_links(tables)],
                   note='화살표 = 한 표에서 줄마다 값이 다른 칸(열쇠)의 값을 다른 표가 쓰는 곳. 괄호 = 두 표에 함께 나온 값의 수.'),
           R.folded(R.counts('원자료 파일마다 행 수(머리줄 뺌)', rows))]
    drawing = HERE / 'data/relationships.json'
    if drawing.is_file():   # 그림 도구 JSON은 편집기로 열면 그림이 아니라 글이라, 여기서 그림으로 보인다
        import json
        g = json.loads(drawing.read_text(encoding='utf-8-sig'))
        g = g.get('graph', g)
        cap = {n['id']: (n.get('caption') or '') + (' (' + ' · '.join(n.get('labels', [])) + ')' if n.get('labels') else '') for n in g.get('nodes', [])}
        out.append(R.graph('출발 그림(data/relationships.json) — 설비 하나에서 이어지는 대상', [R.node(n['id'], (n.get('labels') or ['대상'])[0], text=n.get('caption') or n['id'], props=n.get('properties') or {},
                                  at=(n['position']['x'], n['position']['y']) if isinstance(n.get('position'), dict) and 'x' in n['position'] and 'y' in n['position'] else None) for n in g.get('nodes', [])],
                           [R.edge(r['fromId'], r['toId'], r.get('type', '')) for r in g.get('relationships', [])]))
        out.append(R.folded(R.table('출발 그림(data/relationships.json)의 연결 — 시작 → 끝', ['시작', '관계', '끝'],
                                    [(cap.get(r['fromId'], r['fromId']), r.get('type', ''), cap.get(r['toId'], r['toId'])) for r in g.get('relationships', [])])))
    return out


def expected(previous):
    rows = expected_rows(['질문', '물을_값', '기대_답', '근거'], KEY)
    return [R.verdict('info', f'기대 답 {len(rows)}줄을 정했습니다', '모델을 만든 뒤 이 답과 견줍니다.'),
            question_cards(rows, lambda r: r['물을_값'] + (' → ' + r['항목'] if r.get('항목') else '')),
            R.folded(R.table('내가 정한 기대 답', ['질문', '물을_값', '항목', '기대_답', '근거'], rows))]


def finding_cards(findings):
    """원자료 행을 내 스키마 표에 대어 보아 어긋난 곳 — 정한 줄(스키마 표의 파일:줄)마다 카드 하나, 걸린 원자료 줄을 함께."""
    by = {}
    for f in findings:
        by.setdefault((f['종류'], f['표']), []).append(f)
    return R.cards('원자료가 내 스키마 표와 어긋나는 곳', [dict(title=kind, badge=f'{len(fs)}곳', state='bad', icon='warn', text=fs[0]['글'],
                   lines=[('정한 곳', at), ('걸린 원자료 줄', ' · '.join(f['원자료'].replace('data/', '') for f in fs[:8]) + (f' … 외 {len(fs) - 8}곳' if len(fs) > 8 else ''))]) for (kind, at), fs in by.items()],
                   note='원자료가 틀린 것이 아니면 스키마 표의 그 줄(필수 · 자료형 · 끝이 적어도 하나)을 원자료에 맞게 고칩니다. 근거는 걸린 원자료 줄과 현장 메모에서 찾습니다.', wide=True)


def classes(previous):
    cls, prev, written = guarded(M.classes_view)
    where = lambda v, lines: ', '.join(f"{v['파일']}:{n}" for n in lines[:6]) + (f' … 외 {len(lines) - 6}행' if len(lines) > 6 else '')
    clash = [(k, i, where(v, lines)) for k, v in prev.items() for i, lines in v['겹침'].items()]
    blank = [(k, len(v['빈칸']), where(v, v['빈칸'])) for k, v in prev.items() if v['빈칸']]
    wrong = set(k for k, _, _ in clash) | set(k for k, _, _ in blank)
    items = [dict(title=k, kind=k, state='bad' if k in wrong else '', badge=f"{prev[k]['행']}행 → 식별자 {prev[k]['개수']}개" if k in prev else '센서 행을 내 규칙으로 묶어 만듦',
                  lines=[('의미', c['의미']), ('식별자 만드는 법', c['id'])]) for k, c in cls.items()]
    out = [R.verdict('bad', f'식별자 틀에 쓴 칸이 빈 원자료 행이 있습니다 — {sum(n for _, n, _ in blank)}행', '그 칸이 모든 행에 적혀 있는지 원자료에서 봅니다.') if blank else
           R.verdict('warn', f'식별자가 겹치는 원자료 행 {len(clash)}곳', '겹친 식별자 하나는 인스턴스 하나가 됩니다 — 같은 대상인지 그 원자료 줄로 봅니다.') if clash else
           R.verdict('ok', '식별자가 겹치는 원자료 행이 없습니다', f'클래스 {len(cls)}개'),
           R.cards('내가 정한 클래스 — 의미와 식별자', items, note='오른쪽 수 = 그 클래스의 원자료 행 수와, 내 식별자 틀로 지었을 때 서로 다른 식별자 수. 두 수가 다르면 식별자가 겹친 행이 있습니다.', wide=True)]
    if blank:
        out.append(R.cards('식별자 틀에 쓴 칸이 빈 행', [dict(title=k, kind=k, badge=f'{n}행', state='bad', icon='warn', lines=[('빈 원자료 행', rows)]) for k, n, rows in blank],
                           note='빈 값으로 지은 식별자는 서로 겹칩니다. 그 클래스의 모든 행에 값이 있는 칸으로 짓습니다.'))
    if clash:
        out.append(R.cards('식별자가 겹친 곳', [dict(title=i, badge=k, state='bad', icon='warn', kind=k, lines=[('겹친 원자료 행', rows)]) for k, i, rows in clash]))
    out.append(R.cards('센서 목록의 「재는것」 칸에 적힌 이름', [dict(title=f'{len(written)}가지', kind='물리량', text=' · '.join(written))],
                       note='원자료에 적힌 이름을 그대로 쓰면 물리량이 이만큼으로 갈립니다. 어느 이름을 같은 물리량으로 볼지는 뒤에서 내 규칙으로 정합니다.', wide=True))
    out.append(R.folded(R.table('클래스와 식별자(app/features/classes.csv)', ['클래스', '의미', 'ID_만드는_법', '원자료 행', '서로 다른 식별자'],
                                [(k, c['의미'], c['id'], prev[k]['행'] if k in prev else '', prev[k]['개수'] if k in prev else '') for k, c in cls.items()])))
    return out


def properties(previous):
    cls, props, rows = guarded(M.properties_view)
    lines = lambda r, ns: ', '.join(f"{r['파일']}:{n}" for n in ns[:6]) + (f' … 외 {len(ns) - 6}행' if len(ns) > 6 else '')
    bad = [r for r in rows if (r['필수'] and r['빈칸']) or r['안맞음']]
    cards = []
    for k in cls:
        mine = [r for r in rows if r['클래스'] == k]
        cards.append(dict(title=k, kind=k, badge=f'속성 {len(mine)}개', state='bad' if any(r in bad for r in mine) else '',
                          lines=[(r['속성'] + (' (필수)' if r['필수'] else ''), f"{r['칸']} 칸 · {r['자료형']}" + (f" · {r['단위']}" if r['단위'] else '') + (f" — {r['예']}" if r['예'] else '')) for r in mine]))
    out = [R.verdict('warn', f'원자료와 어긋나는 속성 {len(bad)}개', '필수로 정했는데 비어 있는 행이 있거나, 정한 자료형으로 읽을 수 없는 값이 있습니다.') if bad else
           R.verdict('ok', f'속성 {len(rows)}개가 원자료 행과 모두 맞습니다', '필수로 정한 속성은 모든 행에 값이 있고, 값은 정한 자료형으로 읽힙니다.'),
           R.cards('내가 정한 스키마 — 클래스마다 속성(왼쪽)과 그 속성에 들어갈 원자료의 첫 값(오른쪽 끝)', cards,
                   note='속성 이름 · 원자료 칸 · 자료형 · 필수는 스키마이고, 줄 끝의 값은 그 스키마대로 옮겨질 인스턴스 데이터의 한 예입니다.', wide=True)]
    if bad:
        out.append(R.cards('원자료와 어긋나는 속성', [dict(title=f"{r['클래스']}의 {r['속성']}", kind=r['클래스'], state='bad', icon='warn',
                           badge=' · '.join(x for x in [f"필수인데 빈 행 {len(r['빈칸'])}" if r['필수'] and r['빈칸'] else '', f"{r['자료형']}로 읽을 수 없는 값 {len(r['안맞음'])}" if r['안맞음'] else ''] if x),
                           lines=[('정한 곳', f"app/features/properties.csv:{r['줄']} — {r['칸']} 칸 · {r['자료형']} · 필수 {'예' if r['필수'] else '아니오'}")]
                           + ([('빈 원자료 행', lines(r, r['빈칸']))] if r['필수'] and r['빈칸'] else [])
                           + ([('읽을 수 없는 값', ', '.join(f"{r['파일']}:{n} 「{v}」" for n, v in r['안맞음'][:4]))] if r['안맞음'] else [])) for r in bad],
                           note='원자료가 틀린 것이 아니면 속성 표의 그 줄을 원자료에 맞게 고칩니다(비어도 되는 값이면 필수를 아니오로).', wide=True))
    out.append(R.folded(R.table('속성마다 원자료에 채워진 행(app/features/properties.csv)', ['클래스', '속성', '원자료 칸', '자료형', '필수', '단위', '원자료 행', '빈 행', '읽을 수 없는 값'],
                                [(r['클래스'], r['속성'], r['칸'], r['자료형'], '예' if r['필수'] else '아니오', r['단위'], '제공 코드가 채움' if r['행'] is None else r['행'],
                                  len(r['빈칸']), len(r['안맞음'])) for r in rows])))
    return out


def relations(previous):
    cls, links = guarded(M.relations_view)
    many = lambda side: '많아야 하나' if side == '1' else '여럿'
    items = []
    for name, start, end, card, line, least in links.values():
        a, b = card.split(':')
        items.append(dict(title=f'{start} → {end}', badge=name, lines=[
            ('카디널리티 ' + card, f'{start} 하나에 {end} {many(b)}, {end} 하나에 {start} {many(a)}'),
            ('끝이 적어도 하나', f'예 — {start}마다 {end}가 하나는 있어야 함' if least else f'아니오 — {end}가 하나도 없는 {start}도 됨')]))
    return [R.verdict('info', f'관계 {len(links)}개를 정했습니다', '화살표 방향 · 카디널리티 · 끝이 적어도 하나는 모델을 만들 때 원자료의 실제 연결과 견줍니다.'),
            R.graph('내가 설계한 클래스와 관계', [R.node(k, k, sub='식별자 ' + c['id']) for k, c in cls.items()], [R.edge(v[1], v[2], f'{v[0]} · {v[3]}') for v in links.values()],
                    note='상자 = 클래스, 화살표 = 관계(시작 → 끝), 화살표의 글 = 관계 이름 · 카디널리티.'),
            R.cards('관계마다 내가 정한 것', items, note='화살표를 「시작이 끝을 ~한다」로 소리 내어 읽어 봅니다. 질문은 이 화살표 방향으로 관계를 따라가 답을 찾습니다.', wide=True),
            R.folded(R.table('관계(app/features/relations.csv)', ['관계 이름', '시작 → 끝', '카디널리티', '끝이 적어도 하나'], [(v[0], f'{v[1]} → {v[2]}', v[3], '예' if v[5] else '아니오') for v in links.values()]))]


def names(previous):
    info, _ = guarded(M.build, '이름')
    rows = [(code, made_from, made) for code, (made_from, made) in info['구성 요소'].items()]
    n = info['이름']
    out = []
    if info['실물'] is not None:
        seats = {}
        for seat, serial, state, line in info['실물']:
            seats.setdefault(seat, []).append((serial, state, line))
        nodes, links = [], []
        for seat, units in seats.items():
            nodes.append(R.node(seat, '구성 요소', badge=f'실물 {len(units)}대' if len(units) > 1 else '', mark='ask' if len(units) > 1 else ''))
            for serial, state, line in units:
                nodes.append(R.node(seat + '|' + serial, '실물', text=serial, sub=state, mark='gone' if state == '지난' else '', props=dict(원자료_행=line, 상태=state)))
                links.append(R.edge(seat, seat + '|' + serial, state, 'gone' if state == '지난' else ''))
        many = [s for s, u in seats.items() if len(u) > 1]
        out += [R.verdict('info', f'구성 요소 자리 {len(seats)}곳에 실물 {len(info["실물"])}대', ('실물이 둘 이상 달렸던 자리: ' + ' · '.join(many)) if many else '자리마다 실물이 하나입니다.'),
                R.graph('구성 요소 자리와 그 자리에 달린 실물(일련번호) — 지금 · 지난', nodes, links,
                        note='왼쪽 = 구성 요소 자리, 오른쪽 = 그 자리에 달린 실물. 점선 = 지난 실물(교체되어 떼어 낸 것).',
                        marks=dict(ask='실물이 둘 이상 달렸던 자리', gone='지난 실물'))]
    else:
        out.append(R.verdict('info', '실물을 따로 두지 않았습니다', '일련번호는 속성 표에 적었다면 구성 요소의 속성(지금 달린 것 하나)으로 담깁니다.'))
    out += [R.gather('사람마다 다르게 적은 구성 요소 이름을 하나로', ('원자료 이름(설비)', '맞춘 이름 · 같은 자리로 본 까닭'),
                     [dict(left=[x.strip() for x in str(r[3]).split(' · ')], mid=dict(text=r[0], kind='구성 요소', sub=str(r[4]))) for r in n['묶음']],
                     note='같은 모델의 설비끼리만 맞춥니다. 이름을 맞춰도 설비마다 구성 요소는 따로 하나씩입니다.'),
            R.folded(R.table('같은 모델의 설비끼리 하나로 맞춘 구성 요소 이름(제공 코드)', ['맞춘 이름', '모델', '설비 수', '원자료 이름(설비)', '같은 자리로 본 까닭'], n['묶음'],
                             note='같은 모델의 설비에서 사람마다 다르게 적은 구성 요소 이름을 구성 요소 목록에 먼저 나온 이름 하나로 맞췄습니다. 까닭 칸은 그 행들을 같은 자리로 본 근거(같은 태그의 센서 · 같은 부품)입니다. '
                                  '맞추기 전 원자료 이름은 「다른이름」 칸으로 주므로, 속성 표에 그 칸을 담으면 다른 이름으로 남습니다.')),
            R.folded(R.table('원자료 이름 그대로 둔 구성 요소(그 모델의 설비가 하나)', ['원자료 행', '설비', '모델', '계통', '원자료 이름'], n['그대로'],
                             note='모델이 다른 설비의 구성 요소는 이름이 비슷해도 맞추지 않습니다.')),
            R.folded(R.table('설비별 구성 요소 — 원자료 행 수와 만든 인스턴스 수', ['설비', '원자료 행', '만든 구성 요소'], rows))]
    if info['실물'] is not None:
        out.append(R.folded(R.table('구성 요소 자리마다 실물(일련번호)', ['구성 요소 식별자', '일련번호', '지금 · 지난', '원자료 행'], info['실물'],
                           note='일련번호가 적힌 구성 요소 행마다 실물 하나입니다. 지난 실물은 app/features/row_rules.csv의 「지난 실물」 행이고, 이 모델에서 그 실물의 자리와 이력을 물을 수 있습니다.')))
    else:
        out.append(R.note('실물을 따로 두지 않았습니다. app/features/row_rules.csv에서 뺀 행의 실물(철거된 장치)은 이 모델에서 물을 수 없습니다.'))
    if info['unused']:
        out.append(R.table('app/features/row_rules.csv에 적었지만 쓰이지 않은 행', ['파일', '행'], info['unused']))
    return out


def sensors(previous):
    info, _ = guarded(M.build, '센서')
    groups, at = {}, {}
    for sid, code, tag, q, line, what in info['센서']:
        groups.setdefault(q, []).append(f'{code}:{tag}')
        at[f'{code}:{tag}'] = (line, what)
    base = {q: unit for q, _, unit in info['단위']}
    alone = [(v[0], k, *at[v[0]]) for k, v in sorted(groups.items()) if len(v) == 1]
    keep = info['단위_담는_법'] == '적힌 그대로'
    mixed = [r for r in info['단위'] if ' · ' in r[1]]
    out = [R.verdict('info', f'센서 {len(info["센서"])}개가 물리량 {len(groups)}개로 묶였습니다', f'내 규칙이 다른 센서와 묶지 않은 센서 {len(alone)}개 — 정말 혼자 재는 것인지 봅니다.' if alone else '한 묶음이 물리량 하나입니다 — 내가 정한 범위대로 묶였는지 봅니다.'),
           R.gather('센서가 물리량으로 묶인 모습', ('센서(설비:태그)', '물리량 · 기준 단위'),
                    [dict(left=sorted(v), mid=dict(text=k, kind='물리량', sub=base[k])) for k, v in sorted(groups.items())],
                    note='왼쪽 센서들이 오른쪽 물리량 하나를 잽니다. 같은 물리량이라고 본 센서끼리만 한 줄에 모입니다.')]
    if alone:
        out.append(R.cards('내 규칙이 다른 센서와 묶지 않은 센서', [dict(title=s, kind='센서', badge='혼자인 묶음', state='warn', lines=[('붙인 물리량 이름', q), ('원자료의 재는것', what), ('원자료 행', line)]) for s, q, line, what in alone],
                           note='규칙이 이 센서를 어떤 센서와도 같은 물리량으로 보지 않았습니다. 혼자 재는 것이 맞는지, 규칙이 놓친 것인지는 그 원자료 줄과 같은 태그 · 같은 재는것의 다른 줄로 봅니다.'))
    if info['변환']:
        out.append(R.cards('단위를 기준 단위로 바꾼 센서', [dict(title=r[1], badge=f'{r[3]} → {r[4]}', kind='센서', lines=[('물리량', r[2]), ('원래 정상값 / 한계', r[5]), ('바꾼 정상값 / 한계', r[6]), ('원자료 행', r[0])]) for r in info['변환']]))
    if keep and mixed:
        out.append(R.cards('한 물리량에 단위가 섞여 담겼습니다', [dict(title=r[0], kind='물리량', state='warn', icon='warn', lines=[('원자료에 적힌 단위', r[1])]) for r in mixed],
                           note='속성 표에서 센서의 수 속성을 「적힌 그대로」로 정해 단위를 바꾸지 않았습니다. 이 물리량의 센서 값은 단위가 달라 그대로는 견줄 수 없습니다.'))
    return out + [R.folded(R.table('물리량마다 묶인 센서(same_quantity · quantity_name)', ['물리량', '센서 수', '설비:태그', '기준 단위'], [(k, len(v), ' · '.join(sorted(v)), base[k]) for k, v in sorted(groups.items())])),
                  R.folded(R.table('물리량마다 원자료에 적힌 단위와 기준 단위(제공 코드)', ['물리량', '원자료에 적힌 단위', '기준 단위'], info['단위'],
                                   note='기준 단위는 그 물리량의 센서 행이 가장 많이 쓴 단위입니다. 센서의 수 속성을 속성 표에서 「기준 단위」로 정하면 제공 코드가 이 단위로 바꿔 담습니다(지금: ' + info['단위_담는_법'] + ').')),
                  R.folded(R.table('단위를 기준 단위로 바꾼 센서 행(제공 코드)', ['원자료 행', '센서 식별자', '물리량', '원래 단위', '모델의 단위', '원래 정상값 / 한계', '바꾼 정상값 / 한계'], info['변환'],
                          note='원래 값과 바꾼 값을 그 원자료 줄로 견줍니다. 값이 없는 칸은 0이 아니라 「없음」입니다.'))]


def parts(previous):
    info, _ = guarded(M.build, '부품')
    usage = {}
    for _, code, cname, cell, pid, how in info['이은_부품']:
        usage.setdefault(pid, set()).add(code)
    lost, off = info['못_찾은_칸'], info['어긋남']
    wrong = [r for r in info['카디널리티'] if r[5] != '맞음']
    return [R.verdict('warn', f'사내 품번을 찾지 못한 교체부품 칸 {len(lost)}개', '그 칸의 글을 품번 교차표와 견줍니다.') if lost else
            R.verdict('warn', f'모델 파일을 썼습니다 — 원자료가 내 스키마 표와 어긋나는 곳 {len(off)}곳', '아래 카드에서 정한 줄과 걸린 원자료 줄을 봅니다. 이대로면 넣기 전 검증에서 걸립니다.') if off else
            R.verdict('warn', f'모델 파일을 썼습니다 — 카디널리티를 원자료의 실제 연결보다 넓게 적은 관계 {len(wrong)}개', '아래 표에서 적은 것과 실제 연결을 견줍니다. 여럿이라고 적은 쪽이 원자료에서는 모두 하나뿐입니다.') if wrong else
            R.verdict('ok', f'교체부품 칸 {len(info["이은_부품"])}개를 부품 {len(usage)}개에 이었습니다', '여러 표기가 사내 품번 하나로 모였고, 모델 파일을 새로 썼습니다. 적은 카디널리티와 만든 연결도 모두 맞습니다.')] + (
            [finding_cards(off)] if off else []) + [
            R.gather('여러 가지로 적힌 품번이 사내 품번 하나로 모이는 모습', ('다른 표기', '부품 · 사내 품번', '쓰는 설비'),
                     [dict(left=[x.strip() for x in str(r[3]).split(' · ') if x.strip()], mid=dict(text=r[1], kind='부품', sub=r[2]),
                           right=[dict(text=c, kind='설비') for c in sorted(usage.get(r[0], []))]) for r in info['다른_표기']],
                     note='가운데가 부품 하나(사내 품번)입니다. 왼쪽은 품번 교차표에서 그 부품을 가리키는 다른 표기, 오른쪽은 그 부품을 쓰는 설비입니다.'),
            R.folded(R.table('부품의 식별자와 사내 품번 · 다른 표기', ['식별자', '사내 품번', '품명', '다른 표기'], info['다른_표기'],
                             note='사내 품번 하나에 부품 하나입니다. 다른 표기는 「다른표기」 칸으로 주므로, 속성 표에 그 칸을 담으면 그 부품을 찾는 다른 이름으로 남습니다.')),
            R.folded(R.table('교체부품 칸마다 찾은 사내 품번', ['원자료 행', '설비', '구성 요소', '교체부품 칸', '사내 품번', '찾은 법'], info['이은_부품'])),
            shown_if(R.table('사내 품번을 찾지 못한 교체부품 칸(잇지 않음)', ['원자료 행', '설비', '구성 요소', '교체부품 칸'], info['못_찾은_칸'],
                    note='품번 교차표에 없는 표기는 짐작해 잇지 않습니다. 여기 줄이 있으면 그 칸의 글을 품번 교차표와 견줍니다.')),
            R.table('교체부품 칸이 빈 구성 요소(잇지 않음)', ['원자료 행', '설비', '구성 요소', '교체부품 칸'], info['빈_칸'],
                    note='빈 칸은 부품으로 잇지 않습니다. 교체 부품이 따로 없는 구성 요소인지, 아직 확인하지 못한 칸인지는 현장 메모와 그 원자료 줄로 봅니다.'),
            R.folded(R.table('부품마다 쓰는 설비', ['사내 품번', '설비 수', '설비'], [(p, len(v), ' · '.join(sorted(v))) for p, v in sorted(usage.items())])),
            (lambda block: block if wrong else R.folded(block))(R.table('관계마다 적은 카디널리티와 만든 연결', ['연결', '관계', '적은 것', '시작 하나에 이어진 끝(최대)', '끝 하나에 이어진 시작(최대)', '견줌'], info['카디널리티'])),
            R.note('output/schema.json(스키마) · output/graph.json(인스턴스 데이터)을 새로 썼습니다.')]


def ask(previous):
    rows = expected_rows(['질문', '물을_값', '기대_답'], KEY)
    more = {}
    for r in rows:      # 질문 4(내가 더한 질문)는 답으로 볼 속성(항목)까지 넘긴다
        if str(r['질문']).strip() == '4':
            more.setdefault(('4', r['물을_값']), []).append(r.get('항목', ''))
    got = guarded(M.answers, list(dict.fromkeys((str(r['질문']).strip(), r['물을_값']) for r in rows)), more)   # 같은 설비를 여러 줄에 적어도 한 번만 묻는다
    other = {(str(g['질문']), g['물을_값'], a): g['항목'] for g in got for a in g.get('다른_이름', [])}
    have = {(str(g['질문']), g['물을_값'], g['항목']) for g in got}
    for r in rows:      # 질문 1의 항목을 원자료 이름으로 적었으면 그 구성 요소의 다른 이름으로 찾아 모델의 이름으로 견준다(모델에 그 이름의 항목이 있으면 그대로)
        k = (str(r['질문']).strip(), r['물을_값'], r.get('항목', ''))
        r['항목'] = k[2] if k in have else other.get(k, k[2])
    key = lambda r: f"{r['질문']} | {r['물을_값']} | {r.get('항목', '')}"
    picked = {}      # 질문 1 · 2는 기대 답에 적은 항목만 견준다(모델이 더 돌려준 구성 요소 · 센서는 표에 넣지 않음)
    for r in rows:
        if str(r['질문']).strip() in ('1', '2'):
            picked.setdefault((str(r['질문']).strip(), r['물을_값']), set()).add(r.get('항목', ''))
    stuck = lambda g: str(g['답']).startswith(('답할 수 없음', '찾지 못함', '견줄 수 없음'))      # 스키마에 없어서 · 방향이 달라서 답하지 못한 줄은 그 까닭을 그대로 보인다
    keep = [r for r in got if (str(r['질문']), r['물을_값']) not in picked or r['항목'] in picked[(str(r['질문']), r['물을_값'])] or stuck(r)]
    value = lambda r: str(r['질문']).strip() == '2' and bool(r.get('항목'))   # 질문 2 센서 값은 차례까지 같아야 한다
    exact = lambda e, a: [x.strip() for x in str(e).split('·')] == [x.strip() for x in str(a).split('·')]
    note = (f'기대 답에 적은 항목만 견줍니다(모델이 더 돌려준 {len(got) - len(keep)}줄은 표에 넣지 않음). '
            '물을 값과 답은 설비 코드 · 사내 품번처럼 현장이 쓰는 값이라 식별자와 속성 이름을 어떻게 지었든 같은 값으로 묻습니다. 질문 1의 항목은 원자료 이름으로 적어도 그 구성 요소의 다른 이름으로 찾습니다. '
            '「실제 없음」은 기대 답의 항목이 모델에 없는 것입니다(이름을 다르게 적었거나 모델이 그 인스턴스를 만들지 않음). 「기대 밖」은 모델이 더 돌려준 항목입니다. '
            '「답할 수 없음」은 그 답에 필요한 원자료 칸을 담은 속성이 내 스키마에 없다는 뜻이고, 「찾지 못함」은 질문이 따라가는 방향과 관계가 저장된 방향이 반대라는 뜻이며, 「견줄 수 없음」은 그 속성의 자료형으로는 크기나 앞뒤를 견줄 수 없다는 뜻입니다. '
            '모델의 답 「없음」은 물은 품번 · 표기 · 설비 · 물리량이 모델에 없다는 뜻이고, 「쓰는 설비 없음」은 부품은 모델에 있지만 그 부품에 이은 구성 요소가 없다는 뜻입니다. ' + SAME_NOTE)
    out = [R.compare('기대 답 ↔ 모델에 물은 답(질문 | 물을 값 | 항목)', '짝', [{'짝': key(r), '답': r['기대_답']} for r in rows if not value(r)],
                     [{'짝': key(r), '답': r['답']} for r in keep if not value(r)], ['답'], same=same, note=note)]
    if any(value(r) for r in rows):
        out.append(R.ordered(R.compare('질문 2 센서 값 — 단위 · 정상값 · 한계 · 한계구분 차례', '짝', [{'짝': key(r), '답': r['기대_답']} for r in rows if value(r)],
                             [{'짝': key(r), '답': r['답']} for r in keep if value(r)], ['답'], same=exact,
                             note='값은 차례까지 견줍니다. 값이 없는 칸 · 그 칸을 담은 속성이 없는 칸은 「없음」입니다. 속성 표에서 「기준 단위」로 정한 수는 바꾼 값이고, 「적힌 그대로」면 원자료에 적힌 값입니다.')))
    return [tally(out)] + out


def check(previous):
    """넣기 전 검증 — 만든 모델의 구조 검사에 더해, 원자료 행을 지금의 내 스키마 표에 다시 대어 본다(모델 파일은 고치지 않는다)."""
    out = run_check()
    try:
        info, model = M.build('부품', write=False)
    except M.Stop as e:
        return out + [R.note('원자료를 내 스키마 표에 대어 보지 못했습니다 — ' + str(e))]
    made = [HERE / 'output/schema.json', HERE / 'output/graph.json']
    stale = all(p.is_file() for p in made) and [R.read_json(p) for p in made] != [json.loads(json.dumps(x, ensure_ascii=False)) for x in model]
    if info['어긋남']:
        out.insert(1 if out and out[0]['kind'] in ('verdict', 'error') else 0, finding_cards(info['어긋남']))
        if out[0]['kind'] == 'verdict':
            out[0] = R.verdict('bad', f'원자료가 내 스키마 표와 어긋나는 곳 {len(info["어긋남"])}곳', '아래 카드의 정한 줄과 걸린 원자료 줄을 보고 스키마 표를 고친 뒤 모델을 다시 만듭니다.')
    if stale:
        out.append(R.note('스키마 표나 규칙을 고친 뒤 모델 파일을 다시 만들지 않았습니다 — python run.py parts를 실행한 뒤 다시 검증합니다.'))
    return out

COMMANDS = {
    'sources': ('원자료', sources),
    'expected': ('기대 답', expected),
    'classes': ('클래스와 식별자', classes),
    'properties': ('속성과 자료형', properties),
    'relations': ('관계와 카디널리티', relations),
    'names': ('구성 요소 이름과 실물', names),
    'quantities': ('물리량과 센서', sensors),
    'parts': ('부품과 모델', parts),
    'query': ('질문별 대조', ask),
    'check': ('넣기 전 검증', check),
}
