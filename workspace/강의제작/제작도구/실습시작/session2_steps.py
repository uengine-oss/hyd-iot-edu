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


def numbers(text):
    """같은 값의 숫자는 같은 글로 견준다(0.30 = 0.3, 35.0 = 35)."""
    out = []
    for piece in re.split(r'([·,\\s]+)', str(text or '')):
        try:
            out.append(f'{{float(piece):g}}' if piece.strip() and piece.lower() not in ('nan', 'inf', '-inf') else piece)
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
        return R.verdict('ok', f'기대 답과 같음 {{same_rows}}/{{len(states)}}', '모든 줄이 내가 먼저 정한 기대 답과 같습니다.')
    return R.verdict('bad', f'기대 답과 같음 {{same_rows}}/{{len(states)}}',
                     ' · '.join(f'{{s}} {{states.count(s)}}줄' for s in ('다름', '실제 없음', '기대 밖') if states.count(s)) + ' — 아래 대조 표에서 그 줄을 봅니다.')


def question_cards(rows, asked):
    """기대 답 표를 질문마다 카드 하나로. asked(행) = 그 줄에서 물은 것을 적을 글."""
    by = {{}}
    for r in rows:
        by.setdefault(str(r['질문']).strip(), []).append(r)
    return R.cards('질문마다 내가 정한 기대 답', [dict(title='질문 ' + q, badge=f'{{len(rs)}}줄', lines=[(asked(r), r['기대_답']) for r in rs]) for q, rs in by.items()], wide=True)


# 구조 검사기가 맞춰 보는 것과, 걸렸을 때 검사기가 내는 글의 꼴
CHECKS = [('노드마다 글자로 된 식별자가 있다', '문자열 id가 없는'), ('식별자가 겹치는 노드가 없다', '중복 id'), ('노드의 종류가 스키마에 있다', '종류가 없는 노드|스키마에 없는 종류'),
          ('필수 속성이 빠지지 않았다', '필수 속성'), ('속성 값의 자료형과 허용 값이 스키마와 맞다', '이어야 함|허용 값'), ('관계의 양 끝 노드가 실제로 있다', '없는 관계 끝점'),
          ('같은 관계가 두 번 들어가지 않았다', '중복 관계'), ('관계 이름과 시작 · 끝 종류가 스키마와 맞다', '스키마에 없는 관계|시작 종류가 다름|끝 종류가 다름|관계 이름이 없습니다'),
          ('카디널리티를 넘는 연결이 없다', '카디널리티|cardinality'), ('제공 코드가 받은 그대로다', '제공 파일이'), ('결정 기록의 칸이 다 찼다', '정한_것.csv')]


def run_check():
    # 검사는 UTF-8 모드(-X utf8)로 띄워 그 출력을 UTF-8로 읽는다 — 한국어 Windows의 파이썬은 파이프에 cp949로 써서 결과 화면의 한글이 깨진다
    p = subprocess.run([sys.executable, '-X', 'utf8', 'check.py'], cwd=HERE, capture_output=True, text=True, encoding='utf-8')
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
            items.append(dict(title=name, icon='bad' if hit else 'ok', state='bad' if hit else '', badge=f'{{len(hit)}}건' if hit else '', lines=hit[:3]))
        if left:
            items.append(dict(title='그 밖에 확인할 것', icon='bad', state='bad', badge=f'{{len(left)}}건', lines=left[:5]))
        cards = [R.cards('구조 검사가 맞춰 본 것', items)]
    if not ok:
        return [R.error('python check.py — 구조 확인 필요', text)] + cards
    made = HERE / '결과/graph.json'
    figure = [R.class_map('검사한 그래프 — 종류마다 개수와 관계', R.read_json(made))] if made.is_file() else []
    last = lines[-1] if lines else ''
    return [R.verdict('ok', '구조 검사 통과', last.split(':', 1)[1].strip() if last.startswith('구조 검사 통과') and ':' in last else '')] + cards + figure + [R.raw('터미널 출력 원문', 'python check.py\\n' + text)]
'''

DESIGN_INTEGRATED = '''"""{title} — 기능마다 실제 결과를 블록으로 돌려준다. 제공 파일 — 바꾸지 않는다."""
''' + COMMON + '''
import model_tool as M

TITLE = {title!r}
KEY = ['질문', '물을_값', '항목']   # 기대 답 한 줄을 가리키는 열


def guarded(fn, *a):
    try:
        return fn(*a)
    except M.Stop as e:
        raise R.Stop(str(e))


def table_links(tables):
    """표와 표를 잇는 칸. 한 표에서 줄마다 값이 다른 칸(열쇠)의 값이 다른 표의 칸에 그대로 나오거나 그 칸의 글 속에 들어 있는 곳을 찾는다. [(열쇠 표, 쓰는 표, 칸 이름, 이어진 값 수)]."""
    cols = {{}}
    for name, rows in tables.items():
        for c in (list(rows[0]) if rows else []):
            cols[(name, c)] = [r[c] for r in rows if r[c]]
    best = {{}}
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
    tables = dict((p.name, R.read_table(p)) for p in sorted((HERE / '자료').glob('*.csv')))
    rows = [(name, len(t)) for name, t in tables.items()]
    out = [R.verdict('info', f'원자료 표 {{len(rows)}}개 · {{sum(n for _, n in rows)}}행을 읽었습니다', '표와 표는 같은 값이 나오는 칸으로 이어집니다.'),
           R.graph('원자료 표가 이어지는 칸', [R.node(name, '원자료 표', sub=f'{{len(t)}}행', props=dict(열=' · '.join(t[0]) if t else '', 행=len(t))) for name, t in tables.items()],
                   [R.edge(a, b, f'{{label}} ({{n}}값)') for a, b, label, n in table_links(tables)],
                   note='화살표 = 한 표에서 줄마다 값이 다른 칸(열쇠)의 값을 다른 표가 쓰는 곳. 괄호 = 두 표에 함께 나온 값의 수.'),
           R.folded(R.counts('원자료 파일마다 행 수(머리줄 뺌)', rows))]
    drawing = HERE / '자료/관계그림.json'
    if drawing.is_file():   # 그림 도구 JSON은 편집기로 열면 그림이 아니라 글이라, 여기서 그림으로 보인다
        import json
        g = json.loads(drawing.read_text(encoding='utf-8-sig'))
        g = g.get('graph', g)
        cap = {{n['id']: (n.get('caption') or '') + (' (' + ' · '.join(n.get('labels', [])) + ')' if n.get('labels') else '') for n in g.get('nodes', [])}}
        out.append(R.graph('출발 그림(자료/관계그림.json) — 설비 하나에서 이어지는 대상', [R.node(n['id'], (n.get('labels') or ['대상'])[0], text=n.get('caption') or n['id'], props=n.get('properties') or {{}},
                                  at=(n['position']['x'], n['position']['y']) if isinstance(n.get('position'), dict) and 'x' in n['position'] and 'y' in n['position'] else None) for n in g.get('nodes', [])],
                           [R.edge(r['fromId'], r['toId'], r.get('type', '')) for r in g.get('relationships', [])]))
        out.append(R.folded(R.table('출발 그림(자료/관계그림.json)의 연결 — 시작 → 끝', ['시작', '관계', '끝'],
                                    [(cap.get(r['fromId'], r['fromId']), r.get('type', ''), cap.get(r['toId'], r['toId'])) for r in g.get('relationships', [])])))
    return out


