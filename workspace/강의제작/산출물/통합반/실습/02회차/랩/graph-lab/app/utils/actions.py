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
            raise R.Stop(f'app/features/expected.csv:{seen[k]} · {line}: 같은 ({" · ".join(key)}) 「{" · ".join(k)}」가 두 줄입니다 — 한 줄에서 견줄 열(볼_열)은 하나입니다. 같은 대상의 다른 열도 견주려면 그 대상을 다른 표기로 물은 줄을 더하고, 한 열의 여러 값은 한 칸에 「 · 」로 잇습니다.')
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
        cards = [R.cards('구조 검사가 맞춰 본 것', items, note='구조만 봅니다. 값의 뜻과 질문별 답은 원자료와 따로 대조합니다.')]
    if not ok:
        return [R.error('python run.py check — 구조 확인 필요', text)] + cards
    made = HERE / 'output/graph.json'
    figure = [R.class_map('검사한 그래프 — 종류마다 개수와 관계', R.read_json(made))] if made.is_file() else []
    last = lines[-1] if lines else ''
    return [R.verdict('ok', '구조 검사 통과', last.split(':', 1)[1].strip() if last.startswith('구조 검사 통과') and ':' in last else '')] + cards + figure + [R.note('python run.py check\n' + text)]

import json
from app.utils import cypher as C

TITLE = '설계한 온톨로지를 그래프 DB에 구현하고 검증하기'
CHANGE = True
DECIDE = {'update': ['불용 결정 설비']}   # 기능마다 쓰는 결정 지점(질문 번호 · update)


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
    return [R.link('Neo4j Browser에서 이 랩 DB 열기', url, note='Neo4j 실습에서 쓴 것과 같은 화면이 새 탭으로 열립니다. 연결 창이 뜨면 Database user에 neo4j를 적고 Password는 비워 둔 채 Connect를 누릅니다(이 폴더 전용 랩 DB라 비밀번호가 없습니다).')] if url else []


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
            R.note('처음 만든 DB는 비어 있습니다(0). 첫 적재 뒤에는 모델과 개수를 대조합니다. 수정 뒤에는 수정본과 선택한 삭제 범위로 개수 차이를 확인합니다.' if empty else
                   '이 폴더의 랩 DB에 전에 넣은 대상이 남아 있습니다 — 랩 DB 칸이 지금 개수입니다. 모델 파일 칸과 다르면 적재나 수정이 반영된 것인지 봅니다.')] + browser()


