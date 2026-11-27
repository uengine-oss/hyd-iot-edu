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
    """대조 화면은 적은 글을 그대로 보이고, 같음 여부는 조각의 순서와 숫자 표기(35 = 35.0)를 떼고 견준다 — 그 사실은 대조 표 아래 SAME_NOTE로 밝힌다.
    「 / 」로 이은 묶음(한 공급사의 견적 여럿처럼 값 한 벌이 여럿인 답)은 묶음끼리 견준다 — 묶음의 차례는 떼지만, 값이 묶음을 넘어 섞이면 다르다."""
    bundles = lambda text: sorted(norm(numbers(b)) for b in str(text or '').split(' / '))
    return bundles(expected) == bundles(actual)


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
        if not re.search(r'[^\\s:]+:\\d+', r['근거']):
            raise R.Stop(f'결과/정한_것.csv:{{line}}(지점 「{{point}}」): 근거에 파일:줄이 없습니다 — 그렇게 고른 내 이유 뒤에, 정할 때 열어 본 원문 줄을 파일:줄 꼴로 함께 적습니다.')


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
import json
import model_tool as M

TITLE = {title!r}
KEY = ['질문', '물을_값', '항목']   # 기대 답 한 줄을 가리키는 열
# 이 랩의 구조 검사 화면은 내 스키마 표의 이름으로 말한다(클래스 · 시작 클래스 · 종료 클래스)
CHECKS = [('인스턴스마다 글자로 된 식별자가 있다', '문자열 id가 없는'), ('식별자가 겹치는 인스턴스가 없다', '중복 id'), ('인스턴스의 클래스가 스키마에 있다', '종류가 없는 노드|스키마에 없는 종류'),
          ('필수 속성이 빠지지 않았다', '필수 속성'), ('속성 값의 자료형과 허용 값이 스키마와 맞다', '이어야 함|허용 값'), ('스키마에 없는 속성이 들어가지 않았다', '정의되지 않은 속성'),
          ('관계의 양 끝 인스턴스가 실제로 있다', '없는 관계 끝점'), ('같은 관계가 두 번 들어가지 않았다', '중복 관계'),
          ('관계 이름과 시작 · 종료 클래스가 스키마와 맞다', '스키마에 없는 관계|시작 종류가 다름|끝 종류가 다름|관계 이름이 없습니다'),
          ('카디널리티를 넘는 연결이 없다', '카디널리티|cardinality'), ('「적어도 하나」로 정한 관계가 빠진 인스턴스가 없다', '적어도 하나'),
          ('제공 코드가 받은 그대로다', '제공 파일이'), ('결정 기록의 칸이 다 찼다', '정한_것.csv')]


def guarded(fn, *a):
    try:
        return fn(*a)
    except M.Blank as e:
        raise R.Blank(str(e))
    except M.Stop as e:
        raise R.Stop(str(e))


def in_my_words(text):
    """구조 검사기가 낸 글을 내 스키마 표의 이름으로 — 모델 파일의 영문 클래스 이름 앞에 내 클래스 이름을 붙이고(설비(Asset)), 검사기의 낱말을 표의 칸 이름으로 바꾼다."""
    for kind, label in M.LABEL.items():
        text = re.sub(r'(?<![A-Za-z_(])' + label + r'(?![A-Za-z_])', f'{{kind}}({{label}})', text)
    for old, new in (('시작 종류', '시작 클래스'), ('끝 종류', '종료 클래스'), ('스키마에 없는 종류', '스키마에 없는 클래스'), ('종류가 없는 노드', '클래스가 없는 인스턴스'),
                     ('어느 종류에서 어느 종류로', '어느 클래스에서 어느 클래스로'), ('끝이 적어도 하나', '적어도 하나')):
        text = text.replace(old, new)
    return text


def expected_lines():
    """기대 답 표 데이터 행의 편집기 줄 번호(expected_rows가 돌려주는 행과 같은 차례)."""
    text, _ = R.read_text(HERE / '결과/기대_답.csv')
    return [i for i, x in enumerate(text.splitlines(), 1) if x.strip() and not x.lstrip().startswith('#')][1:]


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
        out.append(R.graph('출발 그림(자료/관계그림.json) — 설비에서 구성 요소, 센서로 이어지는 줄기', [R.node(n['id'], (n.get('labels') or ['대상'])[0], text=n.get('caption') or n['id'], props=n.get('properties') or {{}},
                                  at=(n['position']['x'], n['position']['y']) if isinstance(n.get('position'), dict) and 'x' in n['position'] and 'y' in n['position'] else None) for n in g.get('nodes', [])],
                           [R.edge(r['fromId'], r['toId'], r.get('type', '')) for r in g.get('relationships', [])]))
        out.append(R.folded(R.table('출발 그림(자료/관계그림.json)의 연결 — 시작 → 끝', ['시작', '관계', '끝'],
                                    [(cap.get(r['fromId'], r['fromId']), r.get('type', ''), cap.get(r['toId'], r['toId'])) for r in g.get('relationships', [])])))
    return out


FORM_MORE = {{}}      # 질문 번호 → 그 질문 줄의 꼴을 보는 함수(줄을 더 받는 랩이 얹는다)


def expected_form(rows, lines):
    """기대 답 표의 줄마다 꼴(빈 틀 첫 줄에 적힌 칸 뜻)을 원자료에 대어 본다 — [(파일:줄, 질문, 어긋난 곳, 무엇을 어느 칸에)].
    값이 맞는지는 보지 않는다(그것은 모델을 만든 뒤 질문 대조가 본다). 꼴이 틀린 줄은 대조에서 까닭 없이 「실제 없음」이 되므로, 모델을 만들기 전에 여기서 짚는다."""
    src = lambda name: R.read_table(HERE / '자료' / name)
    assets = set(r['설비코드'] for r in src('설비_대장.csv'))
    places = set(r['구성요소'] for r in src('구성요소_목록.csv')) | set(x for x in [getattr(M, 'ASSET_WIDE', '')] if x)
    sensors = set(f"{{r['설비코드']}}:{{r['태그']}}" for r in src('센서_목록.csv'))
    parts = set(r['품번'] for r in src('예비품_목록.csv'))
    try:
        split = '실물' in M.read_classes()
    except (M.Blank, M.Stop):
        split = False
    ask = re.compile(r'\\s*(.+?)\\.(\\S+?)\\s*(' + '|'.join(re.escape(f) for f in M.FILTERS) + r')\\s*(.*?)\\s*')
    out = []
    for line, r in zip(lines, rows):
        q, asked, item, answer = (str(r.get(c) or '').strip() for c in ('질문', '물을_값', '항목', '기대_답'))
        pieces = [x.strip() for x in answer.split('·') if x.strip()]
        say = lambda what, fix: out.append((f'결과/기대_답.csv:{{line}}', q, what, fix))
        if q == '1':
            base = item.removesuffix('실물').strip()
            if asked not in assets:
                say(M.josa(f'물을_값 「{{asked}}」', '은/는') + ' 설비 대장에 적힌 설비 코드가 아닙니다', '물을_값 칸에는 설비 코드를 원자료에 적힌 그대로 적습니다')
            elif not item or base not in places:
                say(M.josa(f'항목 「{{item}}」', '은/는') + ' 구성 요소 목록에 적힌 구성 요소 이름이 아닙니다', '항목 칸에는 그 설비의 구성 요소 이름을 원자료에 적힌 그대로 적습니다(그 자리에 달린 장치를 묻는 줄이면 「구성 요소 이름 실물」)')
            elif split and item.endswith('실물') and answer != '없음' and not all(p.endswith(('(지금)', '(지난)')) for p in pieces):
                say('실물을 클래스로 따로 둔 스키마인데 기대_답의 일련번호에 (지금) · (지난)이 붙지 않았습니다', '기대_답 칸에는 「일련번호(지금)」 · 「일련번호(지난)」 꼴로 적습니다')
        elif q == '2':
            if asked in sensors or asked in assets:
                say(f'물을_값 「{{asked}}」에 물리량 이름이 아니라 센서나 설비가 적혀 있습니다', '물을_값 칸에는 물리량 이름을 적고, 센서 하나의 값을 보는 줄이면 그 센서를 항목 칸에 설비코드:태그로 적습니다')
            elif item and item not in sensors:
                say(M.josa(f'항목 「{{item}}」', '은/는') + ' 센서 목록의 설비코드:태그가 아닙니다', '그 물리량을 재는 센서 목록을 보는 줄이면 항목 칸을 비우고, 센서 하나의 값을 보는 줄이면 항목 칸에 설비코드:태그를 적습니다')
            elif item and len(pieces) != 4:
                say(f'센서 값 줄인데 기대_답이 {{len(pieces)}}조각입니다', '기대_답 칸에는 「단위 · 정상값 · 한계 · 한계구분」 네 값을 이 차례로 적습니다(값이 없는 칸은 「없음」)')
            elif not item and answer != '없음' and not all(p in sensors for p in pieces):
                say('센서 목록 줄인데 기대_답에 설비코드:태그가 아닌 값이 있습니다 — ' + ' · '.join([p for p in pieces if p not in sensors][:3]), '기대_답 칸에는 그 물리량을 재는 센서를 설비코드:태그로 「 · 」로 이어 적습니다')
        elif q == '3':
            if item and item not in parts:
                say(M.josa(f'항목 「{{item}}」', '은/는') + ' 예비품 목록에 적힌 사내 품번이 아닙니다', '항목 칸에는 물은 표기가 가리키는 사내 품번을 적습니다(원자료에 없는 품번으로 물은 줄이면 비웁니다)')
            elif answer not in ('없음', '쓰는 설비 없음') and not all(p in assets for p in pieces):
                say('기대_답에 설비 코드가 아닌 값이 있습니다 — ' + ' · '.join([p for p in pieces if p not in assets][:3]), '기대_답 칸에는 그 부품을 쓰는 설비 코드들을 「 · 」로 이어 적습니다(원자료에 없는 품번은 「없음」)')
        elif q == '4':
            conds = [ask.fullmatch(x) for x in asked.split('&')]
            if not all(m and m.group(1) in M.LABEL and (m.group(3) in ('=', '>', '<')) == bool(m.group(4)) for m in conds) or len(set(m.group(1) for m in conds)) != 1:
                say(M.josa(f'물을_값 「{{asked}}」', '은/는') + ' 「클래스.속성 조건」 꼴이 아닙니다', M.ASK_FORM)
            elif not item:
                say('항목이 비었습니다', '항목 칸에는 답으로 볼 그 클래스의 속성 이름 하나를 적습니다')
        elif q in FORM_MORE:
            FORM_MORE[q](asked, item, answer, pieces, say, assets, parts)
        else:
            say(M.josa(f'질문 「{{q}}」', '은/는') + ' 이 표가 받는 질문 번호가 아닙니다', '질문 칸에는 ' + ' · '.join(['1', '2', '3', '4'] + sorted(FORM_MORE)) + ' 가운데 하나를 적습니다')
    return out