def expected(previous):
    rows = expected_rows(['질문', '물을_값', '기대_답', '근거'], KEY)
    return [R.verdict('info', f'기대 답 {{len(rows)}}줄을 정했습니다', '모델을 만든 뒤 이 답과 견줍니다.'),
            question_cards(rows, lambda r: r['물을_값'] + (' → ' + r['항목'] if r.get('항목') else '')),
            R.folded(R.table('내가 정한 기대 답', ['질문', '물을_값', '항목', '기대_답', '근거'], rows))]


def design(previous):
    ids, links, prev = guarded(M.preview_ids)
    clash = [(k, i, ', '.join(f"{{v['파일']}}:{{n}}" for n in lines)) for k, v in prev.items() for i, lines in v['겹침'].items()]
    twice = set(k for k, _, _ in clash)
    nodes = [R.node(k, k, sub='식별자 ' + v, badge=f"{{prev[k]['개수']}}개" if k in prev else '', mark='bad' if k in twice else '', props=dict(식별자_만드는_법=v)) for k, v in ids.items()]
    out = [R.verdict('warn', f'식별자가 겹치는 원자료 행 {{len(clash)}}곳', '겹친 식별자 하나는 대상 하나가 됩니다 — 같은 대상인지 그 원자료 줄로 봅니다.') if clash else
           R.verdict('ok', '식별자가 겹치는 원자료 행이 없습니다', f'클래스 {{len(ids)}}개 · 관계 {{len(links)}}개'),
           R.graph('내가 설계한 클래스와 관계', nodes, [R.edge(v[1], v[2], f'{{v[0]}} · {{v[3]}}') for v in links.values()],
                   note='상자 = 클래스, 아래 글 = 식별자 만드는 법, 오른쪽 수 = 서로 다른 식별자 수. 화살표의 글 = 관계 이름 · 카디널리티.' + (' 빨간 테두리 = 식별자가 겹친 클래스.' if clash else ''))]
    if clash:
        out.append(R.cards('식별자가 겹친 곳', [dict(title=i, badge=k, state='bad', icon='warn', kind=k, lines=[('겹친 원자료 행', rows)]) for k, i, rows in clash]))
    out += [R.folded(R.table('종류와 식별자 만드는 법(결과/설계.csv)', ['대상', 'ID_만드는_법'], [(k, v) for k, v in ids.items()],
                    note=('실물 행이 있어 구성 요소(자리)와 일련번호가 붙은 실물을 따로 둡니다.' if '실물' in ids else
                          '실물 행이 없어 일련번호는 구성 요소의 속성으로 둡니다.'))),
            R.folded(R.table('관계와 방향 · 카디널리티(결과/관계.csv)', ['연결', '관계 이름', '시작 → 끝', '카디널리티'], [(k, v[0], f'{{v[1]}} → {{v[2]}}', v[3]) for k, v in links.items()],
                    note='카디널리티는 시작 쪽 수:끝 쪽 수이고 1은 많아야 하나입니다. 만든 연결이 적은 수를 넘으면 그 단계에서 멈추고 관계.csv 줄과 원자료 줄을 짚습니다.'))]
    out.append(R.folded(R.counts('원자료 행마다 내 식별자를 지으면 — 서로 다른 식별자 수', [(k, v['개수']) for k, v in prev.items()])))
    out.append(R.folded(R.table('식별자가 겹치는 원자료 행(이름을 맞추기 전)', ['대상', '식별자', '행'], clash,
                       note='겹친 식별자 하나는 대상 하나가 됩니다. 같은 대상의 겹침인지, 다른 대상을 한 식별자로 짓는 것인지는 그 원자료 줄로 봅니다.')))
    return out


