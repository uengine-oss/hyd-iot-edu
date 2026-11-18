"""그래프 프로젝트의 제공 실행 코드. 적재·조회·수정의 판단 문장은 학생 파일에서 읽는다."""
import session2_project as P


def db_source():
    return (P.HERE / 'lab_db.py').read_text(encoding='utf-8').replace(
        'Path(__file__).resolve().parent', 'Path(__file__).resolve().parents[2]').replace('랩_연결.json', '.lab_connection.json')


def renamed(text, pairs):
    """통합반 그래프 랩의 화면 · 멈춤 문구를 이론이 세운 이름으로 바꾼다. 바꿀 글이 원본에 꼭 한 번 있어야 한다(원본이 바뀌면 여기서 멈춘다)."""
    for old, new in pairs:
        if text.count(old) != 1:
            raise ValueError(f'바꿀 글이 {text.count(old)}번 나옵니다: {old}')
        text = text.replace(old, new)
    return text


# 과정 용어 장부의 이름 — 「쿼리」 하나(조회 · 문장으로 달리 부르지 않는다), MERGE의 패턴에 적는 식별자. 실전반 랩은 이 바꿈을 거치지 않는다(다시 만들 때 함께 맞춘다).
CYPHER_TERMS = [
    ('실행할 문장이 없습니다. 현재 기능의 문장을 작성한 뒤 실행합니다.', '실행할 쿼리가 없습니다. 현재 기능의 쿼리를 작성한 뒤 실행합니다.'),
    ('전체를 지우는 문장은 이 랩에서 실행하지 않습니다.', '전체를 지우는 쿼리는 이 랩에서 실행하지 않습니다.'),
    ('$ 자리가 있는 문장입니다 — 조회 기능에서 {path} --param 이름=값 으로 실행합니다.', '$ 자리가 있는 쿼리입니다 — 수정 쿼리에는 $ 자리를 쓰지 않고 값을 직접 적습니다.'),   # 이 랩에서 $ 자리 없이 실행하는 파일은 update.cypher뿐이다
    ('문장 바로 위에 `// 넣을 것: <종류 또는 관계>` 주석이 한 줄 있어야 합니다(있는 종류: {", ".join(sorted(nodes))} / 관계: {", ".join(sorted(rels))}).',
     '쿼리 바로 위에 `// 넣을 것: <종류 또는 관계>` 주석이 한 줄 있어야 합니다(있는 종류: {", ".join(sorted(nodes))} / 관계: {", ".join(sorted(rels))}).'),
    ('조회 위에 `// 질문 <번호>` 주석이 없습니다.', '쿼리 위에 `// 질문 <번호>` 주석이 없습니다.'),
    ('가 질문 {nums[-1]} 조회 문장 안에 있습니다 — 질문 {nums[-1]} 조회({line}행부터) 끝에 ;가 없습니다.', '가 질문 {nums[-1]} 쿼리 안에 있습니다 — 질문 {nums[-1]} 쿼리({line}행부터) 끝에 ;가 없습니다.'),
    ('「// 질문 {number}」 조회가 없습니다(있는 번호:', '「// 질문 {number}」 쿼리가 없습니다(있는 번호:'),
]
ACTION_TERMS = [
    ("R.table('적재 문장마다 넘긴 행과 바뀐 것', ['문장', '넣을 것', '넘긴 행', '바뀐 것'], done)", "R.table('적재 쿼리마다 넘긴 행과 바뀐 것', ['쿼리', '넣을 것', '넘긴 행', '바뀐 것'], done)"),
    ("note='늘어남이 있으면 같은 대상을 알아보는 열쇠(MERGE)가 다시 실행할 때 새로 만들고 있는 것입니다.'",
     "note='늘어남이 있으면 MERGE의 패턴에 적은 것으로는 이미 있는 대상을 찾지 못해 다시 실행할 때 새로 만들고 있는 것입니다. 패턴에는 바뀌지 않는 식별자만 적습니다.'"),
    ("「// 질문 {number}」 조회가 아직 없습니다.", "「// 질문 {number}」 쿼리가 아직 없습니다."),
    ("f'질문 {number} 기대 답 ↔ 조회 결과(볼_열의 값)'", "f'질문 {number} 기대 답 ↔ 쿼리 결과(볼_열의 값)'"),
    ("조회가 값이 없는 칸을 빈 글자로 바꾸고 있습니다 — 값 없음은 null로 돌려주는 편이 다른 조회와 섞이지 않습니다.", "쿼리가 값이 없는 칸을 빈 글자로 바꾸고 있습니다 — 값 없음은 null로 돌려주는 편이 다른 쿼리와 섞이지 않습니다."),
    # 한 줄에서 견줄 열은 하나 — 같은 짝을 두 줄 쓰면 갈 길(다른 표기로 물은 줄)을 말한다(검토 지적: 「여러 값은 한 칸에」는 엉뚱한 길)
    ("가 두 줄입니다 — 한 짝에 한 줄만 씁니다(여러 값은 한 칸에 「 · 」로).')",
     "가 두 줄입니다 — 한 줄에서 견줄 열(볼_열)은 하나입니다. 같은 대상의 다른 열도 견주려면 그 대상을 다른 표기로 물은 줄을 더하고, 한 열의 여러 값은 한 칸에 「 · 」로 잇습니다.')"),
]


