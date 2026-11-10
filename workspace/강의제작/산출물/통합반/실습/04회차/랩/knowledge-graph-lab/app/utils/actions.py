"""검토한 문서 지식을 그래프 DB에 반영하고 관계 확인하기 — 명령마다 한 기능을 실행해 결과를 output/result.html에 보인다. 제공 파일 — 고치지 않는다."""
from pathlib import Path
import json
from app.utils import results as R
from app.utils import graph as G

HERE = Path(__file__).resolve().parents[2]
TITLE = '검토한 문서 지식을 그래프 DB에 반영하고 관계 확인하기'
PRACTICAL = False
TASK = 'SOP-COOL-14'
LATER_DOCS = ['OEM-HPP45A-MM', 'PR-07']
ITEMS = None                     # expected.csv 질문 칸이 받는 카드 항목 이름(통합반은 None — 「질문 N」)
if PRACTICAL:                         # 실전 카드 랩: 종류마다 계약의 기본 항목, roles.csv는 다르게 둘 것만
    G.ROLE_DEFAULT.update({'precondition': '준비', 'prohibition': '금지', 'completion': '완료', 'unit_value': '완료', 'step': '순서'})


def guard(fn):
    def run(previous):
        try:
            return fn(previous)
        except G.Problem as e:
            raise R.Stop(str(e))
        except RuntimeError as e:
            if type(e).__name__ == 'LabDbOff':
                raise R.Stop(str(e) + ' Docker Desktop이 켜져 있는지 봅니다.')
            raise
    return run


def known():
    return G.model_ids()[0]


def shape():
    sh = G.shape()
    if sh is None:
        raise R.Blank('app/features/graph_shape.json이 아직 비어 있습니다.')
    return sh


def table_of(name, values, title):
    got = G.ask(name, values)
    if got is None:
        return R.note(f'{title} — app/features/query_values.csv에 {name}의 값을 아직 적지 않았습니다.')
    return R.table(title, got[0], got[1])


@guard
def look(previous):
    rows, ok = [], []
    for fname, data in G.reviews():
        n = {}
        for c in data['candidates']:
            n[c['status']] = n.get(c['status'], 0) + 1
            if c['status'] == 'approved':
                ok.append([fname, c['id'], c['section'], c.get('procedure') or '', c['kind'], c['line_start'], c['quote']])
        rows.append([fname, data['doc_id'], data.get('rev'), n.get('approved', 0), n.get('pending', 0), n.get('excluded', 0),
                     ', '.join(f'{x["rule_id"]} {x["match"]}' for x in data.get('rule_links', []))])
    ids, _, sop = G.model_ids()
    kinds = {}
    for v in ids.values():
        kinds[v] = kinds.get(v, 0) + 1
    return [R.table('검토 결과 — 문서마다 승인 · 보류 · 제외 수와 조건 근거 대조', ['파일', '문서', '판', '승인', '보류', '제외', '조건 근거'], rows),
            R.counts('기존 ID(설비 모델 · SOP 구조 · 조건표)', sorted(kinds.items())),
            R.table('승인 후보 찾아보기(적재할 것)', ['검토 파일', '후보', '절', '절차', '종류', '줄', '인용'], ok)]


def look_db(previous):
    return look(previous) + db(previous)


@guard
def expect(previous):
    rows = G.expect_rows(ITEMS)
    if not rows:
        raise R.Blank('app/features/expected.csv에 행이 없습니다.')
    out = [R.table('조회 전에 적은 기대', ['질문', '기대 답', '근거'], [[r['질문'], r['기대_답'], r['근거']] for r in rows])]
    for r in rows:                                   # 근거마다 첫 줄을 원문 그대로(글자 방식은 저절로 — 내가 적은 줄이 그 내용인지 본다)
        for f, n in G.basis_lines(r['근거'])[:1]:
            if (HERE / 'data/documents' / f).is_file():
                out.append(R.source_lines(HERE / 'data/documents' / f, n))
    return out


@guard
def db(previous):
    from app.utils import cypher as lab_cypher
    lab_cypher.model()
    c = G.counts()
    return [R.counts('랩 DB — 설비 모델과 조치 기준 적재 뒤', [('노드', c['nodes']), ('관계', c['rels'])] + sorted(c['labels'].items()))]


@guard
def plan(previous):
    sh = shape()
    p = G.preview(sh)
    out = [R.counts('승인 후보 전부를 이 모양으로 지으면(적재하지 않고 셈)', [('승인 후보', p['approved'])] + sorted(p['merges'].items())),
           R.counts('적재하지 않는 후보', sorted((k, v) for k, v in p['statuses'].items() if k != 'approved'))]
    if p['clash']:
        out.append(R.error('같은 ID에 서로 다른 대상이 겹침 — ID 짓는 꼴을 고칩니다', '\n'.join(f'{i}: {", ".join(w)}' for i, w in p['clash'][:20])))
    return out