def form_cards(off):
    return R.cards(f'꼴이 맞지 않는 기대 답 줄 {{len(off)}}곳', [dict(title=where, badge='질문 ' + q, state='bad', icon='warn', lines=[('어긋난 곳', what, '글'), ('이렇게 적습니다', fix, '글')]) for where, q, what, fix in off[:24]], wide=True,
                   note='값이 맞는지가 아니라 무엇을 어느 칸에 적었는지만 본 것입니다. 꼴이 틀린 줄은 모델이 내는 답과 짝이 맞지 않아 질문 대조에서 「실제 없음」이 됩니다. '
                        '이 카드를 Codex에게 보여 주고, 기대 답의 값은 그대로 둔 채 칸만 맞게 고쳐 달라고 합니다. 칸마다의 뜻은 결과/기대_답.csv 첫 줄에 있습니다.')


EVIDENCE = re.compile(r'([^\\s:·,「」()]+\\.(?:csv|md))\\s*:\\s*(\\d+(?:\\s*[~∼-]\\s*\\d+)?(?:\\s*[·,]\\s*\\d+(?:\\s*[~∼-]\\s*\\d+)?)*)')      # 근거 칸의 「파일:줄」 — 줄은 「2」 · 「2 · 4」 · 「2~21」
EVIDENCE_MORE = {{}}      # 질문 번호 → 그 질문의 근거 줄에 적혀 있어야 하는 것을 보는 함수를 만드는 함수(줄을 더 받는 랩이 얹는다)


def part_words(part):
    """그 사내 품번을 원자료가 적는 글들 — 사내 품번, 품번 교차표의 다른 표기, 예비품 목록의 품명."""
    src = lambda name: R.read_table(HERE / '자료' / name)
    return set([part] + [r['다른표기'] for r in src('품번_교차표.csv') if r['사내품번'] == part] + [r['품명'] for r in src('예비품_목록.csv') if r['품번'] == part]) - set([''])


def evidence_off(rows, lines):
    """기대 답 표의 근거 칸에 적은 파일:줄을 원자료에 대어 본다 — [(기대 답 파일:줄, 질문, 근거로 적은 줄, 어긋난 곳)].
    보는 것은 그 줄이 있는지와, 그 줄에 물은 대상이나 답의 값이 적혀 있는지다(질문 1 = 그 설비의 줄이고 센서 표의 줄이면 답에 적은 태그의 줄, 질문 2 = 답에 적은 센서의 줄, 질문 3 = 그 부품을 적은 줄).
    센서 하나의 값을 보는 질문 2 줄은 센서 표에서 댄 줄 가운데 그 센서의 줄이 하나라도 있으면 된다(기준 단위의 근거로 같은 물리량의 다른 센서 줄을 함께 대는 것은 맞는 근거다).
    질문 3은 구성 요소 목록의 줄이면 그 부품이 적혀 있어야 하고, 다른 표의 줄은 답에 적은 설비의 줄이어도 된다.
    줄을 범위(2~21)로 적은 근거는 그 범위에 그런 줄이 하나라도 있으면 된다. 줄 번호 없이 파일 이름만 적은 근거, 표가 아닌 글(md)의 내용, 질문 4의 값은 보지 않는다. 답의 값이 맞는지는 질문 대조가 본다."""
    files = dict((p.name, p) for p in (HERE / '자료').iterdir() if p.is_file())
    tables, lengths = {{}}, {{}}

    def cells(name, n):      # 그 줄의 칸들(자료가 적힌 줄이 아니면 None)
        if name not in tables:
            tables[name] = dict((at, list(row.values())) for at, row in M.table(files[name]))
        return tables[name].get(n)

    def length(name):
        if name not in lengths:
            lengths[name] = len(R.read_text(files[name])[0].splitlines())
        return lengths[name]
    sensor_table, place_table = M.TABLE['센서'], M.TABLE['구성 요소']
    out = []
    for line, r in zip(lines, rows):
        q, asked, item, answer = (str(r.get(c) or '').strip() for c in ('질문', '물을_값', '항목', '기대_답'))
        pieces = [re.sub(r'\\((지금|지난)\\)$', '', x.strip()) for x in answer.split('·') if x.strip()]
        if q == '1':
            wrong = lambda name, c, asked=asked, pieces=pieces, none=answer == '없음': (
                f'설비 「{{asked}}」의 줄이 아닙니다' if asked not in c else
                '기대_답에 적은 값(' + ' · '.join(pieces[:6]) + ')이 적힌 줄이 아닙니다' if name == sensor_table and not none and not set(pieces) & set(c) else None)
        elif q == '2':
            want = [x.split(':', 1) for x in ([item] if item else pieces) if ':' in x]
            wrong = lambda name, c, want=want, item=item: (
                (f'센서 「{{item}}」의 줄이 아닙니다' if item else '기대_답에 적은 센서의 줄이 아닙니다') if name == sensor_table and want and not any(code in c and tag in c for code, tag in want) else None)
        elif q == '3':
            words = (part_words(item) | set([asked])) if item else set()
            wrong = lambda name, c, words=words, asked=asked, pieces=pieces: (
                M.josa(f'물은 표기 「{{asked}}」', '이나/나') + ' 그 부품의 사내 품번 · 다른 표기 · 품명이 적힌 줄이 아닙니다'
                if words and not any(w in x for w in words for x in c) and (name == place_table or not set(pieces) & set(c)) else None)
        elif q in EVIDENCE_MORE:
            wrong = EVIDENCE_MORE[q](asked, item, answer, pieces)
        else:
            wrong = lambda name, c: None
        together = q == '2' and bool(item)      # 센서 하나의 값을 보는 줄 — 댄 센서 줄 가운데 하나만 그 센서의 줄이면 된다
        held = []
        for m in EVIDENCE.finditer(str(r.get('근거') or '')):
            name = m.group(1).replace('\\\\', '/').rsplit('/', 1)[-1]
            say = lambda at, what, line=line, q=q: out.append((f'결과/기대_답.csv:{{line}}', q, at, what))
            if name not in files:
                say(f'{{m.group(1)}}:{{m.group(2)}}', M.josa(f'「{{name}}」', '은/는') + ' 자료/ 폴더에 없는 파일입니다')
                continue
            for one in re.split(r'\\s*[·,]\\s*', m.group(2)):
                ends = [int(x) for x in re.split(r'\\s*[~∼-]\\s*', one.strip())]
                span = range(ends[0], ends[-1] + 1)
                at = f'자료/{{name}}:{{one.strip()}}'
                if not span or span[0] < 1 or span[-1] > length(name):
                    say(at, f'이 파일은 {{length(name)}}줄까지입니다')
                    continue
                if not name.endswith('.csv'):
                    continue
                found = [c for c in (cells(name, n) for n in span) if c is not None]
                if not found:
                    say(at, '자료가 적힌 줄이 아닙니다(열 이름 줄이거나 빈 줄)')
                    continue
                told = [wrong(name, c) for c in found]
                if together and name == sensor_table:
                    held.append((at, all(told) and told[0]))
                elif all(told):
                    written = ' · '.join(x for x in found[0] if x)
                    say(at + (' — 적힌 것: ' + written[:80] + ('…' if len(written) > 80 else '') if len(found) == 1 else ''),
                        told[0] if len(found) == 1 else '이 범위에는 그런 줄이 없습니다 — ' + told[0])
        if held and all(said for _, said in held):
            out.append((f'결과/기대_답.csv:{{line}}', q, ' · '.join(at for at, _ in held), '센서 표에서 댄 줄 가운데 ' + held[0][1].replace('의 줄이 아닙니다', '의 줄이 없습니다')))
    return out


def evidence_cards(off):
    return R.cards(f'근거로 적은 줄이 맞지 않는 기대 답 줄 {{len(set(x[0] for x in off))}}곳', [dict(title=where, badge='질문 ' + q, state='warn', icon='warn', lines=[('근거로 적은 줄', at, '글'), ('어긋난 곳', what, '글')]) for where, q, at, what in off[:24]], wide=True,
                   note='답의 값이 맞는지가 아니라, 근거 칸에 적은 파일:줄에 물은 대상이나 답의 값이 적혀 있는지만 본 것입니다. AI는 줄 번호를 틀리게 대곤 합니다. '
                        '그 줄을 직접 열어 보고, Codex에게 맞는 줄을 다시 찾아 근거 칸만 고쳐 달라고 합니다. 줄 번호를 범위(2~21)로 적은 근거는 그 범위에 맞는 줄이 하나라도 있으면 걸지 않습니다.')


def expected(previous):
    rows = expected_rows(['질문', '물을_값', '기대_답', '근거'], KEY)
    off = expected_form(rows, expected_lines())
    cited = evidence_off(rows, expected_lines())
    return [R.verdict('bad', f'기대 답 {{len(rows)}}줄 가운데 꼴이 맞지 않는 줄 {{len(off)}}곳', '아래 카드에서 무엇을 어느 칸에 적어야 하는지 보고 그 줄을 고칩니다.') if off else
            R.verdict('warn', f'기대 답 {{len(rows)}}줄 가운데 근거로 적은 줄이 맞지 않는 줄 {{len(set(x[0] for x in cited))}}곳', '아래 카드의 줄을 원자료에서 직접 열어 보고 근거 칸을 고칩니다.') if cited else
            R.verdict('info', f'기대 답 {{len(rows)}}줄을 정했습니다', '모델을 만든 뒤 이 답과 견줍니다.')] + ([form_cards(off)] if off else []) + ([evidence_cards(cited)] if cited else []) + [
            question_cards(rows, lambda r: r['물을_값'] + (' → ' + r['항목'] if r.get('항목') else '')),
            R.folded(R.table('내가 정한 기대 답', ['질문', '물을_값', '항목', '기대_답', '근거'], rows))]


def finding_cards(findings):
    """원자료 행을 내 스키마 표에 대어 보아 어긋난 곳 — 정한 줄(스키마 표의 파일:줄)마다 카드 하나, 걸린 원자료 줄을 함께."""
    by = {{}}
    for f in findings:
        by.setdefault((f['종류'], f['표']), []).append(f)
    return R.cards('원자료가 내 스키마 표와 어긋나는 곳', [dict(title=kind, badge=f'{{len(fs)}}곳', state='bad', icon='warn', text=fs[0]['글'],
                   lines=[('정한 곳', at), ('걸린 원자료 줄', ' · '.join(f['원자료'].replace('자료/', '') for f in fs[:8]) + (f' … 외 {{len(fs) - 8}}곳' if len(fs) > 8 else ''))]) for (kind, at), fs in by.items()],
                   note='원자료가 틀린 것이 아니면 스키마 표의 그 줄(필수 · 자료형 · 적어도 하나)을 원자료에 맞게 고칩니다. 근거는 걸린 원자료 줄과 현장 메모에서 찾습니다.', wide=True)


