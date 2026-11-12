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
                         '원자료를 보고 고른 것과 근거 줄을 적은 뒤 다시 실행합니다. AI가 대신 고르지 않습니다.')


def run_check():
    p = subprocess.run([sys.executable, '-m', 'app.utils.check'], cwd=HERE, capture_output=True, text=True, encoding='utf-8', errors='replace')
    text = (p.stdout + p.stderr).strip()
    return [R.note('python run.py check\n' + text)] if p.returncode == 0 else [R.error('python run.py check — 구조 확인 필요', text)]

import json
from app.utils import cypher as C

TITLE = '부품의 사용 설비와 공급 정보를 조회하는 그래프 구현하기'
CHANGE = False
DECIDE = {'1': ['쓰는 사람에 따라 갈리는 답']}   # 기능마다 쓰는 결정 지점(질문 번호 · update)


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


def start(previous):
    path, model = graph_counts()
    have = db(C.counts)
    rows = [(k, v, have.get(k, 0)) for k, v in sorted(model.items())]
    return [R.table(f'모델 파일({R.rel(path)})과 지금 랩 DB의 개수', ['항목', '모델 파일', '랩 DB'], rows),
            R.note('처음 켠 랩 DB는 비어 있습니다(0). 적재한 뒤에는 두 칸이 같아야 합니다.' if not any(have.values()) else
                   '이 폴더의 랩 DB에 전에 넣은 대상이 남아 있습니다 — 랩 DB 칸이 지금 개수입니다. 모델 파일 칸과 다르면 적재나 수정이 반영된 것인지 봅니다.')]


def load_once():
    out = db(C.load_file, HERE / 'app/features/load.cypher')
    return [(R.rel(HERE / 'app/features/load.cypher') + f':{line}', target, n, ', '.join(f'{k} {v}' for k, v in res.get('stats', {}).items() if isinstance(v, int) and v)) for line, target, n, res in out]


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


def q1(previous):
    return ask_question(1)


def q2(previous):
    return ask_question(2)

def expected(previous):
    rows = expected_rows(['질문', '물을_값', '기대_답', '근거'], ['질문', '물을_값', '볼_열', '기대_답'])
    return [R.table('내가 원자료에서 먼저 적은 기대 답', ['질문', '물을_값', '볼_열', '기대_답', '근거'], rows,
                    note='볼_열은 조회를 만든 뒤 그 조회가 돌려주는 열 이름으로 채웁니다. 한 물을 값에 견줄 열이 여럿이면 볼_열마다 한 줄씩 씁니다.')]


def cell(value):
    """조회 결과 칸 하나를 견줄 글로: 값 없음은 「없음」, 목록은 「 · 」로 잇는다."""
    if value is None or value == '':
        return '없음'
    if isinstance(value, list):
        return ' · '.join(cell(v) for v in value) or '없음'
    return str(value)


def ask_question(number):
    rows = [r for r in expected_rows(['질문', '물을_값', '기대_답'], ['질문', '물을_값', '볼_열', '기대_답']) if r['질문'] == str(number)]
    path = HERE / 'app/features/query.cypher'
    try:
        qs = C.questions(path)
    except RuntimeError as e:
        raise R.Stop(str(e))
    if str(number) not in qs:
        raise R.Blank(f'app/features/query.cypher에 「// 질문 {number}」 조회가 아직 없습니다.')
    line, text = qs[str(number)]
    names = sorted(set(C.PARAM.findall(text)))
    if len(names) > 1:
        raise R.Stop(f'app/features/query.cypher:{line}: 질문 {number}의 $ 자리가 {len(names)}개({", ".join(names)}) — 물을 값 하나를 $ 자리 하나로 받습니다.')
    seen = {}
    for r in rows:
        if r.get('볼_열'):
            pair = (r['물을_값'], r['볼_열'])
            if pair in seen:
                raise R.Stop(f'app/features/expected.csv: 질문 {number}의 물을_값 「{pair[0]}」 · 볼_열 「{pair[1]}」이 두 줄입니다 — 한 열에 한 줄만 씁니다(여러 값은 한 칸에 「 · 」로).')
            seen[pair] = True
    blocks, exp, act, ran = [], [], [], {}
    for r in rows or [{'물을_값': '', '볼_열': ''}]:
        value = r['물을_값']
        if value not in ran:
            params = {names[0]: value} if names else {}
            (_, _, cols, data), = db(C.query, path, str(number), params)
            ran[value] = (cols, data)
            blocks.append(R.table(f'질문 {number} — 물은 값 「{value}」', cols, [[cell(v) for v in row] for row in data]))
        cols, data = ran[value]
        if r.get('볼_열'):
            if r['볼_열'] not in cols:
                raise R.Stop(f'app/features/expected.csv: 볼_열 「{r["볼_열"]}」이 질문 {number} 결과의 열({", ".join(cols)})에 없습니다.')
            i = cols.index(r['볼_열'])
            pair = value + ' | ' + r['볼_열']
            exp.append({'짝': pair, '답': r['기대_답']})
            values = [row[i] for row in data]
            if values and all(isinstance(v, list) for v in values) and all(v == values[0] for v in values):
                values = values[:1]   # 모아 돌려준 목록이 줄마다 되풀이되면 한 번만 견준다
            act.append({'짝': pair, '답': ' · '.join(cell(v) for v in values) or '0줄'})
    if exp:
        blocks.insert(0, R.compare(f'질문 {number} 기대 답 ↔ 조회 결과(물을 값 | 볼_열)', '짝', exp, act, ['답'], same=same,
                                   note=SAME_NOTE + ' 값 없음(null)과 빈 글자 칸은 「없음」으로 견줍니다.'))
    elif rows:
        blocks.insert(0, R.note('기대 답의 볼_열이 비어 있어 대조하지 않았습니다. 이 조회가 돌려주는 열 이름으로 볼_열을 채우면 대조합니다.'))
    return blocks

def sources(previous):
    path, counts = graph_counts()
    files = [(p.name, len(R.read_table(p))) for p in sorted((HERE / 'data').glob('*.csv'))]
    return [R.counts('원자료 파일마다 행 수', files),
            R.counts('사용할 모델: ' + R.rel(path), sorted(counts.items()))]


def prepare(previous):
    from app.utils import db as local_db
    local_db.prepare()
    return [R.note('이 폴더의 랩 DB를 준비했습니다.')] + start(previous)


def save_json(name, value):
    folder = HERE / 'output'
    folder.mkdir(exist_ok=True)
    (folder / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def export(previous):
    path, _ = C.model_graph()
    graph = db(C.export_graph)
    save_json('graph.json', graph)
    save_json('schema.json', json.loads(path.with_name('schema.json').read_text(encoding='utf-8-sig')))
    return [R.counts('저장한 그래프', [('노드', len(graph['nodes'])), ('관계', len(graph['rels']))]),
            R.note('output/schema.json · output/graph.json에 저장했습니다.')]


def check(previous):
    return run_check()


COMMANDS = {
    'sources': ('원자료와 모델', sources),
    'db': ('랩 DB 준비', prepare),
    'status': ('모델과 DB 개수', start),
    'expected': ('기대 답', expected),
    'load': ('모델 적재', load),
    'repeat': ('같은 적재 다시 실행', again),
    'usage': ('사용 설비와 공급 조건', q1),
    'aliases': ('다른 표기와 없는 품번', q2),
    'export': ('그래프 저장', export),
    'check': ('구조 검사', check),
}