def expected(previous):
    rows = expected_rows(['질문', '물을_값', '볼_열', '기대_답', '근거'], ['질문', '물을_값'])
    return [R.verdict('info', f'기대 답 {len(rows)}줄을 정했습니다', '쿼리 결과를 이 답과 견줍니다.'),
            question_cards(rows, lambda r: r['물을_값'] + ' → ' + r['볼_열']),
            R.table('내가 정한 기대 답', ['질문', '물을_값', '볼_열', '기대_답', '근거'], rows)]


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
                          text=(f'같은 식별자 「{first[label]}」로 노드를 두 번 만들면 → ' + ('DB가 거절' if said else 'DB가 받아 줌(노드가 둘 생김)')) if label in first else answer,
                          lines=[('DB의 답', said)] if said else []))
    after = db(C.counts)
    if after != before:
        raise RuntimeError(f'유일 제약 시험이 랩 DB의 개수를 바꿨습니다: {before} → {after}')
    opened = [c['title'] for c in cards if c['state'] == 'bad']
    return [R.verdict('warn', f'유일 제약이 없는 종류 {len(opened)}개 — ' + ' · '.join(opened), '이 종류는 같은 식별자의 노드가 둘 생길 수 있습니다.') if opened else
            R.verdict('ok', f'종류 {len(labels)}개 모두 식별자에 유일 제약이 걸렸습니다', '같은 식별자로 새로 만들면 DB가 거절합니다.'),
            R.cards('종류마다 걸린 자물쇠 — 같은 식별자로 두 번 만들 때 DB의 답', cards, note=f'종류마다 그 종류의 식별자 하나로 CREATE를 두 번 실행해 본 실제 결과입니다. 시험한 노드는 모두 되돌려 랩 DB에 남기지 않았습니다(노드 {before["노드"]}개 그대로).'),
            R.table('제약 쿼리마다 DB가 한 일', ['쿼리', '새로 건 제약'], [(R.rel(path) + f':{line}', res.get('stats', {}).get('constraints_added', 0) or '0(이미 걸려 있음)') for line, res in done]),
            R.table('랩 DB에 걸려 있는 제약(SHOW CONSTRAINTS)', ['이름', '제약 종류', '레이블', '속성'], [(name, kind, ' · '.join(labels_), ' · '.join(props)) for name, kind, entity, labels_, props in have]),
            R.table('종류마다 — 식별자의 유일 제약과, 같은 식별자로 노드를 두 번 만들 때 DB의 답', ['종류', '식별자', '유일 제약', '시험한 식별자', 'DB의 답'], rows,
                    note='모델의 종류(레이블)마다 그 종류의 식별자 하나로 CREATE를 두 번 실행해 본 실제 결과입니다. 유일 제약이 걸린 종류는 DB가 거절하고, 「없음」인 종류는 받아 줍니다. '
                         f'시험한 노드는 모두 되돌려 랩 DB에 남기지 않았습니다(노드 {before["노드"]}개 그대로).')]


def load_once():
    out = db(C.load_file, HERE / 'app/features/load.cypher')
    return [(R.rel(HERE / 'app/features/load.cypher') + f':{line}', target, n, ', '.join(f'{k} {v}' for k, v in res.get('stats', {}).items() if isinstance(v, int) and v)) for line, target, n, res in out]


def load(previous):
    done = load_once()
    _, model = graph_counts()
    have = db(C.counts)
    rows = [(k, v, have.get(k, 0), '같음' if v == have.get(k, 0) else '다름') for k, v in sorted(model.items())]
    differ = [r[0] for r in rows if r[3] == '다름']
    inside = db(C.export_graph)
    roots = sorted(set(n['props'].get('id') for n in inside['nodes']) - set(r['b'] for r in inside['rels']), key=str)
    return [R.verdict('bad', f'모델 파일과 랩 DB의 개수가 다른 항목 {len(differ)}개', ' · '.join(differ[:6])) if differ else
            R.verdict('ok', f'모델 파일과 랩 DB의 개수가 같습니다 — 노드 {have.get("노드", 0)}개 · 관계 {have.get("관계", 0)}개', '모델의 종류는 레이블이, 인스턴스는 노드가 됐습니다.'),
            R.count_bars('모델 파일 ↔ 랩 DB 개수', ('모델 파일', '랩 DB'), model, have)] + (
            [R.around_figure(f'랩 DB에 들어간 그래프의 한 부분 — 「{roots[0]}」에서 두 걸음', inside, roots[0])] if roots else []) + [
            R.class_map('랩 DB 전체 — 종류(레이블)마다 노드 수와 관계', inside),
            R.table('적재 쿼리마다 넘긴 행과 바뀐 것', ['쿼리', '넣을 것', '넘긴 행', '바뀐 것'], done),
            R.folded(R.table('모델 파일 ↔ 랩 DB 개수', ['항목', '모델 파일', '랩 DB', '견줌'], rows))] + browser()


