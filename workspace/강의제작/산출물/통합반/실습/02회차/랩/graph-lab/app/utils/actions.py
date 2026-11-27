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
            raise R.Stop(f'app/features/expected.csv:{seen[k]} · {line}: 같은 ({" · ".join(key)}) 「{" · ".join(k)}」가 두 줄입니다 — 같은 값을 같은 열로 두 번 견주는 줄입니다. 한 줄만 남기고, 한 열의 여러 값은 한 칸에 「 · 」로 잇습니다. 같은 결과의 다른 열을 견주려면 볼_열을 바꾼 줄을 씁니다.')
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
        if not re.search(r'[^\s:]+:\d+', r['근거']):
            raise R.Stop(f'app/features/decisions.csv:{line}(지점 「{point}」): 근거에 파일:줄이 없습니다 — 그렇게 고른 내 이유 뒤에, 정할 때 열어 본 원문 줄을 파일:줄 꼴로 함께 적습니다.')


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
from app.utils import cypher as C

TITLE = '설계한 온톨로지를 그래프 DB에 구현하고 검증하기'
CHANGE = True
DECIDE = {'update': ['불용 결정 설비', '목록에서 빠진 센서']}   # 기능마다 쓰는 결정 지점(질문 번호 · update)
STUDENT = ['Asset', '설비-구성 요소', '구성 요소-부품']   # 내 적재 쿼리 몫 — 종류(레이블) 이름이거나 두 클래스의 짝(그 짝을 잇는 관계 이름은 스키마에서 읽는다). 비어 있으면 적재 쿼리를 모두 내가 쓴다
RAW = {'Asset': 'equipment.csv'}   # 원자료 표의 줄을 적힌 그대로 받는 종류(열 이름 → 속성 짝을 내 쿼리가 정한다)


def db(fn, *a):
    try:
        return fn(*a)
    except C.LabDbOff as e:
        raise R.Stop(str(e))
    except RuntimeError as e:
        raise R.Stop(str(e))


def graph_counts():
    path, graph = C.model_graph()
    out = {'노드': len(graph['nodes']), '관계': len(graph['rels'])}
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
    return [R.verdict('info', '랩 DB가 비어 있습니다 (노드 0개)', f'모델 파일에는 노드 {model["노드"]}개 · 관계 {model["관계"]}개가 있습니다.') if empty else
            R.verdict('ok', f'랩 DB와 모델 파일의 개수가 같습니다 — 노드 {have.get("노드", 0)}개 · 관계 {have.get("관계", 0)}개') if not differ else
            R.verdict('info', f'랩 DB에 노드 {have.get("노드", 0)}개 · 관계 {have.get("관계", 0)}개', f'모델 파일과 개수가 다른 항목 {len(differ)}개 — 적재나 수정이 반영된 것인지 봅니다.'),
            R.count_bars('모델 파일과 지금 랩 DB의 개수', ('모델 파일', '랩 DB'), model, have),
            R.folded(R.table(f'모델 파일({R.rel(path)})과 지금 랩 DB의 개수', ['항목', '모델 파일', '랩 DB'], rows)),
            ] + browser()


def expected(previous):
    rows = expected_rows(['질문', '물을_값', '볼_열', '기대_답', '근거'], ['질문', '물을_값', '볼_열'])
    return [R.verdict('info', f'기대 답 {len(rows)}줄을 정했습니다', '쿼리 결과를 이 답과 견줍니다.'),
            question_cards(rows, lambda r: r['물을_값'] + ' → ' + r['볼_열']),
            R.folded(R.table('내가 정한 기대 답', ['질문', '물을_값', '볼_열', '기대_답', '근거'], rows))]


def constraints(previous):
    """유일 제약 걸기 — 학생의 제약 쿼리를 실행하고, 지금 쓰는 모델의 종류마다 식별자(id)에 유일 제약이 걸렸는지와 같은 식별자로 노드를 두 번 만들 때 DB가 하는 답을 보인다.
    시험한 노드는 받아 주든 거절하든 되돌린다(랩 DB의 개수가 전후로 같지 않으면 멈춘다)."""
    path = HERE / 'app/features/constraints.cypher'
    model_path, graph = C.model_graph()
    labels = sorted(json.loads(model_path.with_name('schema.json').read_text(encoding='utf-8-sig'))['classes'])
    first = {}
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
            raise R.Stop(f'{e}\n랩 DB에 같은 식별자의 노드가 이미 겹쳐 있어 유일 제약을 걸 수 없습니다 — ' + ' / '.join(f'{l} 「{v}」 {c}개' for l, v, c in twice)
                         + '. 겹친 노드를 하나만 남긴 뒤 다시 실행합니다.')
        raise R.Stop(str(e))
    have = db(C.constraints)
    unique = {labels_[0]: name for name, kind, entity, labels_, props in have
              if entity == 'NODE' and ('UNIQUE' in kind or kind == 'NODE_KEY') and len(labels_) == 1 and props == ['id']}
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
                          text=(f'「{first[label]}」로 두 번 만들기 → ' + ('DB가 거절' if said else 'DB가 받아 줌(노드가 둘 생김)')) if label in first else answer,
                          lines=[('DB가 한 말' + (' — 같은 식별자의 노드가 이미 있다는 뜻' if 'already exists' in said else ''), said)] if said else []))
    after = db(C.counts)
    if after != before:
        raise RuntimeError(f'유일 제약 시험이 랩 DB의 개수를 바꿨습니다: {before} → {after}')
    opened = [c['title'] for c in cards if c['state'] == 'bad']
    return [R.verdict('warn', f'유일 제약이 없는 종류 {len(opened)}개 — ' + ' · '.join(opened), '이 종류는 같은 식별자의 노드가 둘 생길 수 있습니다.') if opened else
            R.verdict('ok', f'종류 {len(labels)}개 모두 식별자에 유일 제약이 걸렸습니다', '같은 식별자로 새로 만들면 DB가 거절합니다.'),
            R.cards('종류마다 걸린 자물쇠 — 같은 식별자로 두 번 만들 때 DB의 답', cards, note='종류마다 같은 식별자로 CREATE를 두 번 실행해 본 실제 결과입니다. 시험한 노드는 되돌렸습니다.'),
            R.folded(R.table('제약 쿼리마다 DB가 한 일', ['쿼리', '새로 건 제약'], [(R.rel(path) + f':{line}', res.get('stats', {}).get('constraints_added', 0) or '0(이미 걸려 있음)') for line, res in done])),
            R.folded(R.table('랩 DB에 걸려 있는 제약(SHOW CONSTRAINTS)', ['이름', '제약 종류', '레이블', '속성'], [(name, kind, ' · '.join(labels_), ' · '.join(props)) for name, kind, entity, labels_, props in have])),
            R.folded(R.table('종류마다 — 식별자의 유일 제약과, 같은 식별자로 노드를 두 번 만들 때 DB의 답', ['종류', '식별자', '유일 제약', '시험한 식별자', 'DB의 답'], rows,
                    note='모델의 종류(레이블)마다 그 종류의 식별자 하나로 CREATE를 두 번 실행해 본 실제 결과입니다. 유일 제약이 걸린 종류는 DB가 거절하고, 「없음」인 종류는 받아 줍니다. '
                         f'시험한 노드는 모두 되돌려 랩 DB에 남기지 않았습니다(노드 {before["노드"]}개 그대로).'))]