def names(previous):
    info, _ = guarded(M.build, '이름')
    rows = [(code, made_from, made) for code, (made_from, made) in info['구성 요소'].items()]
    n = info['이름']
    out = []
    if info['실물'] is not None:
        seats = {{}}
        for seat, serial, state, line in info['실물']:
            seats.setdefault(seat, []).append((serial, state, line))
        nodes, links = [], []
        for seat, units in seats.items():
            nodes.append(R.node(seat, '구성 요소', badge=f'실물 {{len(units)}}대' if len(units) > 1 else '', mark='ask' if len(units) > 1 else ''))
            for serial, state, line in units:
                nodes.append(R.node(seat + '|' + serial, '실물', text=serial, sub=state, mark='gone' if state == '지난' else '', props=dict(원자료_행=line, 상태=state)))
                links.append(R.edge(seat, seat + '|' + serial, state, 'gone' if state == '지난' else ''))
        many = [s for s, u in seats.items() if len(u) > 1]
        out += [R.verdict('info', f'구성 요소 자리 {{len(seats)}}곳에 실물 {{len(info["실물"])}}대', ('실물이 둘 이상 달렸던 자리: ' + ' · '.join(many)) if many else '자리마다 실물이 하나입니다.'),
                R.graph('구성 요소 자리와 그 자리에 달린 실물(일련번호) — 지금 · 지난', nodes, links,
                        note='왼쪽 = 구성 요소 자리, 오른쪽 = 그 자리에 달린 실물. 점선 = 지난 실물(교체되어 떼어 낸 것).',
                        marks=dict(ask='실물이 둘 이상 달렸던 자리', gone='지난 실물'))]
    else:
        out.append(R.verdict('info', '실물을 따로 두지 않았습니다', '일련번호는 구성 요소의 속성(지금 달린 것 하나)입니다.'))
    out += [R.gather('사람마다 다르게 적은 구성 요소 이름을 하나로', ('원자료 이름(설비)', '맞춘 이름 · 모델'),
                     [dict(left=[x.strip() for x in str(r[3]).split(' · ')], mid=dict(text=r[0], kind='구성 요소', sub=str(r[1]))) for r in n['묶음']],
                     note='같은 모델의 설비끼리만 맞춥니다. 이름을 맞춰도 설비마다 구성 요소는 따로 하나씩입니다.'),
            R.folded(R.table('같은 모델의 설비끼리 하나로 맞춘 구성 요소 이름(제공 코드)', ['맞춘 이름', '모델', '설비 수', '원자료 이름(설비)'], n['묶음'],
                             note='같은 모델의 설비에서 사람마다 다르게 적은 구성 요소 이름을 구성 요소 목록에 먼저 나온 이름 하나로 맞췄습니다. 맞추기 전 원자료 이름은 그 구성 요소의 다른 이름으로 남습니다. '
                                  '이름을 맞춰도 설비마다 구성 요소는 따로 하나씩입니다.')),
            R.folded(R.table('원자료 이름 그대로 둔 구성 요소(그 모델의 설비가 하나)', ['원자료 행', '설비', '모델', '계통', '원자료 이름'], n['그대로'],
                             note='모델이 다른 설비의 구성 요소는 이름이 비슷해도 맞추지 않습니다.')),
            R.folded(R.table('설비별 구성 요소 — 원자료 행 수와 만든 대상 수', ['설비', '원자료 행', '만든 구성 요소'], rows))]
    if info['실물'] is not None:
        out.append(R.folded(R.table('구성 요소 자리마다 실물(일련번호)', ['구성 요소 식별자', '일련번호', '지금 · 지난', '원자료 행'], info['실물'],
                           note='일련번호가 적힌 구성 요소 행마다 실물 하나입니다. 지난 실물은 결과/행_처리.csv의 「지난 실물」 행이고, 이 모델에서 그 실물의 자리와 이력을 물을 수 있습니다.')))
    else:
        out.append(R.note('실물을 따로 두지 않았습니다. 일련번호는 구성 요소의 속성(지금 달린 것 하나)이고, 결과/행_처리.csv에서 뺀 행의 실물(철거된 장치)은 이 모델에서 물을 수 없습니다.'))
    if info['unused']:
        out.append(R.table('결과/행_처리.csv에 적었지만 쓰이지 않은 행', ['파일', '행'], info['unused']))
    return out


def sensors(previous):
    info, _ = guarded(M.build, '센서')
    groups = {{}}
    for sid, code, tag, q in info['센서']:
        groups.setdefault(q, []).append(f'{{code}}:{{tag}}')
    base = {{q: unit for q, _, unit in info['단위']}}
    out = [R.verdict('info', f'센서 {{len(info["센서"])}}개가 물리량 {{len(groups)}}개로 묶였습니다', '한 묶음이 물리량 하나입니다 — 내가 정한 범위대로 묶였는지 봅니다.'),
           R.gather('센서가 물리량으로 묶인 모습', ('센서(설비:태그)', '물리량 · 기준 단위'),
                    [dict(left=sorted(v), mid=dict(text=k, kind='물리량', sub=base[k])) for k, v in sorted(groups.items())],
                    note='왼쪽 센서들이 오른쪽 물리량 하나를 잽니다. 같은 물리량이라고 본 센서끼리만 한 줄에 모입니다.')]
    if info['변환']:
        out.append(R.cards('단위를 기준 단위로 바꾼 센서', [dict(title=r[1], badge=f'{{r[3]}} → {{r[4]}}', kind='센서', lines=[('물리량', r[2]), ('원래 정상값 / 한계', r[5]), ('바꾼 정상값 / 한계', r[6]), ('원자료 행', r[0])]) for r in info['변환']]))
    return out + [R.folded(R.table('물리량마다 묶인 센서(same_quantity · quantity_name)', ['물리량', '센서 수', '설비:태그', '기준 단위'], [(k, len(v), ' · '.join(sorted(v)), base[k]) for k, v in sorted(groups.items())])),
                  R.folded(R.table('물리량마다 원자료에 적힌 단위와 기준 단위(제공 코드)', ['물리량', '원자료에 적힌 단위', '기준 단위'], info['단위'],
                                   note='기준 단위는 그 물리량의 센서 행이 가장 많이 쓴 단위입니다. 단위가 다른 값을 그대로 견주면 어긋나므로 제공 코드가 기준 단위로 바꿉니다.')),
                  R.folded(R.table('단위를 기준 단위로 바꾼 센서 행(제공 코드)', ['원자료 행', '센서 식별자', '물리량', '원래 단위', '모델의 단위', '원래 정상값 / 한계', '바꾼 정상값 / 한계'], info['변환'],
                          note='원래 값과 바꾼 값을 그 원자료 줄로 견줍니다. 값이 없는 칸은 0이 아니라 「없음」입니다.'))]