def again(previous):
    before = db(C.counts)
    load_once()
    after = db(C.counts)
    grew = [k for k in sorted(set(before) | set(after)) if before.get(k, 0) != after.get(k, 0)]
    return [R.verdict('bad', f'다시 넣으니 개수가 달라졌습니다 — {len(grew)}개 항목', ' · '.join(f'{k} {before.get(k, 0)} → {after.get(k, 0)}' for k in grew[:6])) if grew else
            R.verdict('ok', f'다시 넣어도 그대로입니다 — 노드 {after.get("노드", 0)}개 · 관계 {after.get("관계", 0)}개', '같은 적재를 한 번 더 실행했지만 늘어난 것이 없습니다.'),
            R.count_bars('같은 적재를 한 번 더 — 앞과 뒤의 개수', ('한 번 넣은 뒤', '한 번 더 넣은 뒤'), before, after),
            R.before_after('같은 적재를 한 번 더 — 개수 전후', before, after,
                           note='늘어남이 있으면 MERGE의 패턴에 적은 것으로는 이미 있는 대상을 찾지 못해 다시 실행할 때 새로 만들고 있는 것입니다. 패턴에는 바뀌지 않는 식별자만 적습니다.')]


def load_and_again(previous):
    return load(previous) + again(previous)


def ask_question(number):
    need_decided(DECIDE.get(str(number), []))
    rows = [r for r in expected_rows(['질문', '물을_값', '볼_열', '기대_답'], ['질문', '물을_값']) if r['질문'] == str(number)]
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
    blocks, exp, act, blanks = [], [], [], 0
    inside = db(C.export_graph)
    for r in rows or [{'물을_값': '', '볼_열': ''}]:
        params = {names[0]: r['물을_값']} if names else {}
        (_, _, cols, data), = db(C.query, path, str(number), params)
        if r['물을_값']:
            walked = R.path_figure(f'쿼리가 따라간 길 — 물은 값 「{r["물을_값"]}」', inside, r['물을_값'], [v for row in data for v in row],
                                   note='물은 값(점선 테두리)에서 쿼리 결과에 나온 대상까지, 랩 DB의 관계를 따라 이어지는 길입니다.')
            blocks.append(walked or R.cards(f'쿼리가 따라간 길 — 물은 값 「{r["물을_값"]}」', [dict(title=r['물을_값'], icon='warn', state='warn', badge='랩 DB에 없음',
                                            text='이 값과 같은 식별자를 가졌거나 이 값을 속성(다른 이름 포함)으로 가진 노드가 랩 DB에 없습니다. 그래서 따라갈 길이 없습니다.')]))
        blocks.append(R.table(f'질문 {number} — 물은 값 「{r["물을_값"]}」', cols, [[shown(v) for v in row] for row in data]))
        if r.get('볼_열'):
            if r['볼_열'] not in cols:
                raise R.Stop(f'app/features/expected.csv: 볼_열 「{r["볼_열"]}」이 질문 {number} 결과의 열({", ".join(cols)})에 없습니다.')
            i = cols.index(r['볼_열'])
            exp.append({'짝': r['물을_값'], '답': r['기대_답']})
            act.append({'짝': r['물을_값'], '답': ' · '.join('없음' if row[i] in (None, '') else str(row[i]) for row in data) or '0줄'})
            blanks += sum(1 for row in data if row[i] == '')
    if exp:
        blocks.insert(0, R.compare(f'질문 {number} 기대 답 ↔ 쿼리 결과(볼_열의 값)', '짝', exp, act, ['답'], same=same,
                                   note=SAME_NOTE + ' ' + (f'볼_열에서 빈 글자 {blanks}칸을 값 없음(null)과 같은 「없음」으로 견줬습니다. 쿼리가 값이 없는 칸을 빈 글자로 바꾸고 있습니다 — 값 없음은 null로 돌려주는 편이 다른 쿼리와 섞이지 않습니다.' if blanks else '')))
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
    first = db(C.run_file, HERE / 'app/features/update.cypher')
    after = db(C.export_graph)
    db(C.run_file, HERE / 'app/features/update.cypher')
    again = db(C.export_graph)
    save_json('before_update.json', before)
    save_json('after_update.json', after)
    d = C.diff_graphs(before, after)
    d2 = C.diff_graphs(after, again)
    rows = [(k, len(v), ' · '.join(str(x if not isinstance(x, tuple) else f'{x[0]} {x[1]}: {x[2]} → {x[3]}') for x in v[:12]) + (' …' if len(v) > 12 else '')) for k, v in d.items()]
    same = all(not v for v in d2.values())
    old = {n['props'].get('id'): n for n in before['nodes']}
    new = {n['props'].get('id'): n for n in after['nodes']}
    moved = {}
    for i, k, was, now in d['속성 바뀐 노드']:
        moved.setdefault(i, []).append((k, f'{shown(was)} → {shown(now)}'))
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
                    one['sub'] = ' · '.join(f'{k}: {shown(n["props"].get(k))}' for k, _ in moved[i])
                nodes.append(one)
        return R.graph(title, nodes[:16], [R.edge(r['a'], r['b'], r['type']) for r in data['rels'] if r['a'] in touched and r['b'] in touched],
                       marks=dict(ask='값이 바뀐 노드', gone='수정 뒤 사라지는 노드', new='새로 생긴 노드'))

    left, right = side('수정 전', before, set(d['사라진 노드']), set()), side('수정 뒤', after, set(), set(d['늘어난 노드']))
    counted = f'값이 바뀐 노드 {len(moved)}개 · 사라진 노드 {len(d["사라진 노드"])}개 · 늘어난 노드 {len(d["늘어난 노드"])}개'
    return [R.verdict('ok' if same else 'warn', '수정본 반영 — ' + counted, '같은 수정을 한 번 더 실행해도 더 바뀐 것이 없습니다.' if same else '같은 수정을 한 번 더 실행하니 또 바뀌었습니다 — 아래 안내를 봅니다.'),
            R.cards('바뀐 노드 — 전 → 뒤', cards, note='식별자로 찾아 값만 고친 노드는 「값 바뀜」, 지운 노드는 「사라짐」입니다. 수정본의 줄과 하나씩 견줍니다.') if cards else R.note('노드의 값 · 개수에 바뀐 것이 없습니다.')] + (
            [R.pair('바뀐 노드를 수정 전과 뒤로 나란히', left, right, note='점선 테두리는 값이 바뀐 노드이고 아래 작은 글이 그때의 값입니다. 흐린 노드는 수정 뒤 사라지는 노드입니다. 16개까지만 그립니다.')] if touched else []) + [
            R.count_bars('수정 전 ↔ 수정 뒤 개수', ('수정 전', '수정 뒤'), R.graph_counts(before), R.graph_counts(after)),
            R.table('수정 전 → 수정 뒤', ['바뀜', '개수', '대상'], rows),
            R.counts('수정 뒤 개수', [('노드', len(after['nodes'])), ('관계', len(after['rels']))]),
            R.note('같은 수정을 한 번 더 실행: ' + ('더 바뀐 것 없음' if same else '또 바뀜 — ' + '; '.join(f'{k} {len(v)}' for k, v in d2.items() if v)))] + browser()