STATS = dict(nodes_created='만든 노드', nodes_deleted='지운 노드', relationships_created='만든 관계', relationship_deleted='지운 관계', relationships_deleted='지운 관계',
             properties_set='넣은 속성 값', labels_added='붙인 레이블', labels_removed='뗀 레이블', constraints_added='건 제약', constraints_removed='푼 제약')


def changed(stats):
    """DB가 돌려준 바뀐 수 — 한국어 뜻을 앞에 쓰고, DB가 쓰는 이름은 괄호에 근거로 둔다."""
    seen = [(k, v) for k, v in stats.items() if isinstance(v, int) and not isinstance(v, bool) and v]
    if not seen:
        return '바뀐 것 없음'
    return ' · '.join(f'{STATS.get(k, k)} {v}' for k, v in seen) + ' (' + ', '.join(f'{k} {v}' for k, v in seen) + ')'


def load_once():
    """적재 실행 — 내 쿼리 몫이 정해진 랩은 내 쿼리와 제공 쿼리를 함께(노드 먼저, 관계 나중), 아니면 내 쿼리 파일만. ([(파일:줄, 넣을 것, 넘긴 행, 바뀐 것)], 쿼리가 없는 종류 · 관계)."""
    mine = HERE / 'app/features/load.cypher'
    if STUDENT:
        out, missing = db(C.load_files, mine, STUDENT, RAW)
    else:
        out, missing = [(mine, *x) for x in db(C.load_file, mine)], []
    return [(R.rel(path) + f':{line}', target, n, changed(res.get('stats', {}))) for path, line, target, n, res in out], missing


def seek_cards():
    """내 적재 쿼리마다 DB가 노드를 어떻게 찾는지 — 쿼리를 실행하지 않고 DB에 미리 물어본 답(EXPLAIN). 유일 제약을 건 식별자로 바로 찾는지, 노드를 하나씩 다 보는지."""
    items, said = [], []
    for line, target, s, rows, _ in db(C.load_plan, HERE / 'app/features/load.cypher', None, RAW):
        ops = db(C.seek_plan, s, rows)
        scan = [o for o in ops if 'Scan' in o]
        where = R.rel(HERE / 'app/features/load.cypher') + f':{line}'
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
    kinds = {n['props'].get('id'): n['labels'][0] for n in model['nodes']}
    back = {}
    for i, k, was, now in d['속성 바뀐 노드']:
        back.setdefault(i, []).append((k, f'모델 {shown(was)} → 랩 DB {shown(now)}'))
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
        lines = [('모델 파일', f"{g['시작']} → {g['끝']} {g['모델']}개")]
        if g['거꾸로']:
            lines.append((f"랩 DB에는 거꾸로 {len(g['거꾸로'])}개", ' · '.join(f'{b} → {a}' for a, b in g['거꾸로'][:3]) + (' …' if len(g['거꾸로']) > 3 else '')))
        if g['빠짐']:
            lines.append((f"랩 DB에 없는 것 {len(g['빠짐'])}개", ' · '.join(f'{a} → {b}' for a, b in g['빠짐'][:3]) + (' …' if len(g['빠짐']) > 3 else '')))
        cards.append(dict(title=g['유형'], badge='화살표가 거꾸로' if g['거꾸로'] else '모델과 다른 노드에 이어짐', state='bad', icon='warn', lines=lines))
    return cards


def date_cards():
    """스키마에서 자료형이 날짜인 속성이 랩 DB에 날짜가 아닌 값으로 들어간 곳 — 내보낸 글로는 날짜와 글자가 똑같이 보여, 랩 DB에 자료형을 직접 물어본다."""
    by = {}
    for label, name, i, kind in db(C.date_gap):
        by.setdefault((label, name), []).append((i, kind))
    return [dict(title=f'{label}.{name}', kind=label, badge=f'{len(hit)}곳', state='bad', icon='warn',
                 lines=[('랩 DB에 들어간 자료형', ' · '.join(sorted({k for _, k in hit}))), ('그 노드', ' · '.join(str(i) for i, _ in hit[:5]) + (' …' if len(hit) > 5 else ''))]) for (label, name), hit in sorted(by.items())]