@guard
def link(previous):
    sh = shape()
    rules = G.link_rows(known())
    if not rules:
        raise R.Blank('app/features/link_rules.csv에 잇는 방법을 정한 행이 없습니다.')
    if not G.role_rows():
        raise R.Blank('app/features/roles.csv에 행이 없습니다.')
    st = G.load_all()
    out = [R.counts('적재 전후', [('노드', st['after']['nodes']), ('관계', st['after']['rels']), ('적재한 지식', st['knowledge']), ('기존 ID에 이은 지식', st['linked'])]),
           R.table('적재한 문서', ['문서', '판'], st['docs'])]
    if st['clash']:
        out.append(R.error('같은 ID에 서로 다른 대상이 겹침', '\n'.join(f'{i}: {", ".join(w)}' for i, w in st['clash'][:20])))
    if st['notes']:
        out.append(R.note('\n'.join(st['notes'][:20])))
    cols, rows = G.linked_to(sh, TASK)
    out.append(R.table(f'핀 세척({TASK})과 그 단계에 이은 지식 — 원문 줄로 확인', ['이은 대상', '관계', '항목', '문서', '판', '절', '줄', '인용'], rows))
    for r in rules[:12]:
        for f, n in G.basis_lines(r['근거'])[:1]:
            if (HERE / 'data/documents' / f).is_file():
                out.append(R.source_lines(HERE / 'data/documents' / f, n))
    return out


@guard
def other(previous):
    shape()
    rows = G.other_rows(known())
    if not rows:
        raise R.Blank('app/features/other_doc_conditions.csv에 행이 없습니다 — 잇지 않기로 했어도 그 행을 「아니오」로 남깁니다.')
    st = G.load_all()
    vals = G.ask_values()
    out = [R.counts('다시 적재한 뒤(직전 실행과 같으면 늘지 않은 것)', [('노드', st['after']['nodes']), ('관계', st['after']['rels'])]),
           R.table('다른 문서의 조건', ['문서', '판', '절', '글자', '작업', '잇는다', '관계', '근거'], [[r['문서'], r['판'], r['절'], r['인용에_든_글자'], r['작업'], r['잇는다'], r.get('관계', ''), r['근거']] for r in rows])]
    for r in rows:
        for f, n in G.basis_lines(r['근거'])[:1]:
            if (HERE / 'data/documents' / f).is_file():
                out.append(R.source_lines(HERE / 'data/documents' / f, n))
    return out


@guard
def ask123(previous):
    sh = shape()
    vals = G.ask_values()
    if not vals:
        raise R.Blank('app/features/query_values.csv에 값이 없습니다.')
    G.write(HERE / 'output/query.cypher', G.query_file(sh, vals))
    exp = G.expect_rows(ITEMS)
    state = json.loads((HERE / '.lab_connection.json').read_text(encoding='utf-8')) if (HERE / '.lab_connection.json').is_file() else {}
    return [R.table('내 기대', ['질문', '기대 답', '근거'], [[r['질문'], r['기대_답'], r['근거']] for r in exp]),
            table_of('q1', vals, '질문 1 — 조치마다 단계 · 준비 · 금지 · 완료 · 승인과 근거'),
            table_of('q2', vals, '질문 2 — 규칙마다 근거 원문과 맞는 정도'),
            table_of('q3', vals, '질문 3 — 이 작업이 확인하는 센서(값은 그래프 밖)'),
            table_of('hold', vals, '보류 후보가 그래프에 있는가'),
            R.note('Neo4j Browser로 모양을 볼 때: ' + (state.get('browser') or '.lab_connection.json의 Browser 주소') + ' — output/query.cypher에서 그 질문의 「// Browser:」 줄의 :param부터 붙여 넣습니다. 터미널로는 「// 터미널:」 줄의 명령을 실행합니다.')]


@guard
def more(previous):
    rules = G.link_rows(known())
    have = {r['문서'] for r in rules}
    if not set(LATER_DOCS) <= have:
        raise R.Blank('app/features/link_rules.csv에 다른 문서(' + ' · '.join(LATER_DOCS) + ')의 행이 아직 없습니다.')
    st = G.load_all()
    vals = G.ask_values()
    c = st['compare']
    out = [R.counts('다른 문서 추가 전후', [('노드', st['after']['nodes']), ('관계', st['after']['rels'])])]
    if c is None:
        out.append(R.note('추가 전 내보내기가 없습니다 — 다른 문서의 행을 처음부터 함께 채워 적재했습니다(추가 전후를 견줄 기준이 없음).'))
    else:
        out.append(R.counts('추가 전 그래프와 비교', [('늘어난 노드', c['added_nodes']), ('늘어난 관계', c['added_rels']), ('속성이 바뀐 기존 노드', len(c['changed_nodes'])),
                                                 ('사라진 노드', len(c['gone_nodes'])), ('사라진 관계', len(c['lost_rels'])), ('속성이 바뀐 기존 관계', len(c['changed_rels']))]))
        if c['changed_nodes'] or c['gone_nodes'] or c['lost_rels']:
            out.append(R.table('바뀌거나 사라진 기존 것', ['무엇', 'ID'], [['속성 바뀜', x] for x in c['changed_nodes']] + [['사라진 노드', x] for x in c['gone_nodes']]
                               + [['사라진 관계', ' '.join(map(str, x))] for x in c['lost_rels']]))
    out += [table_of('q1', vals, '질문 1 — 다시'), table_of('q4', vals, '질문 4 — 더한 문서의 지식이 걸리는 대상')]
    return out