def classes(previous):
    cls, prev, written = guarded(M.classes_view)
    where = lambda v, lines: ', '.join(f"{{v['파일']}}:{{n}}" for n in lines[:6]) + (f' … 외 {{len(lines) - 6}}행' if len(lines) > 6 else '')
    clash = [(k, i, where(v, lines)) for k, v in prev.items() for i, lines in v['겹침'].items()]
    blank = [(k, len(v['빈칸']), where(v, v['빈칸'])) for k, v in prev.items() if v['빈칸']]
    wrong = set(k for k, _, _ in clash) | set(k for k, _, _ in blank)
    items = [dict(title=k, kind=k, state='bad' if k in wrong else '', badge=f"{{prev[k]['행']}}행 → 식별자 {{prev[k]['개수']}}개" if k in prev else '센서 행을 내 규칙으로 묶어 만듦',
                  lines=[('의미', c['의미']), ('식별자 만드는 법', c['id'])]) for k, c in cls.items()]
    out = [R.verdict('bad', f'식별자 틀에 쓴 칸이 빈 원자료 행이 있습니다 — {{sum(n for _, n, _ in blank)}}행', '그 칸이 모든 행에 적혀 있는지 원자료에서 봅니다.') if blank else
           R.verdict('warn', f'식별자가 겹치는 원자료 행 {{len(clash)}}곳', '겹친 식별자 하나는 인스턴스 하나가 됩니다 — 같은 대상인지 그 원자료 줄로 봅니다.') if clash else
           R.verdict('ok', '식별자가 겹치는 원자료 행이 없습니다', f'클래스 {{len(cls)}}개'),
           R.cards('내가 정한 클래스 — 의미와 식별자', items, note='오른쪽 수 = 그 클래스의 원자료 행 수와, 내 식별자 틀로 지었을 때 서로 다른 식별자 수. 두 수가 다르면 식별자가 겹친 행이 있습니다.', wide=True)]
    if blank:
        out.append(R.cards('식별자 틀에 쓴 칸이 빈 행', [dict(title=k, kind=k, badge=f'{{n}}행', state='bad', icon='warn', lines=[('빈 원자료 행', rows)]) for k, n, rows in blank],
                           note='빈 값으로 지은 식별자는 서로 겹칩니다. 그 클래스의 모든 행에 값이 있는 칸으로 짓습니다.'))
    if clash:
        out.append(R.cards('식별자가 겹친 곳', [dict(title=i, badge=k, state='bad', icon='warn', kind=k, lines=[('겹친 원자료 행', rows)]) for k, i, rows in clash]))
    out.append(R.cards('센서 목록의 「재는것」 칸에 적힌 이름', [dict(title=f'{{len(written)}}가지', kind='물리량', text=' · '.join(f'{{name}} {{n}}행' for name, n in written))],
                       note='「재는것」을 센서의 속성으로만 두면, 같은 것을 재는 센서를 모을 때 글자가 같은 행끼리만 모여 이만큼의 묶음이 됩니다. '
                            '물리량을 클래스로 따로 두면 다르게 적힌 이름도 한 물리량으로 이을 수 있고, 어느 이름을 같은 물리량으로 볼지는 뒤에서 내 규칙으로 정합니다.', wide=True))
    out.append(R.folded(R.table('클래스와 식별자(결과/클래스.csv)', ['클래스', '의미', 'ID_만드는_법', '원자료 행', '서로 다른 식별자'],
                                [(k, c['의미'], c['id'], prev[k]['행'] if k in prev else '', prev[k]['개수'] if k in prev else '') for k, c in cls.items()])))
    return out


def properties_before():
    """속성 표를 적기 전 — 클래스마다 쓸 수 있는 칸과 값이 빈 원자료 줄(제공 코드가 센다). 필수로 두면 걸리는 줄 수를 AI에게 다시 세게 하지 않는다."""
    cls, cols = guarded(M.columns_view)
    lines = lambda c: ', '.join(f"{{c['파일']}}:{{n}}" for n in c['빈칸'][:8]) + (f" … 외 {{len(c['빈칸']) - 8}}줄" if len(c['빈칸']) > 8 else '')
    some = [c for c in cols if c['빈칸']]
    return [R.verdict('info', '속성 표를 아직 적지 않았습니다 — 클래스마다 쓸 수 있는 칸과 값이 빈 줄을 먼저 봅니다',
                      f'값이 빈 줄이 있는 칸 {{len(some)}}개. 어느 칸을 속성으로 담고 필수로 둘지는 내가 정합니다.'),
            R.table('클래스마다 쓸 수 있는 칸 — 값이 빈 원자료 줄', ['클래스', '원자료 칸', '원자료 줄', '빈 줄', '빈 줄의 자리', '수로 읽히는 값', '날짜로 읽히는 값', '첫 값'],
                    [(c['클래스'], c['칸'], '제공 코드가 채움' if c['행'] is None else c['행'], '' if c['행'] is None else len(c['빈칸']), lines(c),
                      '' if c['행'] is None else c['수'], '' if c['행'] is None else c['날짜'], c['예']) for c in cols],
                    note='원자료 줄을 센 수입니다(모델에 담지 않기로 결과/행_처리.csv에 적은 줄은 뺌). 어떤 칸을 필수로 두면 그 칸의 「빈 줄」이 넣기 전 검증에서 걸리고, 자료형을 수나 날짜로 두면 그렇게 읽히지 않는 값이 걸립니다. '
                         '빈 줄이 왜 비었는지는 그 줄을 열어 보거나 Codex에게 원자료 줄로 물어봅니다. 속성 표를 적은 뒤 이 명령을 다시 실행하면 내가 정한 속성을 원자료에 대어 본 화면이 나옵니다.')]


def properties(previous):
    cls, props, rows = guarded(M.properties_view)
    if not rows:
        return properties_before()
    lines = lambda r, ns: ', '.join(f"{{r['파일']}}:{{n}}" for n in ns[:6]) + (f' … 외 {{len(ns) - 6}}행' if len(ns) > 6 else '')
    bad = [r for r in rows if (r['필수'] and r['빈칸']) or r['안맞음']]
    cards = []
    for k in cls:
        mine = [r for r in rows if r['클래스'] == k]
        cards.append(dict(title=k, kind=k, badge=f'속성 {{len(mine)}}개', state='bad' if any(r in bad for r in mine) else '',
                          lines=[(r['속성'] + (' (필수)' if r['필수'] else ''), f"{{r['칸']}} 칸 · {{r['자료형']}}" + (f" · {{r['단위']}}" if r['단위'] else '') + (f" — {{r['예']}}" if r['예'] else '')) for r in mine]))
    out = [R.verdict('warn', f'원자료와 어긋나는 속성 {{len(bad)}}개', '필수로 정했는데 비어 있는 행이 있거나, 정한 자료형으로 읽을 수 없는 값이 있습니다.') if bad else
           R.verdict('ok', f'속성 {{len(rows)}}개가 원자료 행과 모두 맞습니다', '필수로 정한 속성은 모든 행에 값이 있고, 값은 정한 자료형으로 읽힙니다.'),
           R.cards('내가 정한 스키마 — 클래스마다 속성(왼쪽)과 그 속성에 들어갈 원자료의 첫 값(오른쪽 끝)', cards,
                   note='속성 이름 · 원자료 칸 · 자료형 · 필수는 스키마이고, 줄 끝의 값은 그 스키마대로 옮겨질 인스턴스 데이터의 한 예입니다.', wide=True)]
    if bad:
        out.append(R.cards('원자료와 어긋나는 속성', [dict(title=f"{{r['클래스']}}의 {{r['속성']}}", kind=r['클래스'], state='bad', icon='warn',
                           badge=' · '.join(x for x in [f"필수인데 빈 행 {{len(r['빈칸'])}}" if r['필수'] and r['빈칸'] else '', f"{{r['자료형']}}로 읽을 수 없는 값 {{len(r['안맞음'])}}" if r['안맞음'] else ''] if x),
                           lines=[('정한 곳', f"결과/속성.csv:{{r['줄']}} — {{r['칸']}} 칸 · {{r['자료형']}} · 필수 {{'예' if r['필수'] else '아니오'}}")]
                           + ([('빈 원자료 행', lines(r, r['빈칸']))] if r['필수'] and r['빈칸'] else [])
                           + ([('읽을 수 없는 값', ', '.join(f"{{r['파일']}}:{{n}} 「{{v}}」" for n, v in r['안맞음'][:4]))] if r['안맞음'] else [])) for r in bad],
                           note='원자료가 틀린 것이 아니면 속성 표의 그 줄을 원자료에 맞게 고칩니다(비어도 되는 값이면 필수를 아니오로).', wide=True))
    out.append(R.folded(R.table('속성마다 원자료에 채워진 행(결과/속성.csv)', ['클래스', '속성', '원자료 칸', '자료형', '필수', '단위', '원자료 행', '빈 행', '읽을 수 없는 값'],
                                [(r['클래스'], r['속성'], r['칸'], r['자료형'], '예' if r['필수'] else '아니오', r['단위'], '제공 코드가 채움' if r['행'] is None else r['행'],
                                  len(r['빈칸']), len(r['안맞음'])) for r in rows],
                                note='모델에 담지 않기로 결과/행_처리.csv에 적은 줄은 세지 않습니다 — 넣기 전 검증이 보는 줄과 같습니다.')))
    return out


def relations_before():
    """관계 표를 적기 전 — 클래스 짝마다 원자료 줄이 지금 이어진 개수와, 반대쪽이 하나도 없는 대상(제공 코드가 센다)."""
    facts = guarded(M.links_view)
    listed = lambda xs, unit: f'{{len(xs)}}{{unit}}' + (' — ' + ', '.join(xs[:6]) + (f' … 외 {{len(xs) - 6}}{{unit}}' if len(xs) > 6 else '') if xs else '')
    top = lambda pair: f'가장 많은 곳 {{pair[0]}}개' + (' — ' + ', '.join(pair[1][:6]) + (f' … 외 {{len(pair[1]) - 6}}곳도 같은 수' if len(pair[1]) > 6 else '') if pair[1] and pair[0] else '')
    items = [dict(title=f"{{f['앞']}} · {{f['뒤']}}", state='warn' if f['앞_없음'] or f['뒤_없음'] else '', lines=[
        (f"{{f['앞']}} 하나에 이어진 {{f['뒤']}}", top(f['앞_최대']), '글'), (f"{{f['뒤']}} 하나에 이어진 {{f['앞']}}", top(f['뒤_최대']), '글'),
        (f"{{M.josa(f['뒤'], '이/가')}} 하나도 없는 {{f['앞']}}", listed(f['앞_없음'], '곳')), (f"{{M.josa(f['앞'], '이/가')}} 하나도 없는 {{f['뒤']}}", listed(f['뒤_없음'], '곳'))]) for f in facts]
    return [R.verdict('info', '관계 표를 아직 적지 않았습니다 — 원자료 줄이 지금 어떻게 이어져 있는지 먼저 봅니다',
                      '카디널리티는 이어질 수 있는 개수라 지금 자료보다 넓게 정해도 됩니다. 화살표와 카디널리티, 적어도 하나는 내가 정합니다.'),
            R.cards('클래스 짝마다 지금 자료의 이어짐', items, wide=True,
                    note='원자료 줄을 그대로 센 수입니다(모델에 담지 않기로 결과/행_처리.csv에 적은 줄은 뺌). 어느 쪽을 「적어도 하나」로 두면 그쪽의 「하나도 없는」 대상이 넣기 전 검증에서 걸립니다. '
                         '센서와 물리량 사이는 내 규칙(결과/quantity_rules.py)으로 센서를 묶은 뒤에 정해집니다. 관계 표를 적은 뒤 이 명령을 다시 실행하면 내가 정한 관계를 문장으로 읽은 화면이 나옵니다.')]