def query_pairs():
    """내 쿼리와 제공 쿼리를 나란히 — 같은 곳과 다른 곳을 읽어 보는 재료."""
    given = HERE / 'output/load_provided.cypher'
    if not given.is_file():
        return []
    one = lambda path, pick: [(t, s) for line, t, s, rows, node in db(C.load_plan, path, None, RAW) if pick(node)]
    mine = one(HERE / 'app/features/load.cypher', lambda node: True)
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
    return [R.verdict('bad', f'모델 파일과 랩 DB의 개수가 다른 항목 {len(differ)}개', ' · '.join(differ[:6]) + (' — 쿼리가 없는 종류 · 관계: ' + ' · '.join(missing) if missing else '')) if differ else
            R.verdict('bad', f'개수는 같지만 모델 파일과 다르게 이어진 관계가 있습니다 — {" · ".join(c["title"] for c in turned)}', '아래 카드에서 화살표가 어느 쪽으로 들어갔는지 보고, 내 관계 쿼리의 시작과 종료가 스키마와 같은지 봅니다.') if turned else
            R.verdict('bad', f'개수는 같지만 모델 파일과 값이 다른 노드가 있습니다 — {len(gap)}곳', '아래 카드에서 어느 속성이 다른지 보고, 내 쿼리가 원자료의 어느 열을 어느 속성에 넣었는지 봅니다.') if gap else
            R.verdict('bad', f'스키마는 날짜인데 랩 DB에 글자로 들어간 값이 있습니다 — {" · ".join(c["title"] for c in dated)}', '글자로 들어간 날짜는 날짜와 앞뒤를 견주는 쿼리에서 조용히 빠집니다. 아래 카드의 속성을 넣는 쿼리를 봅니다.') if dated else
            R.verdict('ok', f'모델 파일과 랩 DB의 개수가 같습니다 — 노드 {have.get("노드", 0)}개 · 관계 {have.get("관계", 0)}개', '모델의 종류는 레이블이, 인스턴스는 노드가 됐습니다.' + (' 값과 관계의 방향도 모델 파일과 같습니다.' if STUDENT else '')),
            R.count_bars('모델 파일 ↔ 랩 DB 개수', ('모델 파일', '랩 DB'), model, have)] + (
            [R.cards('모델 파일과 다르게 이어진 관계', turned, wide=True, note=TURNED_NOTE)] if turned else []) + (
            [R.cards('스키마는 날짜인데 랩 DB에 글자로 들어간 값', dated, wide=True, note=DATED_NOTE)] if dated else []) + (
            [R.cards('모델 파일과 값이 다른 노드', gap, wide=True,
                     note='모델 파일은 스키마대로 옮긴 인스턴스 데이터입니다. 원자료 표의 줄을 내 쿼리로 넣은 종류는 식별자로 쓴 열과 열 → 속성 짝이 스키마와 같아야 모델 파일과 같은 노드가 됩니다. 고친 뒤에는 python run.py reset으로 넣은 것을 비우고 다시 넣습니다.')] if gap else []) + (
            [R.cards('모델보다 적게 들어간 관계', [dict(title=k, badge=f'모델 {v}개 → 랩 DB {h}개', state='bad', icon='warn') for k, v, h, _ in rows if k in short],
                     note='관계는 양 끝 노드를 찾았을 때만 만들어집니다. 끝 노드를 찾지 못한 줄은 오류 없이 빠지므로, 넣은 뒤에는 개수를 모델과 견줍니다. 끝 노드를 넣는 쿼리가 있는지, 관계 쿼리가 끝 노드를 무엇으로 찾는지 봅니다.')] if short else []) + seek_cards() + (
            [R.around_figure(f'랩 DB에 들어간 그래프의 한 부분 — 「{roots[0]}」에서 두 걸음', inside, roots[0])] if roots else []) + (query_pairs() if STUDENT else []) + [
            R.folded(R.table('적재 쿼리마다 넘긴 행과 바뀐 것', ['쿼리', '넣을 것', '넘긴 행', '바뀐 것'], done)),
            R.folded(R.table('모델 파일 ↔ 랩 DB 개수', ['항목', '모델 파일', '랩 DB', '견줌'], rows))] + browser()


