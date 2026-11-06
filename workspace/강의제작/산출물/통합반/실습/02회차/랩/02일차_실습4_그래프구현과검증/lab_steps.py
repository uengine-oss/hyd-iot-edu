"""설계한 온톨로지를 그래프 DB에 구현하고 검증하기 — 결과 화면의 단계(START.md 「진행 단계」와 같은 번호 · 이름). 제공 파일 — 바꾸지 않는다."""

from pathlib import Path
import re
import subprocess
import sys
import show_result as R

HERE = Path(__file__).resolve().parent


def norm(text):
    """답 글자 견주기: 「·」 · 쉼표 · 공백으로 나눈 조각을 정렬해 다시 잇는다(순서 · 띄어쓰기 차이는 같게 본다)."""
    return ' · '.join(sorted(x for x in re.split(r'[·,\s]+', str(text or '')) if x))


def expected_rows(columns, key):
    """기대 답 표의 행. key = 한 행을 가리키는 열들 — 같은 짝이 두 줄이면 결과 화면이 한 줄을 조용히 덮으므로 두 줄 번호를 대고 멈춘다."""
    path = HERE / '결과/기대_답.csv'
    rows = R.read_table(path)
    text, _ = R.read_text(path)
    lines = [i for i, x in enumerate(text.splitlines(), 1) if x.strip() and not x.lstrip().startswith('#')][1:]   # 데이터 행의 편집기 줄 번호
    seen = {}
    for line, r in zip(lines, rows):
        empty = [c for c in columns if not r.get(c)]
        if empty:
            raise R.Stop(f'결과/기대_답.csv:{line}: 빈 칸 ' + ', '.join(empty))
        k = tuple(r.get(c, '') for c in key)
        if k in seen:
            raise R.Stop(f'결과/기대_답.csv:{seen[k]} · {line}: 같은 ({" · ".join(key)}) 「{" · ".join(k)}」가 두 줄입니다 — 한 짝에 한 줄만 씁니다(여러 값은 한 칸에 「 · 」로).')
        seen[k] = line
    return rows


def run_check():
    p = subprocess.run([sys.executable, 'check.py'], cwd=HERE, capture_output=True, text=True, encoding='utf-8', errors='replace')
    text = (p.stdout + p.stderr).strip()
    return [R.note('python check.py\n' + text)] if p.returncode == 0 else [R.error('python check.py — 구조 확인 필요', text)]

import json
import lab_cypher as C

TITLE = '설계한 온톨로지를 그래프 DB에 구현하고 검증하기'
CHANGE = True


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
            R.note('처음 켠 랩 DB는 비어 있습니다(0). 적재한 뒤에는 두 칸이 같아야 합니다.')]


def expected(previous):
    rows = expected_rows(['질문', '물을_값', '볼_열', '기대_답', '근거'], ['질문', '물을_값'])
    return [R.table('내가 원자료에서 먼저 적은 기대 답', ['질문', '물을_값', '볼_열', '기대_답', '근거'], rows)]


def load_once():
    out = db(C.load_file, HERE / '결과/load.cypher')
    return [(R.rel(HERE / '결과/load.cypher') + f':{line}', target, n, ', '.join(f'{k} {v}' for k, v in res.get('stats', {}).items() if isinstance(v, int) and v)) for line, target, n, res in out]


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
    rows = [r for r in expected_rows(['질문', '물을_값', '볼_열', '기대_답'], ['질문', '물을_값']) if r['질문'] == str(number)]
    path = HERE / '결과/query.cypher'
    try:
        qs = C.questions(path)
    except RuntimeError as e:
        raise R.Stop(str(e))
    if str(number) not in qs:
        raise R.Blank(f'결과/query.cypher에 「// 질문 {number}」 조회가 아직 없습니다.')
    line, text = qs[str(number)]
    names = sorted(set(C.PARAM.findall(text)))
    if len(names) > 1:
        raise R.Stop(f'결과/query.cypher:{line}: 질문 {number}의 $ 자리가 {len(names)}개({", ".join(names)}) — 물을 값 하나를 $ 자리 하나로 받습니다.')
    blocks, exp, act = [], [], []
    for r in rows or [{'물을_값': '', '볼_열': ''}]:
        params = {names[0]: r['물을_값']} if names else {}
        (_, _, cols, data), = db(C.query, path, str(number), params)
        blocks.append(R.table(f'질문 {number} — 물은 값 「{r["물을_값"]}」', cols, [[json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v for v in row] for row in data]))
        if r.get('볼_열'):
            if r['볼_열'] not in cols:
                raise R.Stop(f'결과/기대_답.csv: 볼_열 「{r["볼_열"]}」이 질문 {number} 결과의 열({", ".join(cols)})에 없습니다.')
            i = cols.index(r['볼_열'])
            exp.append({'짝': r['물을_값'], '답': norm(r['기대_답'])})
            act.append({'짝': r['물을_값'], '답': norm(' · '.join('없음' if row[i] is None else str(row[i]) for row in data) or '0줄')})
    if exp:
        blocks.insert(0, R.compare(f'질문 {number} 기대 답 ↔ 조회 결과(볼_열의 값)', '짝', exp, act, ['답']))
    return blocks


def q1(previous):
    return ask_question(1)


def q2(previous):
    return ask_question(2)


def q3(previous):
    return ask_question(3)


def change(previous):
    before = db(C.export_graph)
    first = db(C.run_file, HERE / '결과/update.cypher')
    after = db(C.export_graph)
    db(C.run_file, HERE / '결과/update.cypher')
    again = db(C.export_graph)
    d = C.diff_graphs(before, after)
    d2 = C.diff_graphs(after, again)
    rows = [(k, len(v), ' · '.join(str(x if not isinstance(x, tuple) else f'{x[0]} {x[1]}: {x[2]} → {x[3]}') for x in v[:12]) + (' …' if len(v) > 12 else '')) for k, v in d.items()]
    same = all(not v for v in d2.values())
    return [R.table('수정 전 → 수정 뒤(적재 직후와 견줌)', ['바뀜', '개수', '대상'], rows),
            R.counts('수정 뒤 개수', [('노드', len(after['nodes'])), ('관계', len(after['rels']))]),
            R.note('같은 수정을 한 번 더 실행: ' + ('더 바뀐 것 없음' if same else '또 바뀜 — ' + '; '.join(f'{k} {len(v)}' for k, v in d2.items() if v)))] + ask_question(3)


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


STEPS = [
    dict(no=1, name='폴더와 출발점 · 랩 DB 켜기', slots=[], run=start),
    dict(no=2, name='파일을 바꾸지 않고 자료 파악', slots=[], run=None),
    dict(no=3, name='요구와 기대 답 정하기', slots=['결과/기대_답.csv'], run=expected),
    dict(no=4, name='판단① 적재 쿼리 쓰기', slots=['결과/load.cypher'], run=load),
    dict(no=5, name='같은 적재 다시 실행', slots=[], run=again),
    dict(no=6, name='판단② 설비별 센서 조회', slots=['결과/query.cypher'], run=q1),
    dict(no=7, name='판단③ 설비별 교체 부품 조회', slots=['결과/query.cypher'], run=q2),
    dict(no=8, name='판단④ 부품의 사용 설비 조회', slots=['결과/query.cypher'], run=q3),
    dict(no=9, name='판단⑤ 수정본 반영하기', slots=['결과/update.cypher'], run=change),
    dict(no=10, name='포털 기준 지도와 비교', slots=[], run=portal),
    dict(no=11, name='저장하고 다시 열기', slots=[], run=None),
]