def portal(previous):
    """내 그래프와 기준 지도(자료의 reference_map.json — 포털 지식 지도의 한 길)를 나란히 그린다. 내 그래프는 기준 지도의 설비에서 기준 지도에 있는 관계 이름만 따라가 그린다."""
    graph = db(C.export_graph)
    ref = json.loads((HERE / 'data/reference_map.json').read_text(encoding='utf-8'))
    by = {n['props'].get('id'): n for n in graph['nodes']}
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
    name = {x['id']: f"{x['id']}({x['알아볼 값']})" for x in ref['대상']}
    theirs = R.graph('기준 지도(포털 지식 지도의 같은 길)', [R.node(x['id'], x['종류'], sub=x['알아볼 값'], props=dict(알아볼_값=x['알아볼 값'])) for x in ref['대상']],
                     [R.edge(r['시작'], r['끝'], r['관계']) for r in ref['관계']])
    return [R.verdict('info', '내 그래프와 기준 지도를 나란히 놓았습니다', f'내 그래프 노드 {len(keep)}개 · 기준 지도 노드 {len(ref["대상"])}개 — 같은 대상을 몇 개로 셌는지 견줍니다.'),
            R.pair('같은 길을 두 그래프가 어떻게 그렸나', mine, theirs, note=ref['설명'] + ' — 설비 여럿이 구성 요소 하나를 함께 가리키는지, 설비마다 따로 두었는지 식별자와 화살표로 견줍니다.'),
            R.table('내 그래프 — 기준 지도의 설비에서 시작하는 관계(시작 → 끝)', ['시작 id', '관계', '끝 id'], links,
                    note='아래 기준 지도 표와 식별자 · 관계 방향을 견줍니다.'),
            R.table('기준 지도 — 포털 지식 지도의 같은 길(시작 → 끝)', ['시작 id', '관계', '끝 id'],
                    [(name[r['시작']], f"{r['관계']}({r['화면 이름']})", name[r['끝']]) for r in ref['관계']], note=ref['설명'])] + browser()