def parts(previous):
    info, _ = guarded(M.build, '부품')
    usage = {{}}
    for _, code, cname, cell, pid, how in info['이은_부품']:
        usage.setdefault(pid, set()).add(code)
    lost = info['못_찾은_칸']
    wrong = [r for r in info['카디널리티'] if r[5] != '맞음']
    return [R.verdict('warn', f'사내 품번을 찾지 못한 교체부품 칸 {{len(lost)}}개', '그 칸의 글을 품번 교차표와 견줍니다.') if lost else
            R.verdict('ok', f'교체부품 칸 {{len(info["이은_부품"])}}개를 부품 {{len(usage)}}개에 이었습니다', '여러 표기가 사내 품번 하나로 모였고, 모델 파일을 새로 썼습니다.' + ('' if wrong else ' 적은 카디널리티와 만든 연결도 모두 맞습니다.')),
            R.gather('여러 가지로 적힌 품번이 사내 품번 하나로 모이는 모습', ('다른 표기(다른 이름으로 남김)', '부품 · 사내 품번', '쓰는 설비'),
                     [dict(left=[x.strip() for x in str(r[3]).split(' · ') if x.strip()], mid=dict(text=r[1], kind='부품', sub=r[2]),
                           right=[dict(text=c, kind='설비') for c in sorted(usage.get(r[0], []))]) for r in info['다른_표기']],
                     note='가운데가 부품 하나(사내 품번)입니다. 왼쪽은 그 부품을 찾는 다른 이름, 오른쪽은 그 부품을 쓰는 설비입니다.'),
            R.folded(R.table('부품의 식별자와 사내 품번 · 다른 표기', ['식별자', '사내 품번', '품명', '다른 표기'], info['다른_표기'],
                             note='사내 품번 하나에 부품 하나이고, 예전 품번 · 줄여 쓴 표기 · 제조사 품번은 그 부품을 찾는 다른 이름으로 남깁니다.')),
            R.folded(R.table('교체부품 칸마다 찾은 사내 품번', ['원자료 행', '설비', '구성 요소', '교체부품 칸', '사내 품번', '찾은 법'], info['이은_부품'])),
            shown_if(R.table('사내 품번을 찾지 못한 교체부품 칸(잇지 않음)', ['원자료 행', '설비', '구성 요소', '교체부품 칸'], info['못_찾은_칸'],
                    note='품번 교차표에 없는 표기는 짐작해 잇지 않습니다. 여기 줄이 있으면 그 칸의 글을 품번 교차표와 견줍니다.')),
            R.table('교체부품 칸이 빈 구성 요소(잇지 않음)', ['원자료 행', '설비', '구성 요소', '교체부품 칸'], info['빈_칸'],
                    note='빈 칸은 부품으로 잇지 않습니다. 교체 부품이 따로 없는 구성 요소인지, 아직 확인하지 못한 칸인지는 현장 메모와 그 원자료 줄로 봅니다.'),
            R.folded(R.table('부품마다 쓰는 설비', ['사내 품번', '설비 수', '설비'], [(p, len(v), ' · '.join(sorted(v))) for p, v in sorted(usage.items())])),
            (lambda block: block if wrong else R.folded(block))(R.table('관계마다 적은 카디널리티와 만든 연결', ['연결', '관계', '적은 것', '시작 하나에 이어진 끝(최대)', '끝 하나에 이어진 시작(최대)', '견줌'], info['카디널리티'])),
            R.note('결과/schema.json · 결과/graph.json을 새로 썼습니다.')]


def ask(previous):
    rows = expected_rows(['질문', '물을_값', '기대_답'], KEY)
    got = guarded(M.answers, list(dict.fromkeys((r['질문'], r['물을_값']) for r in rows)))   # 같은 설비를 여러 줄에 적어도 한 번만 묻는다
    other = {{(str(g['질문']), g['물을_값'], a): g['항목'] for g in got for a in g.get('다른_이름', [])}}
    have = {{(str(g['질문']), g['물을_값'], g['항목']) for g in got}}
    for r in rows:      # 질문 1의 항목을 원자료 이름으로 적었으면 그 구성 요소의 다른 이름으로 찾아 모델의 이름으로 견준다(모델에 그 이름의 항목이 있으면 그대로)
        k = (str(r['질문']).strip(), r['물을_값'], r.get('항목', ''))
        r['항목'] = k[2] if k in have else other.get(k, k[2])
    key = lambda r: f"{{r['질문']}} | {{r['물을_값']}} | {{r.get('항목', '')}}"
    picked = {{}}      # 질문 1 · 2는 기대 답에 적은 항목만 견준다(모델이 더 돌려준 구성 요소 · 센서는 표에 넣지 않음)
    for r in rows:
        if str(r['질문']).strip() in ('1', '2'):
            picked.setdefault((str(r['질문']).strip(), r['물을_값']), set()).add(r.get('항목', ''))
    keep = [r for r in got if (str(r['질문']), r['물을_값']) not in picked or r['항목'] in picked[(str(r['질문']), r['물을_값'])]]
    value = lambda r: str(r['질문']).strip() == '2' and bool(r.get('항목'))   # 질문 2 센서 값은 차례까지 같아야 한다
    exact = lambda e, a: [x.strip() for x in str(e).split('·')] == [x.strip() for x in str(a).split('·')]
    note = (f'기대 답에 적은 항목만 견줍니다(모델이 더 돌려준 {{len(got) - len(keep)}}줄은 표에 넣지 않음). '
            '물을 값과 답은 설비 코드 · 사내 품번처럼 현장이 쓰는 값이라 식별자를 어떻게 지었든 같은 값으로 묻습니다. 질문 1의 항목은 원자료 이름으로 적어도 그 구성 요소의 다른 이름으로 찾습니다. '
            '「실제 없음」은 기대 답의 항목이 모델에 없는 것입니다(이름을 다르게 적었거나 모델이 그 대상을 만들지 않음). 「기대 밖」은 모델이 더 돌려준 항목입니다. '
            '모델의 답 「없음」은 물은 품번 · 표기 · 설비 · 물리량이 모델에 없다는 뜻이고, 「쓰는 설비 없음」은 부품은 모델에 있지만 그 부품에 이은 구성 요소가 없다는 뜻입니다. ' + SAME_NOTE)
    out = [R.compare('기대 답 ↔ 모델에 물은 답(질문 | 물을 값 | 항목)', '짝', [{{'짝': key(r), '답': r['기대_답']}} for r in rows if not value(r)],
                     [{{'짝': key(r), '답': r['답']}} for r in keep if not value(r)], ['답'], same=same, note=note)]
    if any(value(r) for r in rows):
        out.append(R.ordered(R.compare('질문 2 센서 값 — 단위 · 정상값 · 한계 · 한계구분 차례', '짝', [{{'짝': key(r), '답': r['기대_답']}} for r in rows if value(r)],
                             [{{'짝': key(r), '답': r['답']}} for r in keep if value(r)], ['답'], same=exact,
                             note='값은 차례까지 견줍니다. 단위를 바꾼 센서는 바꾼 단위의 값, 값이 없는 칸은 「없음」, 단위를 정하지 못했으면 「미확인」입니다.')))
    return [tally(out)] + out