def relations(previous):
    if not guarded(M.need, M.OUT / '관계.csv', ['관계_이름']):
        return relations_before()
    cls, links, pairs = guarded(M.relations_view)
    many = lambda side: '많아야 하나' if side == '1' else '여럿'
    least_of = lambda start, end, least: ' · '.join(f'{{start}}마다 {{end}} 적어도 하나' if s == '시작' else f'{{end}}마다 {{start}} 적어도 하나' for s in least) or '없음(이 관계가 하나도 없는 인스턴스도 됨)'
    items = []
    for link, (name, start, end, card, line, least, reads) in links.items():
        a, b = card.split(':')
        x, y = pairs.get(link, ('', ''))
        if start != M.LINKS[link][0]:
            x, y = y, x
        items.append(dict(title=f'{{start}} → {{reads}} → {{end}}', badge=name, lines=[
            ('문장으로 읽기', f'{{start}} 「{{x}}」 → {{reads}} → {{end}} 「{{y}}」' if x else '원자료에 이 관계로 이을 줄이 없습니다'),
            ('카디널리티 ' + card, f'{{start}} 하나에 {{end}} {{many(b)}}, {{end}} 하나에 {{start}} {{many(a)}}'),
            ('적어도 하나', least_of(start, end, least)),
            ('정한 곳', f'결과/관계.csv:{{line}}')]))
    return [R.verdict('info', f'관계 {{len(links)}}개를 정했습니다', '줄마다 「문장으로 읽기」가 말이 되는지 봅니다. 주어와 대상이 뒤바뀐 말이면 그 줄의 시작과 종료를 바꿉니다.'),
            R.graph('내가 설계한 클래스와 관계', [R.node(k, k, sub='식별자 ' + c['id']) for k, c in cls.items()], [R.edge(v[1], v[2], f'{{v[6]}} · {{v[3]}}') for v in links.values()],
                    note='상자 = 클래스, 화살표 = 관계(시작 클래스 → 종료 클래스), 화살표의 글 = 읽는 말 · 카디널리티.'),
            R.cards('관계마다 내가 정한 것 — 문장으로 읽기', items, wide=True,
                    note='「문장으로 읽기」는 원자료의 실제 한 쌍을 내가 그은 화살표대로 읽은 것입니다. 화살표가 나가는 쪽이 문장의 주어입니다. '
                         '카디널리티는 이어질 수 있는 개수이고, 적어도 하나는 빠지면 안 되는 연결입니다. 둘 다 모델을 만들 때 원자료의 실제 연결에 대어 봅니다.'),
            R.folded(R.table('관계(결과/관계.csv)', ['관계 이름', '읽는 말', '시작 → 종료', '카디널리티', '적어도 하나'],
                             [(v[0], v[6], f'{{v[1]}} → {{v[2]}}', v[3], least_of(v[1], v[2], v[5])) for v in links.values()]))]


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
                           note='일련번호가 적힌 구성 요소 행마다 실물 하나입니다. 지난 실물은 결과/행_처리.csv의 「지난 실물」 행이고, 이 모델에서 그 실물의 자리와 이력을 물을 수 있습니다.')))
    else:
        out.append(R.note('실물을 따로 두지 않았습니다. 결과/행_처리.csv에서 뺀 행의 실물(철거된 장치)은 이 모델에서 물을 수 없습니다.'))
    if info['unused']:
        out.append(R.table('결과/행_처리.csv에 적었지만 쓰이지 않은 행', ['파일', '행'], info['unused']))
    return out


def sensors(previous):
    info, _ = guarded(M.build, '센서')
    groups, at = {{}}, {{}}
    for sid, code, tag, q, line, what in info['센서']:
        groups.setdefault(q, []).append(f'{{code}}:{{tag}}')
        at[f'{{code}}:{{tag}}'] = (line, what)
    base = {{q: unit for q, _, unit in info['단위']}}
    alone = [(v[0], k, *at[v[0]]) for k, v in sorted(groups.items()) if len(v) == 1]
    keep = info['단위_담는_법'] == '적힌 그대로'
    mixed = [r for r in info['단위'] if ' · ' in r[1]]
    out = [R.verdict('info', f'센서 {{len(info["센서"])}}개가 물리량 {{len(groups)}}개로 묶였습니다', f'내 규칙이 다른 센서와 묶지 않은 센서 {{len(alone)}}개 — 정말 혼자 재는 것인지 봅니다.' if alone else '한 묶음이 물리량 하나입니다 — 내가 정한 범위대로 묶였는지 봅니다.'),
           R.gather('센서가 물리량으로 묶인 모습', ('센서(설비:태그)', '물리량 · 기준 단위'),
                    [dict(left=sorted(v), mid=dict(text=k, kind='물리량', sub=base[k])) for k, v in sorted(groups.items())],
                    note='왼쪽 센서들이 오른쪽 물리량 하나를 잽니다. 같은 물리량이라고 본 센서끼리만 한 줄에 모입니다.')]
    if alone:
        out.append(R.cards('내 규칙이 다른 센서와 묶지 않은 센서', [dict(title=s, kind='센서', badge='혼자인 묶음', state='warn', lines=[('붙인 물리량 이름', q), ('원자료의 재는것', what), ('원자료 행', line)]) for s, q, line, what in alone],
                           note='규칙이 이 센서를 어떤 센서와도 같은 물리량으로 보지 않았습니다. 혼자 재는 것이 맞는지, 규칙이 놓친 것인지는 그 원자료 줄과 같은 태그 · 같은 재는것의 다른 줄로 봅니다.'))
    if info['변환']:
        out.append(R.cards('단위를 기준 단위로 바꾼 센서', [dict(title=r[1], badge=f'{{r[3]}} → {{r[4]}}', kind='센서', lines=[('물리량', r[2]), ('원래 정상값 / 한계', r[5]), ('바꾼 정상값 / 한계', r[6]), ('원자료 행', r[0])]) for r in info['변환']]))
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
    usage = {{}}
    for _, code, cname, cell, pid, how in info['이은_부품']:
        usage.setdefault(pid, set()).add(code)
    lost, off = info['못_찾은_칸'], info['어긋남']
    return [R.verdict('warn', f'사내 품번을 찾지 못한 교체부품 칸 {{len(lost)}}개', '그 칸의 글을 품번 교차표와 견줍니다.') if lost else
            R.verdict('warn', f'모델 파일을 썼습니다 — 원자료가 내 스키마 표와 어긋나는 원자료 줄 {{len(off)}}곳', '아래 카드에서 정한 줄과 걸린 원자료 줄을 봅니다. 이대로면 넣기 전 검증에서 걸립니다.') if off else
            R.verdict('ok', f'교체부품 칸 {{len(info["이은_부품"])}}개를 부품 {{len(usage)}}개에 이었습니다', '여러 표기가 사내 품번 하나로 모였고, 모델 파일을 새로 썼습니다. 만든 연결은 모두 내가 정한 카디널리티 안에 있습니다.')] + (
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
            R.folded(R.table('관계마다 정한 카디널리티와 지금 자료에서 만든 연결', ['연결', '관계', '정한 카디널리티', '시작 하나에 이어진 종료(가장 많은 곳)', '종료 하나에 이어진 시작(가장 많은 곳)', '견줌'], info['카디널리티'],
                             note='카디널리티는 이어질 수 있는 개수를 정해 둔 것입니다. 지금 자료의 연결이 그보다 적어도 정한 범위 안이고, 「많아야 하나」로 정한 쪽에 둘 이상 이어지면 그 줄을 짚고 멈춥니다.')),
            R.note('결과/schema.json(스키마) · 결과/graph.json(인스턴스 데이터)을 새로 썼습니다.')]


def ask(previous):
    rows = expected_rows(['질문', '물을_값', '기대_답'], KEY)
    off = expected_form(rows, expected_lines())      # 꼴이 틀린 줄은 아래 대조에서 「실제 없음」이 된다 — 그 까닭을 먼저 짚는다
    cited = evidence_off(rows, expected_lines())     # 근거로 적은 줄은 답이 같아도 틀릴 수 있다 — 기대 답 화면을 다시 실행하지 않는 뒤 단계에서 더한 줄도 여기서 본다
    more = {{}}
    for line, r in zip(expected_lines(), rows):      # 질문 4(내가 더한 질문)는 답으로 볼 속성(항목)과 그 줄 번호까지 넘긴다
        if str(r['질문']).strip() == '4':
            more.setdefault(('4', r['물을_값']), []).append((r.get('항목', ''), line))
    got = guarded(M.answers, list(dict.fromkeys((str(r['질문']).strip(), r['물을_값']) for r in rows)), more)   # 같은 설비를 여러 줄에 적어도 한 번만 묻는다
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
    stuck = lambda g: str(g['답']).startswith(('답할 수 없음', '견줄 수 없음'))      # 스키마에 없어서 답하지 못한 줄은 그 까닭을 그대로 보인다
    keep = [r for r in got if (str(r['질문']), r['물을_값']) not in picked or r['항목'] in picked[(str(r['질문']), r['물을_값'])] or stuck(r)]
    schema = guarded(M.load_model)[0]
    if '다른이름' not in schema['classes'].get(M.LABEL['구성 요소'], {{}}).get('source', {{}}).values():      # 원자료 이름으로 적은 항목을 찾지 못한 까닭을 그 줄에 말한다
        found = {{(str(g['질문']), g['물을_값'], g['항목']) for g in keep}}
        asked = {{(str(g['질문']), g['물을_값']) for g in got if not stuck(g) and g['답'] != '없음'}}
        keep += [dict(r, 답='없음(모델에 이 이름의 구성 요소가 없음 — 구성 요소 클래스에 「다른이름」 칸을 담은 속성이 없어, 같은 모델의 설비끼리 하나로 맞춘 이름으로만 찾음)')
                 for r in rows if str(r['질문']).strip() == '1' and (str(r['질문']).strip(), r['물을_값']) in asked and (str(r['질문']).strip(), r['물을_값'], r.get('항목', '')) not in found]
    value = lambda r: str(r['질문']).strip() == '2' and bool(r.get('항목'))   # 질문 2 센서 값은 차례까지 같아야 한다
    exact = lambda e, a: [x.strip() for x in str(e).split('·')] == [x.strip() for x in str(a).split('·')]
    note = (f'기대 답에 적은 항목만 견줍니다(모델이 더 돌려준 {{len(got) - len(keep)}}줄은 표에 넣지 않음). '
            '물을 값과 답은 설비 코드 · 사내 품번처럼 현장이 쓰는 값이라 식별자와 속성 이름을 어떻게 지었든 같은 값으로 묻습니다. 질문 1의 항목은 원자료 이름으로 적어도 그 구성 요소의 다른 이름으로 찾습니다. '
            '「실제 없음」은 기대 답의 항목이 모델에 없는 것입니다(이름을 다르게 적었거나 모델이 그 인스턴스를 만들지 않음). 「기대 밖」은 모델이 더 돌려준 항목입니다. '
            '「답할 수 없음」은 그 답에 필요한 원자료 칸을 담은 속성이 내 스키마에 없다는 뜻이고, 「견줄 수 없음」은 그 속성의 자료형으로는 크기나 앞뒤를 견줄 수 없다는 뜻입니다. 관계는 화살표를 어느 쪽에서 그었든 따라가 찾습니다. '
            '모델의 답 「없음」은 물은 품번 · 표기 · 설비 · 물리량이 모델에 없다는 뜻이고, 「쓰는 설비 없음」은 부품은 모델에 있지만 그 부품에 이은 구성 요소가 없다는 뜻입니다. ' + SAME_NOTE)
    out = [R.compare('기대 답 ↔ 모델에 물은 답(질문 | 물을 값 | 항목)', '짝', [{{'짝': key(r), '답': r['기대_답']}} for r in rows if not value(r)],
                     [{{'짝': key(r), '답': r['답']}} for r in keep if not value(r)], ['답'], same=same, note=note)]
    if any(value(r) for r in rows):
        out.append(R.ordered(R.compare('질문 2 센서 값 — 단위 · 정상값 · 한계 · 한계구분 차례', '짝', [{{'짝': key(r), '답': r['기대_답']}} for r in rows if value(r)],
                             [{{'짝': key(r), '답': r['답']}} for r in keep if value(r)], ['답'], same=exact,
                             note='값은 차례까지 견줍니다. 값이 없는 칸 · 그 칸을 담은 속성이 없는 칸은 「없음」입니다. 속성 표에서 「기준 단위」로 정한 수는 바꾼 값이고, 「적힌 그대로」면 원자료에 적힌 값입니다.')))
    head = tally(out)
    if cited:      # 답이 모두 같아도 근거 줄이 틀린 것은 결론 줄이 말한다
        head = dict(head, state='warn' if head['state'] == 'ok' else head['state'],
                    detail=(head['detail'] + ' ' if head['detail'] else '') + f'근거로 적은 줄이 맞지 않는 기대 답 줄 {{len(set(x[0] for x in cited))}}곳 — 아래 카드의 줄을 원자료에서 직접 열어 봅니다.')
    return [head] + ([form_cards(off)] if off else []) + ([evidence_cards(cited)] if cited else []) + out