def cypher_source(integrated=False):
    """integrated = 통합반 그래프 랩이면 멈춤 문구를 장부의 이름(CYPHER_TERMS)으로 바꾼다."""
    source = (P.HERE / 'lab_cypher.py').read_text(encoding='utf-8')
    names = {'WIPE', 'PARAM', 'TARGET', 'QUESTION', 'LabDbOff', 'model_graph', 'endpoint', 'cypher', 'rows_of',
             'statements', 'guard', 'read', 'run_file', 'load_file', 'questions', 'query', 'counts', 'export_graph', 'keyed', 'diff_graphs'}
    text = ('from pathlib import Path\nimport json, re, urllib.request, urllib.error\nfrom app.utils import db as local_db\n'
            "HERE = Path(__file__).resolve().parents[2]\nSTATE = HERE / '.lab_connection.json'\n_ENDPOINT = None\n\n" + P.extract(source, names))
    text = text.replace(P.extract(source, {'endpoint'}).strip(), ENDPOINT.strip())
    text = P.convert(text).replace('랩_연결.json', '.lab_connection.json').replace('python lab_db.py', 'python run.py db')
    text = text.replace('python lab_cypher.py query', '조회 기능에서')
    text = text.replace('def guard(path, parts):\n', "def guard(path, parts):\n    if not parts:\n        raise RuntimeError(f'{path}: 실행할 문장이 없습니다. 현재 기능의 문장을 작성한 뒤 실행합니다.')\n")
    text = text.replace("    path = mine if mine.is_file() else HERE / 'data/model/graph.json'",
                        "    if mine.exists() and not mine.with_name('schema.json').is_file():\n        raise RuntimeError('app/features/model에는 schema.json과 graph.json을 함께 둡니다.')\n    path = mine if mine.is_file() else HERE / 'data/model/graph.json'")
    old = "        out[nums[-1]] = (line, s)\n"
    if text.count(old) != 1:
        raise ValueError('cypher.questions의 꼴이 바뀌었습니다 — 묻힌 질문 주석을 짚을 자리를 다시 봅니다.')
    text = text.replace(old, old + BURIED)
    return renamed(text, CYPHER_TERMS) if integrated else text


# 조회 끝에 ;가 없으면 다음 「// 질문 N」 주석이 앞 조회 문장 안에 들어간다(리허설 07 막힘 1) — 그 줄과 끝이 빠진 조회를 짚고 멈춘다.
BURIED = '''        for k, body_line in enumerate(s.splitlines()):
            m = QUESTION.match(body_line)
            if m and k:
                raise RuntimeError(f'{path}:{line + k}: 「// 질문 {m.group(1)}」가 질문 {nums[-1]} 조회 문장 안에 있습니다 — 질문 {nums[-1]} 조회({line}행부터) 끝에 ;가 없습니다.')
'''


ENDPOINT = '''
def endpoint():
    global _ENDPOINT
    if _ENDPOINT:
        return _ENDPOINT
    if not STATE.is_file():
        raise LabDbOff('랩 DB 연결이 없습니다. python run.py db로 준비합니다.')
    state = json.loads(STATE.read_text(encoding='utf-8'))
    info = json.loads(local_db.docker('inspect', state['container']))[0]
    if info['Config']['Labels'].get('hyd.practice.id') != state['id']:
        raise RuntimeError('이 폴더의 랩 DB가 아닙니다.')
    if not info['State']['Running']:
        raise LabDbOff('랩 DB가 꺼져 있습니다. python run.py db로 다시 켭니다.')
    mapping = info['NetworkSettings']['Ports']['7474/tcp'][0]
    if mapping['HostIp'] != '127.0.0.1':
        raise RuntimeError('이 폴더 전용 로컬 DB의 포트가 아닙니다.')
    _ENDPOINT = 'http://127.0.0.1:' + mapping['HostPort'] + '/db/neo4j/tx/commit'
    return _ENDPOINT
'''


def actions_source(L):
    """통합반 그래프 랩의 기능 코드(실전반 생성기는 P.actions_source와 EXTRA_ACTIONS를 따로 쓴다)."""
    text = P.actions_source(L)
    # 수정 기능은 수정과 재실행 확인만 한다. 다른 조회를 암묵적으로 실행하지 않는다.
    text = text.replace('] + ask_question(3)', ']')
    text = text.replace('처음 켠 랩 DB는 비어 있습니다(0). 적재한 뒤에는 두 칸이 같아야 합니다.',
                        '처음 만든 DB는 비어 있습니다(0). 첫 적재 뒤에는 모델과 개수를 대조합니다. 수정 뒤에는 수정본과 선택한 삭제 범위로 개수 차이를 확인합니다.')
    text = text.replace("    d = C.diff_graphs(before, after)",
                        "    save_json('before_update.json', before)\n    save_json('after_update.json', after)\n    d = C.diff_graphs(before, after)")
    text = text.replace("'수정 전 → 수정 뒤(적재 직후와 견줌)'", "'수정 전 → 수정 뒤'")
    return renamed(text, ACTION_TERMS) + EXTRA_ACTIONS


EXTRA_ACTIONS = '''
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
    (folder / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')


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
'''
