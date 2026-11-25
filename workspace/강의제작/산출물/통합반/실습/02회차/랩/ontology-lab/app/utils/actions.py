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

from app.utils import model as M

TITLE = '현장 정보를 체계화하는 온톨로지 직접 설계하기'
KEY = ['질문', '물을_값', '항목']   # 기대 답 한 줄을 가리키는 열


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


def design(previous):
    ids, links, prev = guarded(M.preview_ids)
    clash = [(k, i, ', '.join(f"{v['파일']}:{n}" for n in lines)) for k, v in prev.items() for i, lines in v['겹침'].items()]
    twice = set(k for k, _, _ in clash)
    nodes = [R.node(k, k, sub='식별자 ' + v, badge=f"{prev[k]['개수']}개" if k in prev else '', mark='bad' if k in twice else '', props=dict(식별자_만드는_법=v)) for k, v in ids.items()]
    out = [R.verdict('warn', f'식별자가 겹치는 원자료 행 {len(clash)}곳', '겹친 식별자 하나는 대상 하나가 됩니다 — 같은 대상인지 그 원자료 줄로 봅니다.') if clash else
           R.verdict('ok', '식별자가 겹치는 원자료 행이 없습니다', f'클래스 {len(ids)}개 · 관계 {len(links)}개'),
           R.graph('내가 설계한 클래스와 관계', nodes, [R.edge(v[1], v[2], f'{v[0]} · {v[3]}') for v in links.values()],
                   note='상자 = 클래스, 아래 글 = 식별자 만드는 법, 오른쪽 수 = 서로 다른 식별자 수. 화살표의 글 = 관계 이름 · 카디널리티.' + (' 빨간 테두리 = 식별자가 겹친 클래스.' if clash else ''))]
    if clash:
        out.append(R.cards('식별자가 겹친 곳', [dict(title=i, badge=k, state='bad', icon='warn', kind=k, lines=[('겹친 원자료 행', rows)]) for k, i, rows in clash]))
    out += [R.folded(R.table('종류와 식별자 만드는 법(app/features/design.csv)', ['대상', 'ID_만드는_법'], [(k, v) for k, v in ids.items()],
                    note=('실물 행이 있어 구성 요소(자리)와 일련번호가 붙은 실물을 따로 둡니다.' if '실물' in ids else
                          '실물 행이 없어 일련번호는 구성 요소의 속성으로 둡니다.'))),
            R.folded(R.table('관계와 방향 · 카디널리티(app/features/relations.csv)', ['연결', '관계 이름', '시작 → 끝', '카디널리티'], [(k, v[0], f'{v[1]} → {v[2]}', v[3]) for k, v in links.items()],
                    note='카디널리티는 시작 쪽 수:끝 쪽 수이고 1은 많아야 하나입니다. 만든 연결이 적은 수를 넘으면 그 단계에서 멈추고 relations.csv 줄과 원자료 줄을 짚습니다.'))]
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
                           note='일련번호가 적힌 구성 요소 행마다 실물 하나입니다. 지난 실물은 app/features/row_rules.csv의 「지난 실물」 행이고, 이 모델에서 그 실물의 자리와 이력을 물을 수 있습니다.')))
    else:
        out.append(R.note('실물을 따로 두지 않았습니다. 일련번호는 구성 요소의 속성(지금 달린 것 하나)이고, app/features/row_rules.csv에서 뺀 행의 실물(철거된 장치)은 이 모델에서 물을 수 없습니다.'))
    if info['unused']:
        out.append(R.table('app/features/row_rules.csv에 적었지만 쓰이지 않은 행', ['파일', '행'], info['unused']))
    return out


def sensors(previous):
    info, _ = guarded(M.build, '센서')
    groups = {}
    for sid, code, tag, q in info['센서']:
        groups.setdefault(q, []).append(f'{code}:{tag}')
    base = {q: unit for q, _, unit in info['단위']}
    out = [R.verdict('info', f'센서 {len(info["센서"])}개가 물리량 {len(groups)}개로 묶였습니다', '한 묶음이 물리량 하나입니다 — 내가 정한 범위대로 묶였는지 봅니다.'),
           R.gather('센서가 물리량으로 묶인 모습', ('센서(설비:태그)', '물리량 · 기준 단위'),
                    [dict(left=sorted(v), mid=dict(text=k, kind='물리량', sub=base[k])) for k, v in sorted(groups.items())],
                    note='왼쪽 센서들이 오른쪽 물리량 하나를 잽니다. 같은 물리량이라고 본 센서끼리만 한 줄에 모입니다.')]
    if info['변환']:
        out.append(R.cards('단위를 기준 단위로 바꾼 센서', [dict(title=r[1], badge=f'{r[3]} → {r[4]}', kind='센서', lines=[('물리량', r[2]), ('원래 정상값 / 한계', r[5]), ('바꾼 정상값 / 한계', r[6]), ('원자료 행', r[0])]) for r in info['변환']]))
    return out + [R.folded(R.table('물리량마다 묶인 센서(same_quantity · quantity_name)', ['물리량', '센서 수', '설비:태그', '기준 단위'], [(k, len(v), ' · '.join(sorted(v)), base[k]) for k, v in sorted(groups.items())])),
                  R.folded(R.table('물리량마다 원자료에 적힌 단위와 기준 단위(제공 코드)', ['물리량', '원자료에 적힌 단위', '기준 단위'], info['단위'],
                                   note='기준 단위는 그 물리량의 센서 행이 가장 많이 쓴 단위입니다. 단위가 다른 값을 그대로 견주면 어긋나므로 제공 코드가 기준 단위로 바꿉니다.')),
                  R.folded(R.table('단위를 기준 단위로 바꾼 센서 행(제공 코드)', ['원자료 행', '센서 식별자', '물리량', '원래 단위', '모델의 단위', '원래 정상값 / 한계', '바꾼 정상값 / 한계'], info['변환'],
                          note='원래 값과 바꾼 값을 그 원자료 줄로 견줍니다. 값이 없는 칸은 0이 아니라 「없음」입니다.'))]