def check(previous):
    """넣기 전 검증 — 만든 모델의 구조 검사에 더해, 원자료 행을 지금의 내 스키마 표에 다시 대어 본다(모델 파일은 고치지 않는다)."""
    out = run_check()
    for b in out:      # 구조 검사기의 글을 내 스키마 표의 이름으로
        for k in ('text', 'detail', 'title'):
            if isinstance(b.get(k), str):
                b[k] = in_my_words(b[k])
        for item in b.get('items', []) if b['kind'] == 'cards' else []:
            item['lines'] = [in_my_words(x) if isinstance(x, str) else tuple(in_my_words(y) for y in x) for x in item.get('lines', [])]
    try:
        info, model = M.build('부품', write=False)
    except M.Stop as e:
        return out + [R.note('원자료를 내 스키마 표에 대어 보지 못했습니다 — ' + str(e))]
    made = [HERE / '결과/schema.json', HERE / '결과/graph.json']
    stale = all(p.is_file() for p in made) and [R.read_json(p) for p in made] != [json.loads(json.dumps(x, ensure_ascii=False)) for x in model]
    if info['어긋남']:
        out.insert(1 if out and out[0]['kind'] in ('verdict', 'error') else 0, finding_cards(info['어긋남']))
        if out[0]['kind'] == 'verdict':
            out[0] = R.verdict('bad', f'원자료가 내 스키마 표와 어긋나는 원자료 줄 {{len(info["어긋남"])}}곳', '아래 카드의 정한 줄과 걸린 원자료 줄을 보고 스키마 표를 고친 뒤 모델을 다시 만듭니다.')
        out.append(R.note('카드의 수는 걸린 원자료 줄 수이고, 구조 검사의 「구조 확인 필요 N건」은 만들어 둔 모델 파일에서 어긋난 조건을 센 수입니다(「적어도 하나」는 관계마다 한 건으로 셉니다).'))
    linked = {{r[k] for r in model[1]['rels'] for k in ('a', 'b')}}
    alone = [n for n in model[1]['nodes'] if n['props']['id'] not in linked]
    if alone:      # 검사 조건은 지켰어도 아무것과도 이어지지 않은 인스턴스는 사실로 보인다 — 담을 대상인지, 다른 줄과 같은 대상인지는 사람이 원자료로 가린다
        out.append(R.cards(f'관계가 하나도 이어지지 않은 인스턴스 {{len(alone)}}개', [dict(title=in_my_words(f"{{n['labels'][0]}} 「{{n['props']['id']}}」"), icon='open', state='warn', badge='이어진 관계 0',
                                                                       lines=[f'{{k}} — {{v}}' for k, v in n['props'].items() if k != 'id' and v not in ('', None)][:4]) for n in alone[:8]],
                           note='검사 조건은 지켰지만 다른 인스턴스와 이어진 관계가 하나도 없습니다. 원래 따로 있는 대상인지, 다른 줄과 같은 대상을 한 번 더 적은 것인지, 이을 관계가 빠졌는지를 원자료 줄로 확인합니다.'))
    if stale:
        out.append(R.note('스키마 표나 규칙을 고친 뒤 모델 파일을 다시 만들지 않았습니다 — python run.py parts를 실행한 뒤 다시 검증합니다.'))
    return out
'''


GRAPH = '''"""{title} — 결과 화면의 단계(START.md 「진행 단계」와 같은 번호 · 이름). 제공 파일 — 바꾸지 않는다."""
''' + COMMON + '''
import json
import lab_cypher as C

TITLE = {title!r}
CHANGE = {change!r}
DECIDE = {decide!r}   # 기능마다 쓰는 결정 지점(질문 번호 · update)
STUDENT = {student!r}   # 내 적재 쿼리 몫 — 종류(레이블) 이름이거나 두 클래스의 짝(그 짝을 잇는 관계 이름은 스키마에서 읽는다). 비어 있으면 적재 쿼리를 모두 내가 쓴다
RAW = {raw!r}   # 원자료 표의 줄을 적힌 그대로 받는 종류(열 이름 → 속성 짝을 내 쿼리가 정한다)


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
    rows = expected_rows(['질문', '물을_값', '볼_열', '기대_답', '근거'], ['질문', '물을_값', '볼_열'])
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
    """적재 실행 — 내 쿼리 몫이 정해진 랩은 내 쿼리와 제공 쿼리를 함께(노드 먼저, 관계 나중), 아니면 내 쿼리 파일만. ([(파일:줄, 넣을 것, 넘긴 행, 바뀐 것)], 쿼리가 없는 종류 · 관계)."""
    mine = HERE / '결과/load.cypher'
    if STUDENT:
        out, missing = db(C.load_files, mine, STUDENT, RAW)
    else:
        out, missing = [(mine, *x) for x in db(C.load_file, mine)], []
    return [(R.rel(path) + f':{{line}}', target, n, changed(res.get('stats', {{}}))) for path, line, target, n, res in out], missing


def seek_cards():
    """내 적재 쿼리마다 DB가 노드를 어떻게 찾는지 — 쿼리를 실행하지 않고 DB에 미리 물어본 답(EXPLAIN). 유일 제약을 건 식별자로 바로 찾는지, 노드를 하나씩 다 보는지."""
    items, said = [], []
    for line, target, s, rows, _ in db(C.load_plan, HERE / '결과/load.cypher', None, RAW):
        ops = db(C.seek_plan, s, rows)
        scan = [o for o in ops if 'Scan' in o]
        where = R.rel(HERE / '결과/load.cypher') + f':{{line}}'
        items.append(dict(title=target, badge='노드를 하나씩 다 봄' if scan else '식별자로 바로 찾음', state='warn' if scan else 'ok', icon='warn' if scan else 'ok', lines=[('쿼리', where)]))
        said.append((where, target, ' · '.join(ops) or '찾기 없음'))
    return [R.cards('내 쿼리가 노드를 찾는 법 — DB에 미리 물어본 답', items,
                    note='유일 제약을 건 식별자를 레이블과 함께 적으면 DB가 그 노드를 바로 찾습니다. 레이블 없이 식별자만 적으면 모든 종류의 노드를 하나씩 다 보고, 다른 종류에 같은 식별자가 있으면 그 노드에도 이어집니다.'),
            R.folded(R.table('DB가 답한 찾는 법 원문(EXPLAIN)', ['쿼리', '넣을 것', 'DB가 쓴 이름'], said,
                             note='DB가 쓴 이름에 Seek가 있으면 바로 찾는 것이고, Scan이 있으면 하나씩 다 보는 것입니다.'))] if items else []


def model_gap():
    """넣은 그래프의 값이 모델 파일과 같은가 — 개수가 같아도 식별자나 속성 값이 다르면 그 노드를 짚는다(원자료 표의 줄을 내 쿼리로 옮긴 종류에서 갈린다)."""
    _, model = C.model_graph()
    d = C.diff_graphs(model, db(C.export_graph))
    kinds = {{n['props'].get('id'): n['labels'][0] for n in model['nodes']}}
    back = {{}}
    for i, k, was, now in d['속성 바뀐 노드']:
        back.setdefault(i, []).append((k, f'모델 {{shown(was)}} → 랩 DB {{shown(now)}}'))
    cards = [dict(title=str(i), kind=kinds.get(i, ''), badge='값이 다름', state='bad', lines=ks) for i, ks in list(back.items())[:12]]
    cards += [dict(title=str(i), kind=kinds.get(i, ''), badge='모델에는 있는데 랩 DB에 없음', state='bad') for i in d['사라진 노드'][:12]]
    cards += [dict(title=str(i), badge='모델에 없는 노드가 생김', state='bad') for i in d['늘어난 노드'][:12]]
    return cards


TURNED_NOTE = ('막대는 관계를 이름별로만 세므로, 화살표를 거꾸로 넣어도 개수는 같습니다. 방향은 DB가 봐 주지 않습니다 — 내 관계 쿼리의 MERGE (a)-[…]->(b)에서 a와 b가 스키마의 시작 · 종료와 같은 쪽인지 봅니다. '
               '고친 뒤에는 python run.py reset으로 넣은 것을 비우고 다시 넣습니다.')
DATED_NOTE = ('모델 파일은 날짜를 「2026-10-15」 꼴의 글자로 적어 두지만, 스키마에서 자료형이 날짜인 속성은 랩 DB에 날짜로 들어가야 날짜끼리 앞뒤를 견줄 수 있습니다. '
              '원자료 표의 줄을 받는 내 쿼리는 그 열을 date(…)로 바꿔 넣습니다(빈 칸은 그대로 비워 둡니다). 고친 뒤에는 python run.py reset으로 넣은 것을 비우고 다시 넣습니다.')