def check(previous):
    return run_check()
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
    try:
        need_decided([{quote_point!r}])
    except R.Stop as e:   # 그 결정이 갈리는 원자료 줄을 함께 짚는다(어느 줄을 쓸지는 정하지 않는다)
        where = ' / '.join(f"{{s}} · {{p}}: 자료/{{M.QUOTES}}:{{' · '.join(map(str, lines))}}" for s, p, lines in guarded(M.several_live))
        raise R.Stop(f'{{e}} 기준일({{M.AS_OF}})에 유효기한이 남은 견적이 둘 이상인 쌍 — {{where}}')
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
    return [R.compare('기대 답 ↔ 모델에 물은 답(질문 | 물을 값 | 항목)', '짝', exp, act, ['답'], same=same,
                      note='「다름」은 같은 짝의 값이 다른 것, 「실제 없음」은 기대 답의 짝이 모델 답에 없는 것, 「기대 밖」은 모델이 기대 답에 없는 짝을 더 돌려준 것입니다. ' + SAME_NOTE),
            decision_view()] + run_check()


def decision_view():
    """세 결정이 닿은 곳 — 질문 대조 표의 답(승인 여부 · 단가 · 불량률 · 납기)에 드러나지 않는 선택을 공급 쌍마다 보인다."""
    import json
    g = json.loads((HERE / '결과/graph.json').read_text(encoding='utf-8'))
    base = {{'approved', 'approval_status', 'price_manwon', 'defect_rate', 'lead_days', 'quote_date', 'quote_source', 'approval_source', 'as_of',
            'valid_until', 'min_order_qty', 'supplier_part_no', 'defect_rate_original', 'lead_days_original'}}
    rows = [(r['b'], r['a'], '참' if r['props'].get('approved') else '거짓', r['props'].get('approval_status', ''),
             ' · '.join(f'{{k}}={{v}}' for k, v in sorted(r['props'].items()) if k not in base) or '없음')
            for r in g['rels'] if r['type'] == 'SUPPLIES']
    return R.table('세 결정이 닿은 곳 — 공급 쌍마다 승인 여부와 내가 남긴 속성', ['사내 품번', '공급사', '승인 여부', '승인 상태', '조건 · 함께 볼 정보'], sorted(rows),
                   note='질문 대조 표에는 승인 여부 · 단가 · 불량률 · 납기만 나옵니다. 조건이 붙은 승인 · 빈 값의 뜻 · 쓰는 사람에 따라 갈리는 답의 선택은 이 표의 승인 여부와 마지막 칸으로 봅니다.')


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


def browser():
    """이 폴더 랩 DB를 Neo4j Browser로 여는 단추. 주소는 python run.py db가 지금 떠 있는 컨테이너의 포트로 적어 둔 것이다(127.0.0.1 — 이 PC 안에서만 열린다)."""
    try:
        url = json.loads(C.STATE.read_text(encoding='utf-8')).get('browser')
    except (OSError, ValueError):
        url = None
    return [R.link('Neo4j Browser에서 이 랩 DB 열기', url, note='연결 창이 뜨면 Database user에 neo4j, Password는 비워 두고 Connect.')] if url else []


def start(previous):
    path, model = graph_counts()
    have = db(C.counts)
    rows = [(k, v, have.get(k, 0)) for k, v in sorted(model.items())]
    differ = [k for k, v, h in rows if v != h]
    empty = not any(have.values())
    return [R.verdict('info', '랩 DB가 비어 있습니다 (노드 0개)', f'모델 파일에는 노드 {{model["노드"]}}개 · 관계 {{model["관계"]}}개가 있습니다.') if empty else
            R.verdict('ok', f'랩 DB와 모델 파일의 개수가 같습니다 — 노드 {{have.get("노드", 0)}}개 · 관계 {{have.get("관계", 0)}}개') if not differ else
            R.verdict('info', f'랩 DB에 노드 {{have.get("노드", 0)}}개 · 관계 {{have.get("관계", 0)}}개', f'모델 파일과 개수가 다른 항목 {{len(differ)}}개 — 적재나 수정이 반영된 것인지 봅니다.'),
            R.count_bars('모델 파일과 지금 랩 DB의 개수', ('모델 파일', '랩 DB'), model, have),
            R.folded(R.table(f'모델 파일({{R.rel(path)}})과 지금 랩 DB의 개수', ['항목', '모델 파일', '랩 DB'], rows)),
            ] + browser()


def expected(previous):
    rows = expected_rows(['질문', '물을_값', '볼_열', '기대_답', '근거'], ['질문', '물을_값'])
    return [R.verdict('info', f'기대 답 {{len(rows)}}줄을 정했습니다', '쿼리 결과를 이 답과 견줍니다.'),
            question_cards(rows, lambda r: r['물을_값'] + ' → ' + r['볼_열']),
            R.folded(R.table('내가 정한 기대 답', ['질문', '물을_값', '볼_열', '기대_답', '근거'], rows))]