@guard
def scope(previous):
    rows = G.now_rows()
    if not rows:
        raise R.Blank('app/features/current_value_sources.csv에 행이 없습니다.')
    vals = G.ask_values()
    rq = G.remaining(vals)
    G.write(HERE / 'output/remaining_questions.json', G.dump(rq))
    kinds = {}
    for x in rq:
        kinds[x['kind']] = kinds.get(x['kind'], 0) + 1
    out = [R.table('작업 직전 확인할 현재값과 읽을 원천(그래프에 넣지 않음)', ['작업', '확인할 값', '읽을 원천', '근거'], [[r['작업'], r['확인할_값'], r['읽을_원천'], r['근거']] for r in rows]),
           R.counts('추가 자료가 필요한 질문(output/remaining_questions.json)', sorted(kinds.items()))]
    if not PRACTICAL:
        out += [table_of('q3', vals, '질문 3 — 이 작업이 확인하는 센서'), table_of('q5_target', vals, '질문 5 — 제공되지 않은 작업 · 대상'), table_of('q5_section', vals, '질문 5 — 제공되지 않은 절')]
    return out


@guard
def save(previous):
    shape()
    from app.utils import cypher as lab_cypher
    import subprocess, sys
    vals = G.ask_values()
    G.write(HERE / 'output/remaining_questions.json', G.dump(G.remaining(vals)))
    graph = G.export_graph()
    graph['remaining_questions'] = json.loads((HERE / 'output/remaining_questions.json').read_text(encoding='utf-8'))
    G.write(HERE / 'output/knowledge_export.json', G.dump(graph))
    c = G.counts()
    run = subprocess.run([sys.executable, '-m', 'app.utils.check'], capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=HERE)
    return [R.counts('내보내기(output/knowledge_export.json)', [('노드', len(graph['nodes'])), ('관계', len(graph['rels'])), ('추가 자료가 필요한 질문', len(graph['remaining_questions'])),
                                                     ('랩 DB 노드', c['nodes']), ('랩 DB 관계', c['rels'])]),
            R.note('python run.py check 출력(끝 12줄, 종료 코드 ' + str(run.returncode) + ')\n' + '\n'.join(run.stdout.strip().splitlines()))]


def prepare(previous):
    from app.utils import db as local_db
    try:
        local_db.prepare()
    except (RuntimeError, OSError) as e:
        raise R.Stop('랩 DB 꺼짐 — Docker Desktop이 켜져 있는지 보고 같은 명령을 다시 실행합니다. (' + str(e).splitlines()[0][:160] + ')')
    return (look_db if PRACTICAL else db)(previous)


@guard
def other_twice(previous):
    out = other(previous)
    first = G.counts()
    G.load_all()
    second = G.counts()
    flat = lambda c: {'노드': c['nodes'], '관계': c['rels'], **{'노드 ' + k: v for k, v in c['labels'].items()}, **{'관계 ' + k: v for k, v in c['types'].items()}}
    block = R.before_after('같은 적재를 한 번 더 실행한 전후 — 늘거나 사라진 것이 없어야 합니다', flat(first), flat(second))
    return out + [block] + ([] if block['rows'] else [R.note(f'한 번 더 적재해도 같음: 노드 {second["nodes"]} · 관계 {second["rels"]}')])


def check(previous):
    import subprocess, sys
    run = subprocess.run([sys.executable, '-m', 'app.utils.check'], capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=HERE)
    return [R.note('python run.py check 출력(종료 코드 ' + str(run.returncode) + ')\n' + run.stdout.strip())]

STEPS = [
    dict(command='expected', slots=['app/features/expected.csv']),
    dict(command='plan', slots=['app/features/graph_shape.json']),
    dict(command='load', slots=['app/features/link_rules.csv', 'app/features/roles.csv']),
    dict(command='other', slots=['app/features/other_doc_conditions.csv']),
    dict(command='query', slots=['app/features/query_values.csv']),
    dict(command='scope', slots=['app/features/current_value_sources.csv']),
]

COMMANDS = {
    'sources': ('검토 결과와 기존 ID', look),
    'expected': ('기대 답', expect),
    'db': ('랩 DB 준비와 설비 모델 적재', prepare),
    'plan': ('그래프 모양과 ID', plan),
    'load': ('승인 지식 적재', link),
    'other': ('다른 문서의 조건 · 다시 적재', other_twice),
    'query': ('질문 1~3 조회와 보류 확인', ask123),
    'more': ('다른 문서 추가 반영', more),
    'scope': ('답할 수 있는 범위', scope),
    'export': ('내보내기', save),
    'check': ('구조 검사', check),
}