def relation_cards(model, inside):
    """모델 파일과 다르게 이어진 관계 — 이름별 개수가 같아도 화살표가 거꾸로 들어갔거나 다른 노드에 이어진 것을 (관계 이름 · 시작 · 종료)마다 카드로 짚는다."""
    cards = []
    for g in C.relation_gap(model, inside):
        lines = [('모델 파일', f"{{g['시작']}} → {{g['끝']}} {{g['모델']}}개")]
        if g['거꾸로']:
            lines.append((f"랩 DB에는 거꾸로 {{len(g['거꾸로'])}}개", ' · '.join(f'{{b}} → {{a}}' for a, b in g['거꾸로'][:3]) + (' …' if len(g['거꾸로']) > 3 else '')))
        if g['빠짐']:
            lines.append((f"랩 DB에 없는 것 {{len(g['빠짐'])}}개", ' · '.join(f'{{a}} → {{b}}' for a, b in g['빠짐'][:3]) + (' …' if len(g['빠짐']) > 3 else '')))
        cards.append(dict(title=g['유형'], badge='화살표가 거꾸로' if g['거꾸로'] else '모델과 다른 노드에 이어짐', state='bad', icon='warn', lines=lines))
    return cards


def date_cards():
    """스키마에서 자료형이 날짜인 속성이 랩 DB에 날짜가 아닌 값으로 들어간 곳 — 내보낸 글로는 날짜와 글자가 똑같이 보여, 랩 DB에 자료형을 직접 물어본다."""
    by = {{}}
    for label, name, i, kind in db(C.date_gap):
        by.setdefault((label, name), []).append((i, kind))
    return [dict(title=f'{{label}}.{{name}}', kind=label, badge=f'{{len(hit)}}곳', state='bad', icon='warn',
                 lines=[('랩 DB에 들어간 자료형', ' · '.join(sorted({{k for _, k in hit}}))), ('그 노드', ' · '.join(str(i) for i, _ in hit[:5]) + (' …' if len(hit) > 5 else ''))]) for (label, name), hit in sorted(by.items())]


def query_pairs():
    """내 쿼리와 제공 쿼리를 나란히 — 같은 곳과 다른 곳을 읽어 보는 재료."""
    given = HERE / 'output/load_provided.cypher'
    if not given.is_file():
        return []
    one = lambda path, pick: [(t, s) for line, t, s, rows, node in db(C.load_plan, path, None, RAW) if pick(node)]
    mine = one(HERE / '결과/load.cypher', lambda node: True)
    theirs = one(given, lambda node: node)[:1] + one(given, lambda node: not node)[:1]
    items = [dict(title=t, badge='내 쿼리', kind=t, lines=[('쿼리', ' '.join(s.split()))]) for t, s in mine]
    items += [dict(title=t, badge='제공 쿼리', lines=[('쿼리', ' '.join(s.split()))]) for t, s in theirs]
    return [R.folded(R.cards('내 쿼리와 제공 쿼리 나란히', items, wide=True,
                             note='제공 쿼리는 모델 파일의 한 줄을 그대로 받아 넣습니다. 내 쿼리가 그것과 같은 곳과 다른 곳을 말해 봅니다. 제공 쿼리 전체는 ' + R.rel(given) + '에 있습니다.'))]


def load(previous):
    done, missing = load_once()
    _, model = graph_counts()
    have = db(C.counts)
    rows = [(k, v, have.get(k, 0), '같음' if v == have.get(k, 0) else '다름') for k, v in sorted(model.items())]
    differ = [r[0] for r in rows if r[3] == '다름']
    short = [r[0] for r in rows if r[0].startswith('관계 ') and r[2] < r[1]]
    inside = db(C.export_graph)
    leaving = set(r['a'] for r in inside['rels'])      # 그림의 출발점은 나가는 관계가 있는 노드에서 고른다 — 아무것과도 이어지지 않은 노드에서 시작하면 그릴 것이 없다
    roots = sorted(leaving - set(r['b'] for r in inside['rels']), key=str) or sorted(leaving, key=str)
    gap = model_gap() if STUDENT else []
    turned = relation_cards(C.model_graph()[1], inside)
    dated = date_cards()
    return [R.verdict('bad', f'모델 파일과 랩 DB의 개수가 다른 항목 {{len(differ)}}개', ' · '.join(differ[:6]) + (' — 쿼리가 없는 종류 · 관계: ' + ' · '.join(missing) if missing else '')) if differ else
            R.verdict('bad', f'개수는 같지만 모델 파일과 다르게 이어진 관계가 있습니다 — {{" · ".join(c["title"] for c in turned)}}', '아래 카드에서 화살표가 어느 쪽으로 들어갔는지 보고, 내 관계 쿼리의 시작과 종료가 스키마와 같은지 봅니다.') if turned else
            R.verdict('bad', f'개수는 같지만 모델 파일과 값이 다른 노드가 있습니다 — {{len(gap)}}곳', '아래 카드에서 어느 속성이 다른지 보고, 내 쿼리가 원자료의 어느 열을 어느 속성에 넣었는지 봅니다.') if gap else
            R.verdict('bad', f'스키마는 날짜인데 랩 DB에 글자로 들어간 값이 있습니다 — {{" · ".join(c["title"] for c in dated)}}', '글자로 들어간 날짜는 날짜와 앞뒤를 견주는 쿼리에서 조용히 빠집니다. 아래 카드의 속성을 넣는 쿼리를 봅니다.') if dated else
            R.verdict('ok', f'모델 파일과 랩 DB의 개수가 같습니다 — 노드 {{have.get("노드", 0)}}개 · 관계 {{have.get("관계", 0)}}개', '모델의 종류는 레이블이, 인스턴스는 노드가 됐습니다.' + (' 값과 관계의 방향도 모델 파일과 같습니다.' if STUDENT else '')),
            R.count_bars('모델 파일 ↔ 랩 DB 개수', ('모델 파일', '랩 DB'), model, have)] + (
            [R.cards('모델 파일과 다르게 이어진 관계', turned, wide=True, note=TURNED_NOTE)] if turned else []) + (
            [R.cards('스키마는 날짜인데 랩 DB에 글자로 들어간 값', dated, wide=True, note=DATED_NOTE)] if dated else []) + (
            [R.cards('모델 파일과 값이 다른 노드', gap, wide=True,
                     note='모델 파일은 스키마대로 옮긴 인스턴스 데이터입니다. 원자료 표의 줄을 내 쿼리로 넣은 종류는 식별자로 쓴 열과 열 → 속성 짝이 스키마와 같아야 모델 파일과 같은 노드가 됩니다. 고친 뒤에는 python run.py reset으로 넣은 것을 비우고 다시 넣습니다.')] if gap else []) + (
            [R.cards('모델보다 적게 들어간 관계', [dict(title=k, badge=f'모델 {{v}}개 → 랩 DB {{h}}개', state='bad', icon='warn') for k, v, h, _ in rows if k in short],
                     note='관계는 양 끝 노드를 찾았을 때만 만들어집니다. 끝 노드를 찾지 못한 줄은 오류 없이 빠지므로, 넣은 뒤에는 개수를 모델과 견줍니다. 끝 노드를 넣는 쿼리가 있는지, 관계 쿼리가 끝 노드를 무엇으로 찾는지 봅니다.')] if short else []) + seek_cards() + (
            [R.around_figure(f'랩 DB에 들어간 그래프의 한 부분 — 「{{roots[0]}}」에서 두 걸음', inside, roots[0])] if roots else []) + (query_pairs() if STUDENT else []) + [
            R.folded(R.table('적재 문장마다 넘긴 행과 바뀐 것', ['문장', '넣을 것', '넘긴 행', '바뀐 것'], done)),
            R.folded(R.table('모델 파일 ↔ 랩 DB 개수', ['항목', '모델 파일', '랩 DB', '견줌'], rows))] + browser()


def again(previous):
    first = db(C.export_graph)
    load_once()
    second = db(C.export_graph)
    moved = C.diff_graphs(first, second)
    n1, n2 = R.graph_counts(first), R.graph_counts(second)
    back = {{}}
    for i, k, was, now in moved['속성 바뀐 노드']:
        back.setdefault(i, []).append((k, f'{{shown(was)}} → {{shown(now)}}'))
    kinds = {{n['props'].get('id'): n['labels'][0] for n in second['nodes']}}
    cards = [dict(title=str(i), kind=kinds.get(i, ''), badge='값이 바뀜', state='bad', lines=ks) for i, ks in back.items()]
    cards += [dict(title=str(i), kind=kinds.get(i, ''), badge='다시 생김', state='bad') for i in moved['늘어난 노드'][:24]]
    cards += [dict(title=str(x), badge='관계가 늘어남', state='bad') for x in moved['늘어난 관계'][:12]]
    cards += [dict(title=f'{{x[0]}}', badge='관계의 값이 바뀜', state='bad', lines=[(x[1], f'{{shown(x[2])}} → {{shown(x[3])}}')]) for x in moved['속성 바뀐 관계'][:12]]
    said = ' · '.join(f'{{k}} {{len(v)}}' for k, v in moved.items() if v)
    return [R.verdict('bad', '다시 넣으니 달라졌습니다 — ' + said, '아래 카드에서 무엇이 달라졌는지 봅니다.') if cards else
            R.verdict('ok', f'다시 넣어도 그대로입니다 — 노드 {{n2.get("노드", 0)}}개 · 관계 {{n2.get("관계", 0)}}개, 값도 그대로', '같은 적재를 한 번 더 실행했지만 늘어난 것도, 바뀐 값도 없습니다.'),
            R.count_bars('같은 적재를 한 번 더 — 앞과 뒤의 개수', ('한 번 더 넣기 전', '한 번 더 넣은 뒤'), n1, n2)] + (
            [R.cards('한 번 더 넣어서 달라진 것', cards, wide=True,
                     note='노드나 관계가 늘었으면 MERGE의 패턴에 적은 것으로는 이미 있는 대상을 찾지 못해 새로 만든 것입니다 — 패턴에는 바뀌지 않는 식별자만 적습니다. '
                          '값이 바뀌었으면 넣는 쿼리가 다시 실행될 때마다 값을 모델 파일의 값으로 덮어쓴 것입니다. '
                          '지웠던 노드가 다시 생겼으면 모델 파일에는 그 줄이 그대로 있기 때문입니다.')] if cards else [])


def load_and_again(previous):
    return load(previous) + again(previous)