def sources(previous):
    path, counts = graph_counts()
    _, model = C.model_graph()
    files = [(p.name, len(R.read_table(p))) for p in sorted((HERE / 'data').glob('*.csv'))]
    return [R.verdict('info', f'사용할 모델에 노드 {counts["노드"]}개 · 관계 {counts["관계"]}개가 있습니다', f'{R.rel(path)} · 원자료 표 {len(files)}개'),
            R.class_map('사용할 모델 — 종류마다 인스턴스 수와 관계', model, note='동그란 상자 하나가 종류(클래스)이고 오른쪽 위 수가 그 종류의 인스턴스 수입니다. 화살표의 글은 관계 이름과 그 관계의 수입니다.'),
            R.counts('원자료 파일마다 행 수', files),
            R.folded(R.counts('사용할 모델: ' + R.rel(path), sorted(counts.items())))]


def prepare(previous):
    from app.utils import db as local_db
    local_db.prepare()
    out = start(previous)
    return out[:1] + [R.note('이 폴더의 랩 DB를 준비했습니다.')] + out[1:]


def save_json(name, value):
    folder = HERE / 'output'
    folder.mkdir(exist_ok=True)
    (folder / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def export(previous):
    path, _ = C.model_graph()
    graph = db(C.export_graph)
    save_json('graph.json', graph)
    save_json('schema.json', json.loads(path.with_name('schema.json').read_text(encoding='utf-8-sig')))
    return [R.verdict('ok', f'랩 DB의 그래프를 저장했습니다 — 노드 {len(graph["nodes"])}개 · 관계 {len(graph["rels"])}개', 'output/schema.json(종류와 관계) · output/graph.json(노드와 관계)'),
            R.class_map('저장한 그래프 — 종류마다 노드 수와 관계', graph),
            R.counts('저장한 그래프', [('노드', len(graph['nodes'])), ('관계', len(graph['rels']))]),
            R.note('output/schema.json · output/graph.json에 저장했습니다.')]


def check(previous):
    return run_check()


COMMANDS = {
    'sources': ('원자료와 모델', sources), 'db': ('랩 DB 준비', prepare), 'status': ('모델과 DB 개수', start),
    'expected': ('기대 답', expected), 'constraints': ('유일 제약 걸기', constraints), 'load': ('모델 적재', load), 'repeat': ('같은 적재 다시 실행', again),
    'sensors': ('설비별 센서', q1), 'parts': ('설비별 교체 부품', q2), 'usage': ('부품의 사용 설비', q3),
    'update': ('수정본 반영', change), 'compare': ('기준 지도와 비교', portal),
    'export': ('그래프 저장', export), 'check': ('구조 검사', check),
}