def constraints(previous):
    """유일 제약 걸기 — 학생의 제약 쿼리를 실행하고, 지금 쓰는 모델의 종류마다 식별자(id)에 유일 제약이 걸렸는지와 같은 식별자로 노드를 두 번 만들 때 DB가 하는 답을 보인다.
    시험한 노드는 받아 주든 거절하든 되돌린다(랩 DB의 개수가 전후로 같지 않으면 멈춘다)."""
    path = HERE / '결과/constraints.cypher'
    model_path, graph = C.model_graph()
    labels = sorted(json.loads(model_path.with_name('schema.json').read_text(encoding='utf-8-sig'))['classes'])
    first = {{}}
    for n in graph['nodes']:
        first.setdefault(n['labels'][0], n['props'].get('id'))
    before = db(C.counts)
    try:
        done = C.constraints_file(path)
    except C.LabDbOff as e:
        raise R.Stop(str(e))
    except RuntimeError as e:
        twice = db(C.duplicates, labels)
        if twice:
            raise R.Stop(f'{{e}}\\n랩 DB에 같은 식별자의 노드가 이미 겹쳐 있어 유일 제약을 걸 수 없습니다 — ' + ' / '.join(f'{{l}} 「{{v}}」 {{c}}개' for l, v, c in twice)
                         + '. 겹친 노드를 하나만 남긴 뒤 다시 실행합니다.')
        raise R.Stop(str(e))
    have = db(C.constraints)
    unique = {{labels_[0]: name for name, kind, entity, labels_, props in have
              if entity == 'NODE' and ('UNIQUE' in kind or kind == 'NODE_KEY') and len(labels_) == 1 and props == ['id']}}
    rows, cards = [], []
    for label in labels:
        said = None
        if label not in first:
            answer = '모델에 이 종류의 인스턴스가 없어 시험하지 않음'
        else:
            said = db(C.try_create_twice, label, first[label])
            answer = '거절 — ' + said if said else '받아 줌 — 같은 식별자의 노드가 둘 생깁니다'
        rows.append((label, 'id', unique.get(label, '없음'), first.get(label, ''), answer))
        locked = label in unique and (said or label not in first)
        cards.append(dict(title=label, kind=label, icon='lock' if locked else 'open', state='ok' if locked else 'bad', badge=unique.get(label, '유일 제약 없음'),
                          text=(f'「{{first[label]}}」로 두 번 만들기 → ' + ('DB가 거절' if said else 'DB가 받아 줌(노드가 둘 생김)')) if label in first else answer,
                          lines=[('DB가 한 말' + (' — 같은 식별자의 노드가 이미 있다는 뜻' if 'already exists' in said else ''), said)] if said else []))
    after = db(C.counts)
    if after != before:
        raise RuntimeError(f'유일 제약 시험이 랩 DB의 개수를 바꿨습니다: {{before}} → {{after}}')
    opened = [c['title'] for c in cards if c['state'] == 'bad']
    return [R.verdict('warn', f'유일 제약이 없는 종류 {{len(opened)}}개 — ' + ' · '.join(opened), '이 종류는 같은 식별자의 노드가 둘 생길 수 있습니다.') if opened else
            R.verdict('ok', f'종류 {{len(labels)}}개 모두 식별자에 유일 제약이 걸렸습니다', '같은 식별자로 새로 만들면 DB가 거절합니다.'),
            R.cards('종류마다 걸린 자물쇠 — 같은 식별자로 두 번 만들 때 DB의 답', cards, note='종류마다 같은 식별자로 CREATE를 두 번 실행해 본 실제 결과입니다. 시험한 노드는 되돌렸습니다.'),
            R.folded(R.table('제약 쿼리마다 DB가 한 일', ['쿼리', '새로 건 제약'], [(R.rel(path) + f':{{line}}', res.get('stats', {{}}).get('constraints_added', 0) or '0(이미 걸려 있음)') for line, res in done])),
            R.folded(R.table('랩 DB에 걸려 있는 제약(SHOW CONSTRAINTS)', ['이름', '제약 종류', '레이블', '속성'], [(name, kind, ' · '.join(labels_), ' · '.join(props)) for name, kind, entity, labels_, props in have])),
            R.folded(R.table('종류마다 — 식별자의 유일 제약과, 같은 식별자로 노드를 두 번 만들 때 DB의 답', ['종류', '식별자', '유일 제약', '시험한 식별자', 'DB의 답'], rows,
                    note='모델의 종류(레이블)마다 그 종류의 식별자 하나로 CREATE를 두 번 실행해 본 실제 결과입니다. 유일 제약이 걸린 종류는 DB가 거절하고, 「없음」인 종류는 받아 줍니다. '
                         f'시험한 노드는 모두 되돌려 랩 DB에 남기지 않았습니다(노드 {{before["노드"]}}개 그대로).'))]


STATS = dict(nodes_created='만든 노드', nodes_deleted='지운 노드', relationships_created='만든 관계', relationship_deleted='지운 관계', relationships_deleted='지운 관계',
             properties_set='넣은 속성 값', labels_added='붙인 레이블', labels_removed='뗀 레이블', constraints_added='건 제약', constraints_removed='푼 제약')


def changed(stats):
    """DB가 돌려준 바뀐 수 — 한국어 뜻을 앞에 쓰고, DB가 쓰는 이름은 괄호에 근거로 둔다."""
    seen = [(k, v) for k, v in stats.items() if isinstance(v, int) and not isinstance(v, bool) and v]
    if not seen:
        return '바뀐 것 없음'
    return ' · '.join(f'{{STATS.get(k, k)}} {{v}}' for k, v in seen) + ' (' + ', '.join(f'{{k}} {{v}}' for k, v in seen) + ')'


def load_once():
    out = db(C.load_file, HERE / '결과/load.cypher')
    return [(R.rel(HERE / '결과/load.cypher') + f':{{line}}', target, n, changed(res.get('stats', {{}}))) for line, target, n, res in out]


def load(previous):
    done = load_once()
    _, model = graph_counts()
    have = db(C.counts)
    rows = [(k, v, have.get(k, 0), '같음' if v == have.get(k, 0) else '다름') for k, v in sorted(model.items())]
    differ = [r[0] for r in rows if r[3] == '다름']
    inside = db(C.export_graph)
    roots = sorted(set(n['props'].get('id') for n in inside['nodes']) - set(r['b'] for r in inside['rels']), key=str)
    return [R.verdict('bad', f'모델 파일과 랩 DB의 개수가 다른 항목 {{len(differ)}}개', ' · '.join(differ[:6])) if differ else
            R.verdict('ok', f'모델 파일과 랩 DB의 개수가 같습니다 — 노드 {{have.get("노드", 0)}}개 · 관계 {{have.get("관계", 0)}}개', '모델의 종류는 레이블이, 인스턴스는 노드가 됐습니다.'),
            R.count_bars('모델 파일 ↔ 랩 DB 개수', ('모델 파일', '랩 DB'), model, have)] + (
            [R.around_figure(f'랩 DB에 들어간 그래프의 한 부분 — 「{{roots[0]}}」에서 두 걸음', inside, roots[0])] if roots else []) + [
            R.folded(R.table('적재 문장마다 넘긴 행과 바뀐 것', ['문장', '넣을 것', '넘긴 행', '바뀐 것'], done)),
            R.folded(R.table('모델 파일 ↔ 랩 DB 개수', ['항목', '모델 파일', '랩 DB', '견줌'], rows))] + browser()


