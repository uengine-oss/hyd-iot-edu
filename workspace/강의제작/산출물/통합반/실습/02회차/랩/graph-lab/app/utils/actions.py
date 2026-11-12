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

TITLE = '설계한 온톨로지를 그래프 DB에 구현하고 검증하기'
CHANGE = True
DECIDE = {'3': ['시점과 상태'], 'update': ['불용 결정 설비']}   # 기능마다 쓰는 결정 지점(질문 번호 · update)


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
            R.note('처음 만든 DB는 비어 있습니다(0). 첫 적재 뒤에는 모델과 개수를 대조합니다. 수정 뒤에는 수정본과 선택한 삭제 범위로 개수 차이를 확인합니다.' if not any(have.values()) else
                   '이 폴더의 랩 DB에 전에 넣은 대상이 남아 있습니다 — 랩 DB 칸이 지금 개수입니다. 모델 파일 칸과 다르면 적재나 수정이 반영된 것인지 봅니다.')]


def expected(previous):
    rows = expected_rows(['질문', '물을_값', '볼_열', '기대_답', '근거'], ['질문', '물을_값'])
    return [R.table('내가 원자료에서 먼저 적은 기대 답', ['질문', '물을_값', '볼_열', '기대_답', '근거'], rows)]


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
        raise R.Blank(f'app/features/query.cypher에 「// 질문 {number}」 조회가 아직 없습니다.')
    line, text = qs[str(number)]
    names = sorted(set(C.PARAM.findall(text)))
    if len(names) > 1:
        raise R.Stop(f'app/features/query.cypher:{line}: 질문 {number}의 $ 자리가 {len(names)}개({", ".join(names)}) — 물을 값 하나를 $ 자리 하나로 받습니다.')
    blocks, exp, act, blanks = [], [], [], 0
    for r in rows or [{'물을_값': '', '볼_열': ''}]:
        params = {names[0]: r['물을_값']} if names else {}
        (_, _, cols, data), = db(C.query, path, str(number), params)
        blocks.append(R.table(f'질문 {number} — 물은 값 「{r["물을_값"]}」', cols, [[shown(v) for v in row] for row in data]))
        if r.get('볼_열'):
            if r['볼_열'] not in cols:
                raise R.Stop(f'app/features/expected.csv: 볼_열 「{r["볼_열"]}」이 질문 {number} 결과의 열({", ".join(cols)})에 없습니다.')
            i = cols.index(r['볼_열'])
            exp.append({'짝': r['물을_값'], '답': r['기대_답']})
            act.append({'짝': r['물을_값'], '답': ' · '.join('없음' if row[i] in (None, '') else str(row[i]) for row in data) or '0줄'})
            blanks += sum(1 for row in data if row[i] == '')
    if exp:
        blocks.insert(0, R.compare(f'질문 {number} 기대 답 ↔ 조회 결과(볼_열의 값)', '짝', exp, act, ['답'], same=same,
                                   note=SAME_NOTE + ' ' + (f'볼_열에서 빈 글자 {blanks}칸을 값 없음(null)과 같은 「없음」으로 견줬습니다. 조회가 값이 없는 칸을 빈 글자로 바꾸고 있습니다 — 값 없음은 null로 돌려주는 편이 다른 조회와 섞이지 않습니다.' if blanks else '')))
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
    return [R.table('수정 전 → 수정 뒤', ['바뀜', '개수', '대상'], rows),
            R.counts('수정 뒤 개수', [('노드', len(after['nodes'])), ('관계', len(after['rels']))]),
            R.note('같은 수정을 한 번 더 실행: ' + ('더 바뀐 것 없음' if same else '또 바뀜 — ' + '; '.join(f'{k} {len(v)}' for k, v in d2.items() if v)))]


def portal(previous):
    graph = db(C.export_graph)
    label = {n['props']['id']: n['labels'][0] for n in graph['nodes']}
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
    'sources': ('원자료와 모델', sources), 'db': ('랩 DB 준비', prepare), 'status': ('모델과 DB 개수', start),
    'expected': ('기대 답', expected), 'load': ('모델 적재', load), 'repeat': ('같은 적재 다시 실행', again),
    'sensors': ('설비별 센서', q1), 'parts': ('설비별 교체 부품', q2), 'usage': ('부품의 사용 설비', q3),
    'update': ('수정본 반영', change), 'compare': ('기준 지도와 비교', portal),
    'export': ('그래프 저장', export), 'check': ('구조 검사', check),
}