def probe(previous):
    """넣기 전 실험 — 넣는 쿼리를 이렇게 쓰면 DB가 뭐라고 하는지, 실험용 식별자로 랩 DB에 실제로 해 보고 모두 되돌린다."""
    path, graph = C.model_graph()
    schema = json.loads(path.with_name('schema.json').read_text(encoding='utf-8-sig'))
    label = {{n['props']['id']: n['labels'][0] for n in graph['nodes']}}
    props = {{n['props']['id']: n['props'] for n in graph['nodes']}}
    text_key = lambda p: 'name' if isinstance(p.get('name'), str) and p['name'] else next((k for k, x in p.items() if k != 'id' and isinstance(x, str) and x and x != p['id']), None)      # 식별자 말고 글자로 적힌 이름 — name이 있으면 name(가이드 06의 물음), 없으면 값이 식별자와 다른 첫 글자 속성
    one = next((r for r in graph['rels'] if r['type'] in schema['relations'] and text_key(props[r['a']])), None)
    if one is None:
        raise R.Stop(f'{{R.rel(path)}}: 실험에 쓸 관계(식별자 말고 글자 속성이 있는 시작 노드)가 모델에 없습니다.')
    A, B, T, K = label[one['a']], label[one['b']], one['type'], text_key(props[one['a']])
    name = str(props[one['a']][K])
    v = dict(a=f'{{one["a"]}} (실험)', b=f'{{one["b"]}} (실험)', name=name, other=name + ' ', none='없는 식별자 (실험)')
    before = db(C.counts)

    def run(queries):
        done, refused = db(C.tried, [(q, v) for q in queries])
        return done, refused

    def count(done, i):
        return done[i]['rows'][0][0] if len(done) > i and done[i]['rows'] else None

    cards = []

    def card(title, queries, answer, quiet):
        cards.append(dict(title=title, icon='open' if quiet else 'lock', state='warn' if quiet else 'ok', badge='오류 없이 받아 줌' if quiet else 'DB가 거절', text=answer,
                          lines=[(f'해 본 쿼리 {{i}}', q) for i, q in enumerate(queries, 1)]))

    q = [f'CREATE (n:{{A}} {{{{id: $a, {{K}}: $name}}}})', f'CREATE (n:{{A}} {{{{id: $a, {{K}}: $name}}}})', f'MATCH (n:{{A}} {{{{id: $a}}}}) RETURN count(n)']
    done, refused = run(q)
    card('CREATE로 같은 줄을 두 번 넣으면', q[:2], f'두 번째 CREATE에서 DB가 거절했습니다 — {{refused}}' if refused else f'두 번 다 받아 줬습니다. 같은 식별자의 노드가 {{count(done, 2)}}개입니다.', not refused)
    q = [f'MERGE (n:{{A}} {{{{id: $a, {{K}}: $name}}}})', f'MERGE (n:{{A}} {{{{id: $a, {{K}}: $other}}}})', f'MATCH (n:{{A}} {{{{id: $a}}}}) RETURN count(n)']
    done, refused = run(q)
    card(f'MERGE 패턴에 식별자 말고 {{K}}까지 적고, 그 값 끝에 빈칸 하나가 붙은 줄을 넣으면', q[:2],
         f'패턴 전체(식별자와 {{K}})가 같은 노드를 찾지 못해 새로 만들려다 DB가 거절했습니다 — {{refused}}' if refused else f'패턴 전체가 같은 노드를 찾지 못해 새로 만들었습니다. 같은 식별자의 노드가 {{count(done, 2)}}개입니다.', not refused)
    q = [f'MERGE (n:{{A}} {{{{id: $a}}}})', f'MERGE (n:{{A}} {{{{ID: $a}}}})', f'MATCH (n:{{A}}) WHERE n.id = $a OR n.ID = $a RETURN count(n)']
    done, refused = run(q)
    card('MERGE 패턴의 속성 이름을 id가 아니라 ID로 적으면', q[:2],
         f'DB가 거절했습니다 — {{refused}}' if refused else f'오류 없이 받아 줬습니다. 같은 값을 식별자로 가진 노드가 {{count(done, 2)}}개입니다 — 속성 이름은 대소문자가 다르면 다른 속성이라, id에 건 유일 제약이 ID는 지키지 못합니다.', not refused)
    q = [f'MERGE (a:{{A}} {{{{id: $a}}}})', f'MERGE (b:{{B}} {{{{id: $b}}}})', f'MATCH (a:{{A}} {{{{id: $a}}}}), (b:{{B}} {{{{id: $b}}}}) MERGE (b)-[:{{T}}]->(a)',
         f'MATCH (a:{{A}} {{{{id: $a}}}})-[:{{T}}]->(b:{{B}}) RETURN count(*)', f'MATCH (a:{{A}} {{{{id: $a}}}})<-[:{{T}}]-(b:{{B}}) RETURN count(*)']
    done, refused = run(q)
    made = done[2]['stats'].get('relationships_created', 0) if len(done) > 2 else 0
    card(f'관계 {{T}}의 화살표를 거꾸로({{B}} → {{A}}) 넣으면', q[2:],
         f'DB가 거절했습니다 — {{refused}}' if refused else f'DB는 거꾸로 그은 관계도 받았습니다(만든 관계 {{made}}개). 모델의 방향({{A}} → {{B}})으로 물으면 {{count(done, 3)}}행, 거꾸로 물으면 {{count(done, 4)}}행입니다 — 방향이 맞는지는 DB가 봐 주지 않습니다.', not refused)
    q = [f'MERGE (a:{{A}} {{{{id: $a}}}})', f'MATCH (a:{{A}} {{{{id: $a}}}}), (b:{{B}} {{{{id: $none}}}}) MERGE (a)-[:{{T}}]->(b)']
    done, refused = run(q)
    made = done[1]['stats'].get('relationships_created', 0) if len(done) > 1 else 0
    card('끝 노드가 아직 없는 관계를 넣으면', q[1:], f'DB가 거절했습니다 — {{refused}}' if refused else f'오류 없이 끝났고 만든 관계는 {{made}}개입니다 — 끝 노드를 찾지 못한 줄은 아무 말 없이 빠집니다.', not refused)
    after = db(C.counts)
    if after != before:
        raise RuntimeError(f'넣기 전 실험이 랩 DB의 개수를 바꿨습니다: {{before}} → {{after}}')
    quiet = sum(1 for c in cards if c['state'] == 'warn')
    return [R.verdict('info', f'다섯 가지를 랩 DB에 해 봤습니다 — DB가 거절 {{len(cards) - quiet}}가지 · 오류 없이 받아 줌 {{quiet}}가지', '내 예측과 견줍니다. 실험한 노드와 관계는 모두 되돌렸습니다.'),
            R.cards('넣는 쿼리를 이렇게 쓰면 DB는 뭐라고 할까 — 실제 답', cards, wide=True,
                    note=f'실험용 식별자 「{{v["a"]}}」 · 「{{v["b"]}}」로 실제 실행한 결과입니다. DB가 거절하는 것은 유일 제약이 지키는 것뿐이고, 오류 없이 받아 준 것은 넣는 사람이 쿼리와 개수로 확인해야 합니다. '
                         f'랩 DB의 개수는 실험 앞뒤로 같습니다(노드 {{before.get("노드", 0)}}개).')] + browser()


def paired(text):
    """「구성 요소=센서」처럼 두 열을 짝지은 조각들을 견줄 꼴로 — 조각은 「 · 」로만 나누고, 짝의 왼쪽 · 오른쪽 차례를 지킨 채 숫자 표기와 빈칸만 고른 뒤 조각 차례를 뗀다."""
    return sorted('='.join(numbers(x.strip()) for x in piece.split('=')) for piece in re.split(r'\\s*·\\s*', str(text or '').strip()) if piece.strip())


def same_answer(expected, actual):
    """볼_열이 한 열이면 same, 두 열의 짝(「=」로 이은 조각)이면 짝마다 견준다 — 값의 묶음이 같아도 짝이 다르면 다르다."""
    if '=' in str(expected) or '=' in str(actual):
        return paired(expected) == paired(actual)
    return same(expected, actual)


def ask_question(number):
    need_decided(DECIDE.get(str(number), []))
    every = expected_rows(['질문', '물을_값', '볼_열', '기대_답'], ['질문', '물을_값', '볼_열'])
    text, _ = R.read_text(HERE / '결과/기대_답.csv')
    at = dict(zip(map(id, every), [i for i, x in enumerate(text.splitlines(), 1) if x.strip() and not x.lstrip().startswith('#')][1:]))      # 기대 답 행의 편집기 줄 번호
    rows = [r for r in every if r['질문'] == str(number)]
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
    blocks, exp, act, blanks, absent = [], [], [], 0, []
    for asked in list(dict.fromkeys(r['물을_값'] for r in rows)) or ['']:      # 같은 값은 한 번만 묻고, 그 결과의 열마다 기대 답과 견준다
        params = {{names[0]: asked}} if names else {{}}
        (_, _, cols, data), = db(C.query, path, str(number), params)
        if asked:
            head = f'쿼리가 따라간 길 — 물은 값 「{{asked}}」'
            try:
                walk = C.walked(path, str(number), params)
            except C.LabDbOff as e:
                raise R.Stop(str(e))
            except RuntimeError as e:      # 짐작해 그리지 않는다 — 읽지 못한 까닭을 말한다
                walk = None
                blocks.append(R.cards(head, [dict(title='이 쿼리에서 길을 읽지 못했습니다', icon='warn', state='warn', text=str(e) + ' 그림만 없고, 아래 쿼리 결과와 기대 답 대조는 그대로입니다.')]))
            if walk is not None:
                blocks.append(R.walk_figure(head, walk, asked, note='쿼리의 MATCH 패턴이 랩 DB에서 실제로 지난 노드와 관계입니다. 굵은 테두리 = 물은 값.')
                              or R.cards(head, [dict(title=asked, icon='warn', state='warn', badge='맞는 노드 없음',
                                                     text='이 값으로 물으니 쿼리의 MATCH 패턴에 맞는 노드가 랩 DB에 하나도 없습니다. 그래서 따라간 길이 없습니다.')]))
        blocks.append(R.folded(R.table(f'질문 {{number}} — 물은 값 「{{asked}}」 쿼리 결과', cols, [[shown(v) for v in row] for row in data])))
        for r in rows:
            if r['물을_값'] != asked or not r.get('볼_열'):
                continue
            wanted = [c.strip() for c in r['볼_열'].split('+')]      # 「열」 하나, 또는 결과 줄마다 두 열을 짝지어 견주는 「열+열」
            exp.append({{'짝': asked + ' → ' + r['볼_열'], '답': r['기대_답']}})
            missing = [c for c in wanted if c not in cols]
            if missing:      # 이 줄만 견주지 못한다 — 다른 줄은 그대로 견준다
                act.append({{'짝': asked + ' → ' + r['볼_열'], '답': f'견줄 수 없음(쿼리 결과에 {{" · ".join(missing)}} 열이 없음)'}})
                absent.append((f'결과/기대_답.csv:{{at[id(r)]}}', r['볼_열'], ' · '.join(missing), ', '.join(cols) or '없음'))
                continue
            idx = [cols.index(c) for c in wanted]
            cell = lambda x: '없음' if x in (None, '') else shown(x)
            act.append({{'짝': asked + ' → ' + r['볼_열'], '답': ' · '.join('='.join(cell(row[i]) for i in idx) for row in data) or '0줄'}})
            blanks += sum(1 for row in data for i in idx if row[i] == '')
    if absent:
        blocks.insert(0, R.cards('기대 답의 볼_열이 쿼리 결과에 없습니다', [dict(title=where, badge=f'없는 열: {{lost}}', state='bad', icon='warn',
                                 lines=[('기대 답이 보려는 열', wanted), ('쿼리가 돌려준 열', had), ('쿼리', f'결과/query.cypher:{{line}}')]) for where, wanted, lost, had in absent],
                                 note='쿼리가 그 열을 돌려주게 고치거나(RETURN … AS 열 이름), 기대 답의 볼_열을 쿼리가 돌려주는 열 이름으로 맞춥니다. 다른 줄은 아래에서 그대로 견줬습니다.'))
    if exp:
        blocks.insert(0, R.compare(f'질문 {{number}} 기대 답 ↔ 조회 결과(볼_열의 값)', '짝', exp, act, ['답'], same=same_answer,
                                   note=SAME_NOTE + ' 볼_열을 「열+열」로 적은 줄은 결과 줄마다 두 열의 값을 「=」로 짝지어 견줍니다(값이 같아도 짝이 다르면 다름). ' + (f'볼_열에서 빈 글자 {{blanks}}칸을 값 없음(null)과 같은 「없음」으로 견줬습니다. 조회가 값이 없는 칸을 빈 글자로 바꾸고 있습니다 — 값 없음은 null로 돌려주는 편이 다른 조회와 섞이지 않습니다.' if blanks else '')))
    texted = db(C.text_against_date, text)
    if texted:      # 오류 없이 답만 비는 쿼리 — 까닭을 화면이 말한다. 대조 표가 길어도 첫 화면에 보이게 결론 줄 바로 아래에 둔다
        blocks.insert(0, R.cards('날짜 속성을 글자와 견준 조건', [dict(title=f'{{k}} ↔ {{lit}}', badge='자료형이 다름', state='bad', icon='warn',
                                 lines=[('쿼리', f'결과/query.cypher:{{line}}'), ('견준 것', f'{{k}}(날짜 속성) ↔ {{lit}}(글자)', '글')]) for k, lit in texted],
                                 note='랩 DB에서 이 속성은 날짜이고, 따옴표로 적은 값은 글자입니다. 날짜와 글자는 자료형이 달라 견준 조건이 참이 되지 않으므로, 이 조건에 걸린 줄은 오류 없이 모두 걸러집니다. '
                                      "글자를 date('2026-10-15')처럼 날짜로 바꿔 견줍니다."))
    return [tally(blocks)] + blocks + browser()