def again(previous):
    before = db(C.counts)
    load_once()
    after = db(C.counts)
    grew = [k for k in sorted(set(before) | set(after)) if before.get(k, 0) != after.get(k, 0)]
    return [R.verdict('bad', f'다시 넣으니 개수가 달라졌습니다 — {{len(grew)}}개 항목', ' · '.join(f'{{k}} {{before.get(k, 0)}} → {{after.get(k, 0)}}' for k in grew[:6])) if grew else
            R.verdict('ok', f'다시 넣어도 그대로입니다 — 노드 {{after.get("노드", 0)}}개 · 관계 {{after.get("관계", 0)}}개', '같은 적재를 한 번 더 실행했지만 늘어난 것이 없습니다.'),
            R.count_bars('같은 적재를 한 번 더 — 앞과 뒤의 개수', ('한 번 넣은 뒤', '한 번 더 넣은 뒤'), before, after),
            ] + ([R.before_after('같은 적재를 한 번 더 — 개수 전후', before, after,
                           note='늘어남이 있으면 같은 대상을 알아보는 열쇠(MERGE)가 다시 실행할 때 새로 만들고 있는 것입니다.')] if grew else [])


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
        if r['물을_값']:
            head = f'쿼리가 따라간 길 — 물은 값 「{{r["물을_값"]}}」'
            try:
                walk = C.walked(path, str(number), params)
            except C.LabDbOff as e:
                raise R.Stop(str(e))
            except RuntimeError as e:      # 짐작해 그리지 않는다 — 읽지 못한 까닭을 말한다
                walk = None
                blocks.append(R.cards(head, [dict(title='이 쿼리에서 길을 읽지 못했습니다', icon='warn', state='warn', text=str(e) + ' 그림만 없고, 아래 쿼리 결과와 기대 답 대조는 그대로입니다.')]))
            if walk is not None:
                blocks.append(R.walk_figure(head, walk, r['물을_값'], note='쿼리의 MATCH 패턴이 랩 DB에서 실제로 지난 노드와 관계입니다. 굵은 테두리 = 물은 값.')
                              or R.cards(head, [dict(title=r['물을_값'], icon='warn', state='warn', badge='맞는 노드 없음',
                                                     text='이 값으로 물으니 쿼리의 MATCH 패턴에 맞는 노드가 랩 DB에 하나도 없습니다. 그래서 따라간 길이 없습니다.')]))
        blocks.append(R.folded(R.table(f'질문 {{number}} — 물은 값 「{{r["물을_값"]}}」 쿼리 결과', cols, [[shown(v) for v in row] for row in data])))
        if r.get('볼_열'):
            if r['볼_열'] not in cols:
                raise R.Stop(f'결과/기대_답.csv: 볼_열 「{{r["볼_열"]}}」이 질문 {{number}} 결과의 열({{", ".join(cols)}})에 없습니다.')
            i = cols.index(r['볼_열'])
            exp.append({{'짝': r['물을_값'], '답': r['기대_답']}})
            act.append({{'짝': r['물을_값'], '답': ' · '.join('없음' if row[i] in (None, '') else str(row[i]) for row in data) or '0줄'}})
            blanks += sum(1 for row in data if row[i] == '')
    if exp:
        blocks.insert(0, R.compare(f'질문 {{number}} 기대 답 ↔ 조회 결과(볼_열의 값)', '짝', exp, act, ['답'], same=same,
                                   note=SAME_NOTE + ' ' + (f'볼_열에서 빈 글자 {{blanks}}칸을 값 없음(null)과 같은 「없음」으로 견줬습니다. 조회가 값이 없는 칸을 빈 글자로 바꾸고 있습니다 — 값 없음은 null로 돌려주는 편이 다른 조회와 섞이지 않습니다.' if blanks else '')))
    return [tally(blocks)] + blocks + browser()


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
    old = {{n['props'].get('id'): n for n in before['nodes']}}
    new = {{n['props'].get('id'): n for n in after['nodes']}}
    moved = {{}}
    for i, k, was, now in d['속성 바뀐 노드']:
        moved.setdefault(i, []).append((k, f'{{shown(was)}} → {{shown(now)}}'))
    cards = [dict(title=i, kind=new[i]['labels'][0], badge='값 바뀜', state='warn', lines=ks) for i, ks in moved.items()]
    cards += [dict(title=str(i), kind=old[i]['labels'][0], badge='사라짐', state='bad', text=str(old[i]['props'].get('name') or old[i]['props'].get('tag') or '')) for i in d['사라진 노드'][:24]]
    cards += [dict(title=str(i), kind=new[i]['labels'][0], badge='새로 생김', state='ok', text=str(new[i]['props'].get('name') or new[i]['props'].get('tag') or '')) for i in d['늘어난 노드'][:24]]
    touched = set(moved) | set(d['사라진 노드']) | set(d['늘어난 노드'])

    def side(title, data, gone, born):
        nodes = []
        for n in data['nodes']:
            i = n['props'].get('id')
            if i in touched:
                one = R.graph_node(n, mark='gone' if i in gone else 'new' if i in born else 'ask' if i in moved else '')
                if i in moved:      # 바뀐 속성의 그때 값을 노드 아래 글로
                    one['sub'] = ' · '.join(f'{{k}}: {{shown(n["props"].get(k))}}' for k, _ in moved[i])
                nodes.append(one)
        return R.graph(title, nodes[:16], [R.edge(r['a'], r['b'], r['type']) for r in data['rels'] if r['a'] in touched and r['b'] in touched],
                       marks=dict(ask='값이 바뀐 노드', gone='수정 뒤 사라지는 노드', new='새로 생긴 노드'))

    left, right = side('수정 전', before, set(d['사라진 노드']), set()), side('수정 뒤', after, set(), set(d['늘어난 노드']))
    counted = f'값이 바뀐 노드 {{len(moved)}}개 · 사라진 노드 {{len(d["사라진 노드"])}}개 · 늘어난 노드 {{len(d["늘어난 노드"])}}개'
    return [R.verdict('ok' if same else 'warn', '수정본 반영 — ' + counted, '같은 수정을 한 번 더 실행해도 더 바뀐 것이 없습니다.' if same else '같은 수정을 한 번 더 실행하니 또 바뀌었습니다 — 아래 안내를 봅니다.'),
            R.cards('바뀐 노드 — 전 → 뒤', cards, note='수정본의 줄과 하나씩 견줍니다.') if cards else R.note('노드의 값 · 개수에 바뀐 것이 없습니다.')] + (
            [R.pair('바뀐 노드를 수정 전과 뒤로 나란히', left, right, note='굵은 테두리 = 값이 바뀐 노드(아래 글 = 그때의 값), 점선 = 수정 뒤 사라지는 노드. 16개까지만 그립니다.')] if d['사라진 노드'] or d['늘어난 노드'] else []) + ([R.count_bars('수정 전 ↔ 수정 뒤 개수', ('수정 전', '수정 뒤'), R.graph_counts(before), R.graph_counts(after))]
                                      if len(before['nodes']) != len(after['nodes']) or len(before['rels']) != len(after['rels']) else []) + [
            R.folded(R.table('수정 전 → 수정 뒤(적재 직후와 견줌)', ['바뀜', '개수', '대상'], rows)),
            R.folded(R.counts('수정 뒤 개수', [('노드', len(after['nodes'])), ('관계', len(after['rels']))])),
            R.raw('같은 수정을 한 번 더 실행한 결과', '같은 수정을 한 번 더 실행: ' + ('더 바뀐 것 없음' if same else '또 바뀜 — ' + '; '.join(f'{{k}} {{len(v)}}' for k, v in d2.items() if v)))] + browser()