def again(previous):
    first = db(C.export_graph)
    load_once()
    second = db(C.export_graph)
    moved = C.diff_graphs(first, second)
    n1, n2 = R.graph_counts(first), R.graph_counts(second)
    back = {}
    for i, k, was, now in moved['속성 바뀐 노드']:
        back.setdefault(i, []).append((k, f'{shown(was)} → {shown(now)}'))
    kinds = {n['props'].get('id'): n['labels'][0] for n in second['nodes']}
    cards = [dict(title=str(i), kind=kinds.get(i, ''), badge='값이 바뀜', state='bad', lines=ks) for i, ks in back.items()]
    cards += [dict(title=str(i), kind=kinds.get(i, ''), badge='다시 생김', state='bad') for i in moved['늘어난 노드'][:24]]
    cards += [dict(title=str(x), badge='관계가 늘어남', state='bad') for x in moved['늘어난 관계'][:12]]
    cards += [dict(title=f'{x[0]}', badge='관계의 값이 바뀜', state='bad', lines=[(x[1], f'{shown(x[2])} → {shown(x[3])}')]) for x in moved['속성 바뀐 관계'][:12]]
    said = ' · '.join(f'{k} {len(v)}' for k, v in moved.items() if v)
    return [R.verdict('bad', '다시 넣으니 달라졌습니다 — ' + said, '아래 카드에서 무엇이 달라졌는지 봅니다.') if cards else
            R.verdict('ok', f'다시 넣어도 그대로입니다 — 노드 {n2.get("노드", 0)}개 · 관계 {n2.get("관계", 0)}개, 값도 그대로', '같은 적재를 한 번 더 실행했지만 늘어난 것도, 바뀐 값도 없습니다.'),
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
    label = {n['props']['id']: n['labels'][0] for n in graph['nodes']}
    props = {n['props']['id']: n['props'] for n in graph['nodes']}
    text_key = lambda p: 'name' if isinstance(p.get('name'), str) and p['name'] else next((k for k, x in p.items() if k != 'id' and isinstance(x, str) and x and x != p['id']), None)      # 식별자 말고 글자로 적힌 이름 — name이 있으면 name(가이드 06의 물음), 없으면 값이 식별자와 다른 첫 글자 속성
    one = next((r for r in graph['rels'] if r['type'] in schema['relations'] and text_key(props[r['a']])), None)
    if one is None:
        raise R.Stop(f'{R.rel(path)}: 실험에 쓸 관계(식별자 말고 글자 속성이 있는 시작 노드)가 모델에 없습니다.')
    A, B, T, K = label[one['a']], label[one['b']], one['type'], text_key(props[one['a']])
    name = str(props[one['a']][K])
    v = dict(a=f'{one["a"]} (실험)', b=f'{one["b"]} (실험)', name=name, other=name + ' ', none='없는 식별자 (실험)')
    before = db(C.counts)

    def run(queries):
        done, refused = db(C.tried, [(q, v) for q in queries])
        return done, refused

    def count(done, i):
        return done[i]['rows'][0][0] if len(done) > i and done[i]['rows'] else None

    cards = []

    def card(title, queries, answer, quiet):
        cards.append(dict(title=title, icon='open' if quiet else 'lock', state='warn' if quiet else 'ok', badge='오류 없이 받아 줌' if quiet else 'DB가 거절', text=answer,
                          lines=[(f'해 본 쿼리 {i}', q) for i, q in enumerate(queries, 1)]))

    q = [f'CREATE (n:{A} {{id: $a, {K}: $name}})', f'CREATE (n:{A} {{id: $a, {K}: $name}})', f'MATCH (n:{A} {{id: $a}}) RETURN count(n)']
    done, refused = run(q)
    card('CREATE로 같은 줄을 두 번 넣으면', q[:2], f'두 번째 CREATE에서 DB가 거절했습니다 — {refused}' if refused else f'두 번 다 받아 줬습니다. 같은 식별자의 노드가 {count(done, 2)}개입니다.', not refused)
    q = [f'MERGE (n:{A} {{id: $a, {K}: $name}})', f'MERGE (n:{A} {{id: $a, {K}: $other}})', f'MATCH (n:{A} {{id: $a}}) RETURN count(n)']
    done, refused = run(q)
    card(f'MERGE 패턴에 식별자 말고 {K}까지 적고, 그 값 끝에 빈칸 하나가 붙은 줄을 넣으면', q[:2],
         f'패턴 전체(식별자와 {K})가 같은 노드를 찾지 못해 새로 만들려다 DB가 거절했습니다 — {refused}' if refused else f'패턴 전체가 같은 노드를 찾지 못해 새로 만들었습니다. 같은 식별자의 노드가 {count(done, 2)}개입니다.', not refused)
    q = [f'MERGE (n:{A} {{id: $a}})', f'MERGE (n:{A} {{ID: $a}})', f'MATCH (n:{A}) WHERE n.id = $a OR n.ID = $a RETURN count(n)']
    done, refused = run(q)
    card('MERGE 패턴의 속성 이름을 id가 아니라 ID로 적으면', q[:2],
         f'DB가 거절했습니다 — {refused}' if refused else f'오류 없이 받아 줬습니다. 같은 값을 식별자로 가진 노드가 {count(done, 2)}개입니다 — 속성 이름은 대소문자가 다르면 다른 속성이라, id에 건 유일 제약이 ID는 지키지 못합니다.', not refused)
    q = [f'MERGE (a:{A} {{id: $a}})', f'MERGE (b:{B} {{id: $b}})', f'MATCH (a:{A} {{id: $a}}), (b:{B} {{id: $b}}) MERGE (b)-[:{T}]->(a)',
         f'MATCH (a:{A} {{id: $a}})-[:{T}]->(b:{B}) RETURN count(*)', f'MATCH (a:{A} {{id: $a}})<-[:{T}]-(b:{B}) RETURN count(*)']
    done, refused = run(q)
    made = done[2]['stats'].get('relationships_created', 0) if len(done) > 2 else 0
    card(f'관계 {T}의 화살표를 거꾸로({B} → {A}) 넣으면', q[2:],
         f'DB가 거절했습니다 — {refused}' if refused else f'DB는 거꾸로 그은 관계도 받았습니다(만든 관계 {made}개). 모델의 방향({A} → {B})으로 물으면 {count(done, 3)}행, 거꾸로 물으면 {count(done, 4)}행입니다 — 방향이 맞는지는 DB가 봐 주지 않습니다.', not refused)
    q = [f'MERGE (a:{A} {{id: $a}})', f'MATCH (a:{A} {{id: $a}}), (b:{B} {{id: $none}}) MERGE (a)-[:{T}]->(b)']
    done, refused = run(q)
    made = done[1]['stats'].get('relationships_created', 0) if len(done) > 1 else 0
    card('끝 노드가 아직 없는 관계를 넣으면', q[1:], f'DB가 거절했습니다 — {refused}' if refused else f'오류 없이 끝났고 만든 관계는 {made}개입니다 — 끝 노드를 찾지 못한 줄은 아무 말 없이 빠집니다.', not refused)
    after = db(C.counts)
    if after != before:
        raise RuntimeError(f'넣기 전 실험이 랩 DB의 개수를 바꿨습니다: {before} → {after}')
    quiet = sum(1 for c in cards if c['state'] == 'warn')
    return [R.verdict('info', f'다섯 가지를 랩 DB에 해 봤습니다 — DB가 거절 {len(cards) - quiet}가지 · 오류 없이 받아 줌 {quiet}가지', '내 예측과 견줍니다. 실험한 노드와 관계는 모두 되돌렸습니다.'),
            R.cards('넣는 쿼리를 이렇게 쓰면 DB는 뭐라고 할까 — 실제 답', cards, wide=True,
                    note=f'실험용 식별자 「{v["a"]}」 · 「{v["b"]}」로 실제 실행한 결과입니다. DB가 거절하는 것은 유일 제약이 지키는 것뿐이고, 오류 없이 받아 준 것은 넣는 사람이 쿼리와 개수로 확인해야 합니다. '
                         f'랩 DB의 개수는 실험 앞뒤로 같습니다(노드 {before.get("노드", 0)}개).')] + browser()


def paired(text):
    """「구성 요소=센서」처럼 두 열을 짝지은 조각들을 견줄 꼴로 — 조각은 「 · 」로만 나누고, 짝의 왼쪽 · 오른쪽 차례를 지킨 채 숫자 표기와 빈칸만 고른 뒤 조각 차례를 뗀다."""
    return sorted('='.join(numbers(x.strip()) for x in piece.split('=')) for piece in re.split(r'\s*·\s*', str(text or '').strip()) if piece.strip())


def same_answer(expected, actual):
    """볼_열이 한 열이면 same, 두 열의 짝(「=」로 이은 조각)이면 짝마다 견준다 — 값의 묶음이 같아도 짝이 다르면 다르다."""
    if '=' in str(expected) or '=' in str(actual):
        return paired(expected) == paired(actual)
    return same(expected, actual)


def ask_question(number):
    need_decided(DECIDE.get(str(number), []))
    every = expected_rows(['질문', '물을_값', '볼_열', '기대_답'], ['질문', '물을_값', '볼_열'])
    text, _ = R.read_text(HERE / 'app/features/expected.csv')
    at = dict(zip(map(id, every), [i for i, x in enumerate(text.splitlines(), 1) if x.strip() and not x.lstrip().startswith('#')][1:]))      # 기대 답 행의 편집기 줄 번호
    rows = [r for r in every if r['질문'] == str(number)]
    path = HERE / 'app/features/query.cypher'
    try:
        qs = C.questions(path)
    except RuntimeError as e:
        raise R.Stop(str(e))
    if str(number) not in qs:
        raise R.Blank(f'app/features/query.cypher에 「// 질문 {number}」 쿼리가 아직 없습니다.')
    line, text = qs[str(number)]
    names = sorted(set(C.PARAM.findall(text)))
    if len(names) > 1:
        raise R.Stop(f'app/features/query.cypher:{line}: 질문 {number}의 $ 자리가 {len(names)}개({", ".join(names)}) — 물을 값 하나를 $ 자리 하나로 받습니다.')
    blocks, exp, act, blanks, absent = [], [], [], 0, []
    for asked in list(dict.fromkeys(r['물을_값'] for r in rows)) or ['']:      # 같은 값은 한 번만 묻고, 그 결과의 열마다 기대 답과 견준다
        params = {names[0]: asked} if names else {}
        (_, _, cols, data), = db(C.query, path, str(number), params)
        if asked:
            head = f'쿼리가 따라간 길 — 물은 값 「{asked}」'
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
        blocks.append(R.folded(R.table(f'질문 {number} — 물은 값 「{asked}」 쿼리 결과', cols, [[shown(v) for v in row] for row in data])))
        for r in rows:
            if r['물을_값'] != asked or not r.get('볼_열'):
                continue
            wanted = [c.strip() for c in r['볼_열'].split('+')]      # 「열」 하나, 또는 결과 줄마다 두 열을 짝지어 견주는 「열+열」
            exp.append({'짝': asked + ' → ' + r['볼_열'], '답': r['기대_답']})
            missing = [c for c in wanted if c not in cols]
            if missing:      # 이 줄만 견주지 못한다 — 다른 줄은 그대로 견준다
                act.append({'짝': asked + ' → ' + r['볼_열'], '답': f'견줄 수 없음(쿼리 결과에 {" · ".join(missing)} 열이 없음)'})
                absent.append((f'app/features/expected.csv:{at[id(r)]}', r['볼_열'], ' · '.join(missing), ', '.join(cols) or '없음'))
                continue
            idx = [cols.index(c) for c in wanted]
            cell = lambda x: '없음' if x in (None, '') else shown(x)
            act.append({'짝': asked + ' → ' + r['볼_열'], '답': ' · '.join('='.join(cell(row[i]) for i in idx) for row in data) or '0줄'})
            blanks += sum(1 for row in data for i in idx if row[i] == '')
    if absent:
        blocks.insert(0, R.cards('기대 답의 볼_열이 쿼리 결과에 없습니다', [dict(title=where, badge=f'없는 열: {lost}', state='bad', icon='warn',
                                 lines=[('기대 답이 보려는 열', wanted), ('쿼리가 돌려준 열', had), ('쿼리', f'app/features/query.cypher:{line}')]) for where, wanted, lost, had in absent],
                                 note='쿼리가 그 열을 돌려주게 고치거나(RETURN … AS 열 이름), 기대 답의 볼_열을 쿼리가 돌려주는 열 이름으로 맞춥니다. 다른 줄은 아래에서 그대로 견줬습니다.'))
    if exp:
        blocks.insert(0, R.compare(f'질문 {number} 기대 답 ↔ 쿼리 결과(볼_열의 값)', '짝', exp, act, ['답'], same=same_answer,
                                   note=SAME_NOTE + ' 볼_열을 「열+열」로 적은 줄은 결과 줄마다 두 열의 값을 「=」로 짝지어 견줍니다(값이 같아도 짝이 다르면 다름). ' + (f'볼_열에서 빈 글자 {blanks}칸을 값 없음(null)과 같은 「없음」으로 견줬습니다. 쿼리가 값이 없는 칸을 빈 글자로 바꾸고 있습니다 — 값 없음은 null로 돌려주는 편이 다른 쿼리와 섞이지 않습니다.' if blanks else '')))
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
    path = HERE / 'app/features/update.cypher'
    _, model = C.model_graph()
    schema = db(C.schema_in_use)
    first, missing = db(C.apply_changes, path)
    after = db(C.export_graph)
    again = db(C.apply_changes_tried, path)
    save_json('before_update.json', model)
    save_json('after_update.json', after)
    d = C.diff_graphs(model, after)
    d2 = C.diff_graphs(after, again)
    rows = [(k, len(v), ' · '.join(str(x if not isinstance(x, tuple) else f'{x[0]} {x[1]}: {x[2]} → {x[3]}') for x in v[:12]) + (' …' if len(v) > 12 else '')) for k, v in d.items()]
    same = all(not v for v in d2.values())
    old = {n['props'].get('id'): n for n in model['nodes']}
    new = {n['props'].get('id'): n for n in after['nodes']}
    moved = {}
    for i, k, was, now in d['속성 바뀐 노드']:
        moved.setdefault(i, []).append((k, f'{shown(was)} → {shown(now)}'))
    off = db(C.against_schema, after, schema)      # 반영한 뒤의 값을 스키마에 대어 본다(스키마에 없는 속성 · 자료형 · 목록에 겹친 값)
    off += [(i, k, f'자료형이 다름(스키마 date — 랩 DB에는 {kind})', after_value(after, i, k)) for _, k, i, kind in db(C.date_gap)]      # 글자로 들어간 날짜는 내보낸 글로는 가를 수 없어 랩 DB에 묻는다
    cards = [dict(title=i, kind=new[i]['labels'][0], badge='값 바뀜', state='warn', lines=ks) for i, ks in moved.items()]
    cards += [dict(title=str(i), kind=old[i]['labels'][0], badge='사라짐', state='bad', text=str(old[i]['props'].get('name') or old[i]['props'].get('tag') or '')) for i in d['사라진 노드'][:24]]
    cards += [dict(title=str(i), kind=new[i]['labels'][0], badge='새로 생김', state='ok', text=str(new[i]['props'].get('name') or new[i]['props'].get('tag') or '')) for i in d['늘어난 노드'][:24]]
    touched = set(moved) | set(d['사라진 노드']) | set(d['늘어난 노드'])
    applied, per_line = [], {}
    for line, name, how, done in first:      # 수정본 줄마다, 그 줄을 받은 쿼리들이 DB에서 바꾼 것
        for n, row, stats in done:
            applied.append((f'{name}:{n}', how, R.rel(path) + f':{line}', changed(stats)))
            per_line.setdefault((name, n, how), []).append(stats)
    idle = [(f'{name}:{n}', how) for (name, n, how), stats in per_line.items() if not any(stats)]
    rows_all = db(C.change_rows)
    lost = [(name, how, len(rows_all[(name, how)])) for name, how in missing]

    def side(title, data, gone, born):
        nodes = []
        for n in data['nodes']:
            i = n['props'].get('id')
            if i in touched:
                one = R.graph_node(n, mark='gone' if i in gone else 'new' if i in born else 'ask' if i in moved else '')
                if i in moved:      # 바뀐 속성의 그때 값을 노드 아래 글로
                    one['sub'] = ' · '.join(f'{k}: {shown(n["props"].get(k))}' for k, _ in moved[i])
                nodes.append(one)
        return R.graph(title, nodes[:16], [R.edge(r['a'], r['b'], r['type']) for r in data['rels'] if r['a'] in touched and r['b'] in touched],
                       marks=dict(ask='값이 바뀐 노드', gone='수정 뒤 사라지는 노드', new='새로 생긴 노드'))

    left, right = side('넣은 직후', model, set(d['사라진 노드']), set()), side('수정본 반영 뒤', after, set(), set(d['늘어난 노드']))
    counted = f'값이 바뀐 노드 {len(moved)}개 · 사라진 노드 {len(d["사라진 노드"])}개 · 늘어난 노드 {len(d["늘어난 노드"])}개'
    good = same and not lost and not off
    detail = ' '.join(x for x in ['같은 수정을 한 번 더 실행해도 더 바뀐 것이 없습니다.' if same else '같은 수정을 한 번 더 실행하면 또 바뀝니다 — 값을 덧붙이거나 새로 만드는 쿼리가 있는지 봅니다.',
                                  f'아직 쿼리가 없는 수정본 줄 {sum(n for _, _, n in lost)}개.' if lost else '', f'스키마와 맞지 않는 값 {len(off)}개.' if off else ''] if x)
    return [R.verdict('ok' if good else 'warn', '수정본 반영 — ' + counted, detail),
            R.cards('바뀐 노드 — 넣은 직후 → 지금', cards, note='모델 파일대로 넣은 직후와 지금 랩 DB를 견준 것입니다. 수정본의 줄과 하나씩 견줍니다.') if cards else R.note('모델 파일대로 넣은 직후와 견줘 노드의 값 · 개수에 바뀐 것이 없습니다.')] + (
            [R.cards('스키마와 맞지 않는 값', [dict(title=f'{i}의 {k}', badge=what, state='bad', icon='warn', lines=[('지금 값', shown(v))]) for i, k, what, v in off[:24]],
                     note='스키마에 없는 속성은 그 자리를 먼저 정한 뒤에 넣습니다(남길 값이면 app/features/schema_additions.csv에 그 속성을 적고, 아니면 쿼리에서 뺍니다). '
                          '수정본의 값은 모두 글자로 넘어오므로 수로 담을 값은 쿼리에서 수로, 날짜로 담을 값은 날짜로(date(…)) 바꿔 넣고, 목록에는 이미 있는 값을 다시 더하지 않습니다. '
                          '쿼리를 고친 뒤에도 앞서 들어간 값이 남아 있으면 python run.py reset으로 넣은 직후로 되돌리고 다시 반영합니다.')] if off else []) + (
            [R.cards('아직 쿼리가 없는 수정본 줄', [dict(title=f'{name} · {how}', badge=f'{n}줄', state='bad', icon='warn') for name, how, n in lost],
                     note='수정본의 이 줄들은 어느 쿼리도 받지 않아 그래프에 반영되지 않았습니다. 지우지 않고 남기기로 한 줄도, 남긴다는 것을 그래프에 적는 쿼리가 있어야 합니다.')] if lost else []) + (
            [R.cards('DB에서 아무것도 바꾸지 않은 수정본 줄', [dict(title=where, badge=how, state='warn', icon='warn') for where, how in idle],
                     note='이 줄을 받은 쿼리가 맞는 노드를 찾지 못했거나, 이미 반영돼 있어 바꿀 것이 없었습니다. 처음 반영인데 여기 나오면 쿼리가 그 줄의 대상을 무엇으로 찾는지 봅니다.')] if idle else []) + (
            [R.pair('바뀐 노드를 넣은 직후와 지금으로 나란히', left, right, note='굵은 테두리 = 값이 바뀐 노드(아래 글 = 그때의 값), 점선 = 수정 뒤 사라지는 노드. 16개까지만 그립니다.')] if d['사라진 노드'] or d['늘어난 노드'] else []) + ([R.count_bars('넣은 직후 ↔ 지금 개수', ('넣은 직후', '지금'), R.graph_counts(model), R.graph_counts(after))]
                                      if len(model['nodes']) != len(after['nodes']) or len(model['rels']) != len(after['rels']) else []) + [
            R.folded(R.table('수정본 줄마다 받은 쿼리와 이번 실행에서 DB가 바꾼 것', ['수정본 줄', '변경', '쿼리', '바뀐 것'], applied)),
            R.folded(R.table('넣은 직후 → 지금', ['바뀜', '개수', '대상'], rows)),
            R.folded(R.counts('지금 개수', [('노드', len(after['nodes'])), ('관계', len(after['rels']))])),
            R.raw('같은 수정을 한 번 더 실행해 본 결과(랩 DB에는 남기지 않음)', '같은 수정을 한 번 더 실행: ' + ('더 바뀐 것 없음' if same else '또 바뀜 — ' + '; '.join(f'{k} {len(v)}' for k, v in d2.items() if v)))] + browser()

def sources(previous):
    path, counts = graph_counts()
    _, model = C.model_graph()
    files = [(p.name, len(R.read_table(p))) for p in sorted((HERE / 'data').glob('*.csv'))]
    return [R.verdict('info', f'사용할 모델에 노드 {counts["노드"]}개 · 관계 {counts["관계"]}개가 있습니다', f'{R.rel(path)} · 원자료 표 {len(files)}개'),
            R.class_map('사용할 모델 — 종류마다 인스턴스 수와 관계', model, note='상자 = 종류(클래스), 오른쪽 수 = 인스턴스 수, 화살표의 글 = 관계 이름과 수.'),
            R.counts('원자료 파일마다 행 수', files),
            R.folded(R.counts('사용할 모델: ' + R.rel(path), sorted(counts.items())))]


def prepare(previous):
    from app.utils import db as local_db
    local_db.prepare()
    return start(previous)


def save_json(name, value):
    folder = HERE / 'output'
    folder.mkdir(exist_ok=True)
    (folder / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def export(previous):
    graph = db(C.export_graph)
    save_json('graph.json', graph)
    save_json('schema.json', db(C.schema_in_use))      # 모델의 스키마에 내가 더한 속성(app/features/schema_additions.csv)을 얹은 것
    return [R.verdict('ok', f'랩 DB의 그래프를 저장했습니다 — 노드 {len(graph["nodes"])}개 · 관계 {len(graph["rels"])}개', 'output/schema.json(종류와 관계) · output/graph.json(노드와 관계)'),
            R.class_map('저장한 그래프 — 종류마다 노드 수와 관계', graph)]


# 수정본 파일마다 견줄 원본 표와, 같은 줄을 알아보는 열
CHANGE_BASE = {'equipment_changes.csv': ('equipment.csv', ['설비코드']), 'sensor_changes.csv': ('sensors.csv', ['설비코드', '태그']),
               'part_alias_changes.csv': ('part_aliases.csv', ['사내품번', '다른표기'])}


def changes(previous):
    """수정본 살펴보기 — 수정본의 줄마다 원본의 같은 줄과 견줘 무엇이 바뀌는지 보이고, 내가 정할 지점이 정해졌는지 보인다. 랩 DB는 건드리지 않는다."""
    paths = {p.name: p for p in sorted((HERE / 'data/changes').glob('*/*.csv'))}
    cards, kinds = [], {}
    for (name, how), items in sorted(C.change_rows().items()):
        base_name, keys = CHANGE_BASE.get(name, (None, []))
        base = list(enumerate(R.read_table(HERE / 'data' / base_name), 2)) if base_name else []
        for n, row in items:
            kinds[how] = kinds.get(how, 0) + 1
            old = next(((i, b) for i, b in base if keys and all(b.get(k) == row.get(k) for k in keys)), None)
            lines = [('수정본 줄', f'{R.rel(paths[name])}:{n}'), ('원본의 같은 줄', f'data/{base_name}:{old[0]}' if old else '원본에 없는 줄')]
            if how == '수정' and old:
                lines += [(k, f'{old[1].get(k) or "없음"} → {v or "없음"}') for k, v in row.items() if k not in ('변경', '비고') and old[1].get(k, '') != v]
            elif not old:
                lines += [(k, v) for k, v in row.items() if k not in ('변경', '비고', *keys) and v]
            if row.get('비고'):
                lines.append(('비고', row['비고']))
            cards.append(dict(title=' · '.join(row.get(k, '') for k in keys) or name, badge=how, state={'추가': 'ok', '삭제': 'bad'}.get(how, 'warn'), lines=lines))
    path = HERE / 'app/features/decisions.csv'
    chosen = {(r.get('지점') or '').strip(): r for r in R.read_table(path)}
    points = DECIDE.get('update', [])
    done = [p for p in points if (chosen.get(p, {}).get('고른_것') or '').strip() not in ('', '미결')]
    decide = [dict(title=p, badge='정함' if p in done else '아직 정하지 않음', state='ok' if p in done else 'warn', icon='ok' if p in done else 'warn',
                   lines=[('고른 것', chosen[p]['고른_것']), ('근거', chosen[p].get('근거', '')), ('바뀌는 답', chosen[p].get('바뀌는_답', ''))] if p in done else []) for p in points]
    return [R.verdict('info', f'수정본 {sum(kinds.values())}줄 — ' + ' · '.join(f'{k} {v}줄' for k, v in sorted(kinds.items())), f'내가 정할 것 {len(points)}곳 가운데 {len(done)}곳을 정했습니다.'),
            R.cards('수정본의 줄마다 — 원본과 견준 것', cards, wide=True, note='「수정」은 원본의 같은 줄에서 값이 달라진 열만 「전 → 뒤」로 보입니다. 「삭제」는 그 담당의 목록에서 빠진 줄이고, 그래프에서 어떻게 할지는 내가 정합니다.'),
            R.cards('내가 정할 것', decide, wide=True, note='정한 것은 app/features/decisions.csv에 있습니다. 수정본 반영(python run.py update)은 이 결정이 다 찬 뒤에 실행됩니다.')]


def reset(previous):
    """넣은 직후로 되돌리기 — 이 폴더 랩 DB의 노드와 관계를 모두 지우고(유일 제약은 그대로) 모델을 다시 넣는다. 수정본으로 바뀐 것과 잘못 들어간 값이 모두 사라진다."""
    before = db(C.counts)
    db(C.clear)
    done, missing = load_once()
    _, model = graph_counts()
    have = db(C.counts)
    differ = [k for k, v in sorted(model.items()) if v != have.get(k, 0)]
    return [R.verdict('bad', f'되돌렸지만 모델 파일과 개수가 다른 항목 {len(differ)}개', ' · '.join(differ[:6]) + ' — python run.py load의 화면에서 내 적재 쿼리를 봅니다.') if differ else
            R.verdict('ok', f'랩 DB를 넣은 직후로 되돌렸습니다 — 노드 {have.get("노드", 0)}개 · 관계 {have.get("관계", 0)}개', '수정본으로 바뀐 값과 지운 것이 모두 모델 파일대로 돌아왔습니다. 유일 제약은 그대로 걸려 있습니다.'),
            R.count_bars('되돌리기 전 ↔ 되돌린 뒤 개수', ('되돌리기 전', '되돌린 뒤'), before, have),
            R.folded(R.table('다시 넣은 쿼리마다 넘긴 행과 바뀐 것', ['쿼리', '넣을 것', '넘긴 행', '바뀐 것'], done))] + browser()


# 이 랩의 구조 검사는 스키마에 없는 속성 · 목록에 겹친 값 · 「적어도 하나」도 본다(build_session2_projects.CHECK_MORE)
CHECKS = CHECKS[:5] + [('스키마에 없는 속성이 들어가지 않았다', '정의되지 않은 속성'), ('목록 속성에 같은 값이 두 번 들어가지 않았다', '같은 값이 두 번')] + CHECKS[5:9] + [
    ('「적어도 하나」로 정한 관계가 빠진 노드가 없다', '적어도 하나')] + CHECKS[9:]


def check(previous):
    return run_check()


COMMANDS = {
    'sources': ('원자료와 모델', sources), 'db': ('랩 DB 준비', prepare), 'status': ('모델과 DB 개수', start),
    'expected': ('기대 답', expected), 'constraints': ('유일 제약 걸기', constraints), 'probe': ('넣기 전 실험', probe), 'load': ('모델 적재', load), 'repeat': ('같은 적재 다시 실행', again),
    'sensors': ('설비별 센서', q1), 'parts': ('설비별 교체 부품', q2), 'usage': ('부품의 사용 설비', q3),
    'changes': ('수정본 살펴보기', changes), 'update': ('수정본 반영', change), 'reset': ('넣은 직후로 되돌리기', reset),
    'export': ('그래프 저장', export), 'check': ('구조 검사', check),
}