def parts(previous):
    info, _ = guarded(M.build, '부품')
    usage = {}
    for _, code, cname, cell, pid, how in info['이은_부품']:
        usage.setdefault(pid, set()).add(code)
    lost = info['못_찾은_칸']
    wrong = [r for r in info['카디널리티'] if r[5] != '맞음']
    return [R.verdict('warn', f'사내 품번을 찾지 못한 교체부품 칸 {len(lost)}개', '그 칸의 글을 품번 교차표와 견줍니다.') if lost else
            R.verdict('ok', f'교체부품 칸 {len(info["이은_부품"])}개를 부품 {len(usage)}개에 이었습니다', '여러 표기가 사내 품번 하나로 모였고, 모델 파일을 새로 썼습니다.' + ('' if wrong else ' 적은 카디널리티와 만든 연결도 모두 맞습니다.')),
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
            R.note('output/schema.json · output/graph.json을 새로 썼습니다.')]


def ask(previous):
    rows = expected_rows(['질문', '물을_값', '기대_답'], KEY)
    got = guarded(M.answers, list(dict.fromkeys((r['질문'], r['물을_값']) for r in rows)))   # 같은 설비를 여러 줄에 적어도 한 번만 묻는다
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
    keep = [r for r in got if (str(r['질문']), r['물을_값']) not in picked or r['항목'] in picked[(str(r['질문']), r['물을_값'])]]
    value = lambda r: str(r['질문']).strip() == '2' and bool(r.get('항목'))   # 질문 2 센서 값은 차례까지 같아야 한다
    exact = lambda e, a: [x.strip() for x in str(e).split('·')] == [x.strip() for x in str(a).split('·')]
    note = (f'기대 답에 적은 항목만 견줍니다(모델이 더 돌려준 {len(got) - len(keep)}줄은 표에 넣지 않음). '
            '물을 값과 답은 설비 코드 · 사내 품번처럼 현장이 쓰는 값이라 식별자를 어떻게 지었든 같은 값으로 묻습니다. 질문 1의 항목은 원자료 이름으로 적어도 그 구성 요소의 다른 이름으로 찾습니다. '
            '「실제 없음」은 기대 답의 항목이 모델에 없는 것입니다(이름을 다르게 적었거나 모델이 그 대상을 만들지 않음). 「기대 밖」은 모델이 더 돌려준 항목입니다. '
            '모델의 답 「없음」은 물은 품번 · 표기 · 설비 · 물리량이 모델에 없다는 뜻이고, 「쓰는 설비 없음」은 부품은 모델에 있지만 그 부품에 이은 구성 요소가 없다는 뜻입니다. ' + SAME_NOTE)
    out = [R.compare('기대 답 ↔ 모델에 물은 답(질문 | 물을 값 | 항목)', '짝', [{'짝': key(r), '답': r['기대_답']} for r in rows if not value(r)],
                     [{'짝': key(r), '답': r['답']} for r in keep if not value(r)], ['답'], same=same, note=note)]
    if any(value(r) for r in rows):
        out.append(R.ordered(R.compare('질문 2 센서 값 — 단위 · 정상값 · 한계 · 한계구분 차례', '짝', [{'짝': key(r), '답': r['기대_답']} for r in rows if value(r)],
                             [{'짝': key(r), '답': r['답']} for r in keep if value(r)], ['답'], same=exact,
                             note='값은 차례까지 견줍니다. 단위를 바꾼 센서는 바꾼 단위의 값, 값이 없는 칸은 「없음」, 단위를 정하지 못했으면 「미확인」입니다.')))
    return [tally(out)] + out


def check(previous):
    return run_check()

COMMANDS = {
    'sources': ('원자료', sources),
    'expected': ('기대 답', expected),
    'design': ('식별자와 관계', design),
    'names': ('구성 요소 이름과 실물', names),
    'quantities': ('물리량과 센서', sensors),
    'parts': ('부품과 모델', parts),
    'query': ('질문별 대조', ask),
    'check': ('구조 검사', check),
}