def q1(previous):
    return ask_question(1)


def q2(previous):
    return ask_question(2)


def q3(previous):
    return ask_question(3)


def after_value(graph, i, k):
    return next((n['props'].get(k) for n in graph['nodes'] if n['props'].get('id') == i), None)


def change(previous):
    """수정본 반영 — 내 수정 쿼리를 실행하고, 모델 파일대로 넣은 직후의 그래프와 견준다(몇 번째 실행이든 수정본의 줄이 다 보인다).
    같은 수정을 한 번 더 실행하면 또 바뀌는지는 되돌리는 트랜잭션에서 해 보고 랩 DB에 남기지 않는다. 반영한 뒤의 값은 스키마에 대어 본다."""
    need_decided(DECIDE.get('update', []))
    path = HERE / '결과/update.cypher'
    _, model = C.model_graph()
    schema = db(C.schema_in_use)
    first, missing = db(C.apply_changes, path)
    after = db(C.export_graph)
    again = db(C.apply_changes_tried, path)
    d = C.diff_graphs(model, after)
    d2 = C.diff_graphs(after, again)
    rows = [(k, len(v), ' · '.join(str(x if not isinstance(x, tuple) else f'{{x[0]}} {{x[1]}}: {{x[2]}} → {{x[3]}}') for x in v[:12]) + (' …' if len(v) > 12 else '')) for k, v in d.items()]
    same = all(not v for v in d2.values())
    old = {{n['props'].get('id'): n for n in model['nodes']}}
    new = {{n['props'].get('id'): n for n in after['nodes']}}
    moved = {{}}
    for i, k, was, now in d['속성 바뀐 노드']:
        moved.setdefault(i, []).append((k, f'{{shown(was)}} → {{shown(now)}}'))
    off = db(C.against_schema, after, schema)      # 반영한 뒤의 값을 스키마에 대어 본다(스키마에 없는 속성 · 자료형 · 목록에 겹친 값)
    off += [(i, k, f'자료형이 다름(스키마 date — 랩 DB에는 {{kind}})', after_value(after, i, k)) for _, k, i, kind in db(C.date_gap)]      # 글자로 들어간 날짜는 내보낸 글로는 가를 수 없어 랩 DB에 묻는다
    cards = [dict(title=i, kind=new[i]['labels'][0], badge='값 바뀜', state='warn', lines=ks) for i, ks in moved.items()]
    cards += [dict(title=str(i), kind=old[i]['labels'][0], badge='사라짐', state='bad', text=str(old[i]['props'].get('name') or old[i]['props'].get('tag') or '')) for i in d['사라진 노드'][:24]]
    cards += [dict(title=str(i), kind=new[i]['labels'][0], badge='새로 생김', state='ok', text=str(new[i]['props'].get('name') or new[i]['props'].get('tag') or '')) for i in d['늘어난 노드'][:24]]
    touched = set(moved) | set(d['사라진 노드']) | set(d['늘어난 노드'])
    applied, per_line = [], {{}}
    for line, name, how, done in first:      # 수정본 줄마다, 그 줄을 받은 쿼리들이 DB에서 바꾼 것
        for n, row, stats in done:
            applied.append((f'{{name}}:{{n}}', how, R.rel(path) + f':{{line}}', changed(stats)))
            per_line.setdefault((name, n, how), []).append(stats)
    idle = [(f'{{name}}:{{n}}', how) for (name, n, how), stats in per_line.items() if not any(stats)]
    rows_all = db(C.change_rows)
    lost = [(name, how, len(rows_all[(name, how)])) for name, how in missing]

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

    left, right = side('넣은 직후', model, set(d['사라진 노드']), set()), side('수정본 반영 뒤', after, set(), set(d['늘어난 노드']))
    counted = f'값이 바뀐 노드 {{len(moved)}}개 · 사라진 노드 {{len(d["사라진 노드"])}}개 · 늘어난 노드 {{len(d["늘어난 노드"])}}개'
    good = same and not lost and not off
    detail = ' '.join(x for x in ['같은 수정을 한 번 더 실행해도 더 바뀐 것이 없습니다.' if same else '같은 수정을 한 번 더 실행하면 또 바뀝니다 — 값을 덧붙이거나 새로 만드는 쿼리가 있는지 봅니다.',
                                  f'아직 쿼리가 없는 수정본 줄 {{sum(n for _, _, n in lost)}}개.' if lost else '', f'스키마와 맞지 않는 값 {{len(off)}}개.' if off else ''] if x)
    return [R.verdict('ok' if good else 'warn', '수정본 반영 — ' + counted, detail),
            R.cards('바뀐 노드 — 넣은 직후 → 지금', cards, note='모델 파일대로 넣은 직후와 지금 랩 DB를 견준 것입니다. 수정본의 줄과 하나씩 견줍니다.') if cards else R.note('모델 파일대로 넣은 직후와 견줘 노드의 값 · 개수에 바뀐 것이 없습니다.')] + (
            [R.cards('스키마와 맞지 않는 값', [dict(title=f'{{i}}의 {{k}}', badge=what, state='bad', icon='warn', lines=[('지금 값', shown(v))]) for i, k, what, v in off[:24]],
                     note='스키마에 없는 속성은 그 자리를 먼저 정한 뒤에 넣습니다(남길 값이면 결과/스키마_추가.csv에 그 속성을 적고, 아니면 쿼리에서 뺍니다). '
                          '수정본의 값은 모두 글자로 넘어오므로 수로 담을 값은 쿼리에서 수로, 날짜로 담을 값은 날짜로(date(…)) 바꿔 넣고, 목록에는 이미 있는 값을 다시 더하지 않습니다. '
                          '쿼리를 고친 뒤에도 앞서 들어간 값이 남아 있으면 python run.py reset으로 넣은 직후로 되돌리고 다시 반영합니다.')] if off else []) + (
            [R.cards('아직 쿼리가 없는 수정본 줄', [dict(title=f'{{name}} · {{how}}', badge=f'{{n}}줄', state='bad', icon='warn') for name, how, n in lost],
                     note='수정본의 이 줄들은 어느 쿼리도 받지 않아 그래프에 반영되지 않았습니다. 지우지 않고 남기기로 한 줄도, 남긴다는 것을 그래프에 적는 쿼리가 있어야 합니다.')] if lost else []) + (
            [R.cards('DB에서 아무것도 바꾸지 않은 수정본 줄', [dict(title=where, badge=how, state='warn', icon='warn') for where, how in idle],
                     note='이 줄을 받은 쿼리가 맞는 노드를 찾지 못했거나, 이미 반영돼 있어 바꿀 것이 없었습니다. 처음 반영인데 여기 나오면 쿼리가 그 줄의 대상을 무엇으로 찾는지 봅니다.')] if idle else []) + (
            [R.pair('바뀐 노드를 넣은 직후와 지금으로 나란히', left, right, note='굵은 테두리 = 값이 바뀐 노드(아래 글 = 그때의 값), 점선 = 수정 뒤 사라지는 노드. 16개까지만 그립니다.')] if d['사라진 노드'] or d['늘어난 노드'] else []) + ([R.count_bars('넣은 직후 ↔ 지금 개수', ('넣은 직후', '지금'), R.graph_counts(model), R.graph_counts(after))]
                                      if len(model['nodes']) != len(after['nodes']) or len(model['rels']) != len(after['rels']) else []) + [
            R.folded(R.table('수정본 줄마다 받은 쿼리와 이번 실행에서 DB가 바꾼 것', ['수정본 줄', '변경', '쿼리', '바뀐 것'], applied)),
            R.folded(R.table('넣은 직후 → 지금', ['바뀜', '개수', '대상'], rows)),
            R.folded(R.counts('지금 개수', [('노드', len(after['nodes'])), ('관계', len(after['rels']))])),
            R.raw('같은 수정을 한 번 더 실행해 본 결과(랩 DB에는 남기지 않음)', '같은 수정을 한 번 더 실행: ' + ('더 바뀐 것 없음' if same else '또 바뀜 — ' + '; '.join(f'{{k}} {{len(v)}}' for k, v in d2.items() if v)))] + browser()


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


def render(kind, title, names, change=False):
    """kind = design_integrated · graph_integrated(두 과정이 같은 화면 코드를 쓴다 — 실전반은 session2_factory*.py가 이 글 뒤에 덧댄다). names는 쓰지 않는다 —
    단계는 가이드 원고(session2_project_guides)가 갖고, 새 프로젝트 구조는 STEPS 앞까지만 쓴다(session2_project.actions_source)."""
    if kind == 'design_integrated':
        return DESIGN_INTEGRATED.format(title=title)
    if kind == 'graph_integrated':
        import build_labs as B
        import session2_answers as ANS
        return GRAPH.format(title=title, change=change, steps='[]', decide={'update': B.GRAPH_POINTS['통합반']}, student=list(ANS.STUDENT_LOAD), raw=dict(ANS.RAW_LOAD))
    raise ValueError(f'2회차 랩의 화면 코드는 design_integrated · graph_integrated 둘입니다: {kind}')