def portal(previous):
    """내 그래프와 기준 지도(자료의 reference_map.json — 포털 지식 지도의 한 길)를 나란히 그린다. 내 그래프는 기준 지도의 설비에서 기준 지도에 있는 관계 이름만 따라가 그린다."""
    graph = db(C.export_graph)
    ref = json.loads((HERE / '입력/reference_map.json').read_text(encoding='utf-8'))
    by = {{n['props'].get('id'): n for n in graph['nodes']}}
    holds = lambda n, value: any(v == value or (isinstance(v, list) and value in v) for v in n['props'].values())
    wanted = set(r['관계'] for r in ref['관계'])
    codes = [x['알아볼 값'] for x in ref['대상'] if not any(r['끝'] == x['id'] for r in ref['관계'])]      # 기준 지도의 출발 대상(들어오는 관계가 없는 것)
    first = set(r['시작'] for r in ref['관계']) - set(r['끝'] for r in ref['관계'])
    second = [x['알아볼 값'] for x in ref['대상'] if any(r['끝'] == x['id'] and r['시작'] in first for r in ref['관계'])]   # 출발 대상 바로 다음 대상
    starts = [i for i, n in by.items() if any(i == c or holds(n, c) for c in codes)]
    if not starts:
        raise R.Stop('랩 DB에서 기준 지도의 출발 대상(' + ' · '.join(codes) + ')을 찾지 못했습니다 — 적재부터 다시 실행합니다.')

    def step(frontier, only):
        return [(r['a'], r['type'], r['b']) for r in graph['rels'] if r['a'] in frontier and r['type'] in wanted and r['b'] in by
                and (not only or any(holds(by[r['b']], s) for s in only))]

    found = step(starts, second) or step(starts, None)      # 첫 걸음은 기준 지도의 둘째 대상과 같은 이름의 것(없으면 전부)
    links, keep = list(found), set(starts)
    for _ in range(3):
        frontier = set(b for _, _, b in found) - keep
        keep |= frontier
        found = step(frontier, None)
        links += found
    keep |= set(b for _, _, b in links)
    links = sorted(set(links))
    mine = R.graph('내 그래프(랩 DB)', [R.graph_node(n) for i, n in by.items() if i in keep], [R.edge(a, b, t) for a, t, b in links])
    name = {{x['id']: f"{{x['id']}}({{x['알아볼 값']}})" for x in ref['대상']}}
    theirs = R.graph('기준 지도(포털 지식 지도의 같은 길)', [R.node(x['id'], x['종류'], sub=x['알아볼 값'], props=dict(알아볼_값=x['알아볼 값'])) for x in ref['대상']],
                     [R.edge(r['시작'], r['끝'], r['관계']) for r in ref['관계']])
    return [R.verdict('info', '내 그래프와 기준 지도를 나란히 놓았습니다', f'내 그래프 노드 {{len(keep)}}개 · 기준 지도 노드 {{len(ref["대상"])}}개 — 같은 대상을 몇 개로 셌는지 견줍니다.'),
            R.pair('같은 길을 두 그래프가 어떻게 그렸나', mine, theirs, note='설비 여럿이 구성 요소 하나를 함께 가리키는지, 설비마다 따로 두었는지 식별자와 화살표로 견줍니다.'),
            R.folded(R.table('내 그래프 — 기준 지도의 설비에서 시작하는 관계(시작 → 끝)', ['시작 id', '관계', '끝 id'], links,
                    note='기준 지도 표와 식별자 · 관계 방향을 견줍니다.')),
            R.folded(R.table('기준 지도 — 포털 지식 지도의 같은 길(시작 → 끝)', ['시작 id', '관계', '끝 id'],
                    [(name[r['시작']], f"{{r['관계']}}({{r['화면 이름']}})", name[r['끝']]) for r in ref['관계']], note=ref['설명']))] + browser()


STEPS = {steps}
'''

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
    """kind = design_integrated · design_practical · graph_integrated · graph_practical. names = 실전반 랩의 옛 단계 이름(STEPS 표를 채운다 — 새 프로젝트 구조는
    STEPS 앞까지만 쓴다, session2_project.actions_source). 통합반 랩은 단계 표를 두지 않는다 — 단계는 가이드 원고(session2_project_guides)가 갖는다."""
    s = {f's{i}': n for i, n in enumerate(names, 1)}
    if kind == 'design_integrated':
        return DESIGN_INTEGRATED.format(title=title)
    if kind == 'design_practical':
        import session2_answers as ANS
        return DESIGN_PRACTICAL.format(title=title, quote_point=ANS.QUOTE_POINT, **s)
    if kind == 'graph_integrated':
        return GRAPH.format(title=title, change=change, steps='[]', decide={'update': ['불용 결정 설비']})
    return GRAPH.format(title=title, change=change, steps=GRAPH_STEPS_PRACTICAL.format(**s), decide={'1': ['쓰는 사람에 따라 갈리는 답']})
