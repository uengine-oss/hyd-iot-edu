"""실전반 2회차 그래프 랩의 정의 — 통합반 그래프 랩(build_session2_projects.build_graph)과 같은 생성 길에 얹는 것만 둔다(코딩랩 K-10).

얹는 것: 공장 규모 자료의 사실을 받는 일반 로직 둘(제공 코드 cypher.py에 덧댐), 끝의 구매팀 응용 두 단계(공급사 · 견적을 부품까지 잇는 관계 넣기 → 구매팀 질문을 쿼리로 묻기)와
그 화면 기능 둘(supply · purchase), 빈 틀의 칸 뜻, AI 경계의 한 문장, 공장 규모 자료의 사실에 맞춘 가이드 문장 몇 곳. 통합반 원본은 한 글자도 바꾸지 않고 그 글에 조각을 덧댄다 —
원본의 그 자리가 바뀌면 조용히 지나가지 않고 멈춘다. 제공 모델은 설계 랩 강사 참조(session2_factory_answers.PROVIDED_SUPPLY 갈래)의 출력이다. 강사 참조 답은 이 파일 끝의 함수들이다.
"""
import session2_factory_answers as FA

TITLE = '설계한 온톨로지를 그래프 DB에 구현하고 검증하기'
LATER = ('공급사-견적', '견적-부품')      # 구매팀 질문 단계에서 학생의 쿼리로 넣는 관계(두 클래스의 짝 — 관계 이름은 스키마의 links에서 읽는다)
QUESTION = '이 부품을 기준일에 어느 공급사에서 어떤 조건(승인 상태 · 단가 · 불량률 · 납기)으로 살 수 있는가? 다른 표기나 원자료에 없는 품번으로 물으면 어떻게 구별되는가?'


def replaced(text, pairs, what):
    for old, new in pairs:
        if text.count(old) != 1:
            raise ValueError(f'{what}의 그 자리가 바뀌었습니다({text.count(old)}번 나옴) — 실전반 덧댐을 다시 봅니다: ' + old[:70])
        text = text.replace(old, new)
    return text


# ───────────── 제공 코드(app/utils/cypher.py) — 통합반 판(session2_graph_project.cypher_source(integrated=True))의 새 구조 글에 덧댄다 ─────────────
CYPHER_PATCHES = [
    # 뒤 단계에서 내 쿼리로 넣는 관계는, 그 쿼리를 쓰기 전에는 지금 쓰는 모델에서 뺀다(개수 견줌 · 수정본 견줌이 아직 넣지 않은 관계를 어긋남으로 세지 않게)
    ("    return path, json.loads(path.read_text(encoding='utf-8-sig'))\n",
     "    graph = json.loads(path.read_text(encoding='utf-8-sig'))\n"
     "    wait = waiting(path)\n"
     "    if wait:      # 뒤 단계에서 내 쿼리로 넣는 관계 — 그 쿼리를 쓰기 전에는 지금 쓰는 모델에서 뺀다\n"
     "        graph = dict(graph, rels=[r for r in graph['rels'] if r['type'] not in wait])\n"
     "    return path, graph\n"),
    # 원자료 표의 줄을 그대로 넘길 때, 모델이 담지 않은 줄(설계에서 빼기로 한 줄)은 넘기지 않는다
    ("        table = raw_rows(name)\n",
     "        table = kept_rows(label, name, nodes.get(label, []))[0]\n"),
]
CYPHER_MORE = '''

LATER = %r      # 구매팀 질문 단계에서 내 쿼리로 넣는 관계(두 클래스의 짝 — 관계 이름은 스키마의 links에서 읽는다)


def later_names(path=None):
    """LATER의 관계 이름들(지금 쓰는 모델의 스키마에서). 공급사 · 견적을 담지 않은 모델이면 빈 목록."""
    if path is None:
        mine = HERE / 'app/features/model/graph.json'
        path = mine if mine.is_file() else HERE / 'data/model/graph.json'
    links = json.loads(path.with_name('schema.json').read_text(encoding='utf-8-sig')).get('links') or {}
    return [links[x] for x in LATER if x in links]


def waiting(path=None):
    """LATER 가운데 app/features/load.cypher에 아직 `// 넣을 것:` 쿼리가 없는 관계 이름들."""
    plan = HERE / 'app/features/load.cypher'
    lines = plan.read_text(encoding='utf-8-sig', errors='replace').splitlines() if plan.is_file() else []
    written = {m.group(1) for m in (TARGET.match(x) for x in lines) if m}
    return [n for n in later_names(path) if n not in written]


def kept_rows(label, name, nodes=None):
    """원자료 표의 줄 가운데 지금 쓰는 모델이 담은 줄만 — 스키마의 식별자 틀로 지은 식별자가 모델의 그 종류에 있는 줄. 돌려주는 것: (넘길 줄, 모델에 없어 넘기지 않은 줄의 편집기 줄 번호).
    모델을 설계할 때 담지 않기로 한 원자료 줄을 적재 쿼리가 다시 넣지 않게 한다. 식별자 틀이 스키마에 없으면 줄을 모두 넘긴다."""
    path, graph = model_graph()
    table = raw_rows(name)
    if nodes is None:
        nodes = [n['props'] for n in graph['nodes'] if n['labels'][0] == label]
    template = (json.loads(read(path.with_name('schema.json'))).get('identity') or {}).get(label)
    if not template:
        return table, []
    have = {n.get('id') for n in nodes}
    made = [re.sub(r'\\{([^}]*)\\}', lambda m: row.get(m.group(1), ''), template) for row in table]
    return [row for row, i in zip(table, made) if i in have], [n for n, i in enumerate(made, 2) if i not in have]
''' % (list(LATER),)


def cypher_source(base):
    return replaced(base, CYPHER_PATCHES, '그래프 랩 제공 코드(cypher.py)') + CYPHER_MORE


# ───────────── 화면 기능(app/utils/actions.py) — 통합반 판(session2_graph_project.actions_source) 뒤에 붙는다 ─────────────
ACTION_PATCHES = [("STUDENT = ['Asset', '설비-구성 요소', '구성 요소-부품']", "STUDENT = ['Asset', '설비-구성 요소', '구성 요소-부품', *C.LATER]")]
ACTION_MORE = '''

def later_note():
    """아직 넣지 않은 뒤 단계 몫의 관계를 사실로 알린다."""
    wait = db(C.waiting)
    return [R.note('공급사와 견적, 견적과 부품을 잇는 관계(' + ' · '.join(wait) + ')는 구매팀 질문 단계에서 내 쿼리로 넣습니다. 그때까지 이 화면의 개수 견줌에는 넣지 않습니다.')] if wait else []


def raw_note():
    """원자료 표의 줄 가운데 지금 쓰는 모델이 담지 않아 내 쿼리로 넘기지 않은 줄."""
    out = []
    for label, name in RAW.items():
        rows, skipped = db(C.kept_rows, label, name)
        if skipped:
            out.append(R.note(f'data/{name}의 {len(rows) + len(skipped)}줄 가운데 지금 쓰는 모델이 담은 {len(rows)}줄만 {label} 쿼리로 넘겼습니다. 모델에 없어 넘기지 않은 줄: '
                              + ' · '.join(f'data/{name}:{n}' for n in skipped) + ' — 모델을 설계할 때 담지 않기로 한 줄입니다.'))
    return out


def supply(previous):
    """구매팀 질문 단계의 넣기 — 내 적재 쿼리 가운데 공급사와 견적, 견적과 부품을 잇는 관계 쿼리만 실행한다(앞에서 넣은 것과 수정본으로 고친 것은 건드리지 않는다).
    모델 파일의 그 관계 수와 랩 DB를 견주고, 같은 쿼리를 한 번 더 실행해 늘지 않는지 본다."""
    names = db(C.later_names)
    if not names:
        raise R.Stop('지금 쓰는 모델에 공급사 · 견적을 잇는 관계가 없습니다 — 공급 조건을 담지 않은 모델입니다.')
    path = HERE / 'app/features/load.cypher'
    plan = [x for x in db(C.load_plan, path, None, RAW) if x[1] in names]
    missing = [n for n in names if n not in {x[1] for x in plan}]
    if missing:
        raise R.Blank('app/features/load.cypher에 「// 넣을 것: ' + '」 · 「// 넣을 것: '.join(missing) + '」 쿼리가 아직 없습니다.')

    def run():
        out = []
        for line, target, s, rows, _ in plan:
            try:
                out.append((R.rel(path) + f':{line}', target, len(rows), changed(C.cypher([(s, {'rows': rows})])[0].get('stats', {}))))
            except C.LabDbOff as e:
                raise R.Stop(str(e))
            except RuntimeError as e:
                raise R.Stop(f'{R.rel(path)}:{line}: 실행 실패 — {e}')
        return out

    done = run()
    first = db(C.counts)
    run()
    second = db(C.counts)
    _, model = graph_counts()
    rows = [('관계 ' + n, model.get('관계 ' + n, 0), second.get('관계 ' + n, 0)) for n in names]
    differ = [k for k, v, h in rows if v != h]
    grew = [k for k, _, _ in rows if second.get(k, 0) != first.get(k, 0)]
    inside = db(C.export_graph)
    label = {n['props'].get('id'): n['labels'][0] for n in inside['nodes']}
    starts = sorted({r['a'] for r in inside['rels'] if r['type'] in names} - {r['b'] for r in inside['rels'] if r['type'] in names}, key=str)
    return [R.verdict('bad', f'모델 파일과 랩 DB의 개수가 다른 관계 {len(differ)}개', ' · '.join(differ) + ' — 아래 막대에서 어느 쪽이 모자라는지 봅니다.') if differ else
            R.verdict('bad', '같은 쿼리를 한 번 더 실행하니 관계가 늘었습니다 — ' + ' · '.join(grew), '이미 있는 관계를 찾지 못해 새로 만든 것입니다. 쿼리가 관계를 무엇으로 알아보는지 봅니다.') if grew else
            R.verdict('ok', '공급사 → 견적 → 부품이 이어졌습니다 — ' + ' · '.join(f'{k} {h}개' for k, _, h in rows), '모델 파일의 수와 같고, 같은 쿼리를 한 번 더 실행해도 늘지 않았습니다.'),
            R.bars('모델 파일 ↔ 랩 DB — 이번에 넣은 관계', ('모델 파일', '랩 DB'), rows)] + (
            [R.around_figure(f'랩 DB에서 {label.get(starts[0], "")} 「{starts[0]}」에서 두 걸음', inside, starts[0],
                             note='이번에 넣은 관계를 따라간 모습입니다. 화살표가 내가 읽은 문장(시작 → 읽는 말 → 종료)과 같은 쪽을 가리키는지 봅니다.')] if starts else []) + (
            [R.cards('모델보다 적게 들어간 관계', [dict(title=k, badge=f'모델 {v}개 → 랩 DB {h}개', state='bad', icon='warn') for k, v, h in rows if h < v],
                     note='관계는 양 끝 노드를 찾았을 때만 만들어집니다. 끝 노드를 찾지 못한 줄은 오류 없이 빠집니다. 쿼리가 양 끝을 무엇으로 찾는지 봅니다.')] if any(h < v for _, v, h in rows) else []) + seek_cards() + [
            R.folded(R.table('이번에 실행한 내 쿼리마다 넘긴 행과 바뀐 것', ['쿼리', '넣을 것', '넘긴 행', '바뀐 것'], done))] + browser()


def q4(previous):
    """구매팀 질문 — 내 질문 4 쿼리의 답을 기대 답과 견주고, 같은 값으로 내 질문 3 쿼리(쓰는 설비)를 물은 결과를 함께 보인다. 이 화면이 구매팀에 건네는 조회 결과다."""
    out = ask_question(4)
    link = browser()
    core = out[:len(out) - len(link)]
    path = HERE / 'app/features/query.cypher'
    qs = db(C.questions, path)
    asked = list(dict.fromkeys(r['물을_값'] for r in expected_rows(['질문', '물을_값', '볼_열', '기대_답'], ['질문', '물을_값', '볼_열']) if r['질문'] == '4'))
    if '3' in qs:
        names = sorted(set(C.PARAM.findall(qs['3'][1])))
        for value in asked:
            (_, _, cols, data), = db(C.query, path, '3', {names[0]: value} if names else {})
            core.append(R.table(f'같은 값 「{value}」으로 내 질문 3 쿼리에 물은 결과 — 이 부품을 쓰는 설비', cols, [[shown(v) for v in row] for row in data]))
    return core + link


def with_notes(fn, *notes):
    def run(previous):
        return fn(previous) + [b for note in notes for b in note()]
    return run


COMMANDS['supply'] = ('구매팀 질문: 공급사 · 견적 관계 넣기', supply)
COMMANDS['purchase'] = ('구매팀 질문: 공급 조건', q4)
for _name, _notes in (('db', [later_note]), ('status', [later_note]), ('load', [later_note, raw_note]), ('reset', [later_note])):
    COMMANDS[_name] = (COMMANDS[_name][0], with_notes(COMMANDS[_name][1], *_notes))
'''


def actions_source(base):
    return replaced(base, ACTION_PATCHES, '그래프 랩 화면 코드(actions.py)') + ACTION_MORE


# ───────────── 빈 틀 · 경계 ─────────────
def graph_lab():
    """실전반 그래프 랩 정의 — 통합반(build_labs.graph_integrated)과 같은 빈 틀 · 같은 결정 지점 둘에 질문 4의 칸 뜻과 적재 쿼리 머리의 두 문장을 더한다."""
    import build_labs as B
    import data_session2 as D
    import lab_frame as F
    import session2_answers as A
    D.require('실전반')
    blanks = dict(A.BLANKS_INTEGRATED)
    blanks['결과/load.cypher'] = replaced(blanks['결과/load.cypher'], [
        ('구성 요소와 부품을 잇는 관계(관계 이름과 시작 · 종료는 입력/schema.json에 있습니다).',
         '구성 요소와 부품을 잇는 관계(관계 이름과 시작 · 종료는 입력/schema.json에 있습니다). 구매팀 질문 단계에서 공급사와 견적을 잇는 관계, 견적과 부품을 잇는 관계 둘을 더 씁니다.'),
        ('(열 이름과 값이 모두 글자)', '(열 이름과 값이 모두 글자, 모델이 담지 않은 줄은 넘어오지 않음)')], '적재 쿼리 빈 틀의 머리')
    explain = replaced(A.GRAPH_EXPECT_EXPLAIN['통합반'], [('(질문 1 · 2는 설비 코드, 질문 3은 품번이나 표기)', '(질문 1 · 2는 설비 코드, 질문 3 · 4는 품번이나 표기)')], '그래프 랩 기대 답 틀의 칸 뜻')
    return dict(title=TITLE, course='실전반', kind='graph_integrated', change=True, steps=[],
                files={'결과/정한_것.csv': B.decision_template(B.GRAPH_POINTS['통합반']), '결과/기대_답.csv': F.blank_csv(A.GRAPH_EXPECT_COLUMNS, explain), **blanks})


def graph_rule(base):
    """실전반 그래프 랩의 랩별 경계 — 통합반 경계(build_session2_projects.GRAPH_RULE)의 적재 쿼리 문장에 구매팀 질문 단계의 두 쿼리를 더한다."""
    return replaced(base, [('- `app/features/load.cypher`에는 그 파일 첫머리에 적힌 쿼리 셋만 쓴다.',
                            '- `app/features/load.cypher`에는 그 파일 첫머리에 적힌 쿼리만 쓴다(처음에는 셋이고, 공급사와 견적 · 견적과 부품을 잇는 관계 쿼리 둘은 학생이 구매팀 질문 단계에서 요청했을 때 더한다).')],
                    '통합반 그래프 랩의 랩별 경계')


PURPOSE_TAIL = ' 끝에서는 같은 그래프에서 공급사와 견적을 부품까지 이어, 구매팀이 묻는 부품의 공급 조건을 쿼리로 조회합니다.'


def purpose():
    import session2_project_guides as G
    return replaced(G.GRAPH_PURPOSE, [(' 결과는 사람마다 조금씩 달라도 되고,', PURPOSE_TAIL + ' 결과는 사람마다 조금씩 달라도 되고,')], '그래프 랩 가이드의 목적 문장')


def graph_guide(model):
    """실전반 그래프 랩 가이드 단계 — 통합반 단계(session2_project_guides.graph)를 그대로 받아 공장 규모 자료의 사실만 바꾸고, 끝의 저장 · 검사 앞에 구매팀 응용 두 단계를 둔다.
    model = 제공 모델의 인스턴스 데이터(화면에 나올 수를 원자료 줄 수와 함께 적는다)."""
    import build_labs as B
    import lab_frame as F
    import session2_project_guides as G
    steps = G.graph()
    li = lambda text: f'<li>{F.inline(text)}</li>'
    count = lambda label: sum(1 for n in model['nodes'] if n['labels'] == [label])
    raw = lambda name: len(B.numbered(name))
    swaps = {
        2: [(li('`data/model/`에 바로 쓸 모델이 있다. `schema.json`은 스키마(클래스와 관계), `graph.json`은 인스턴스 데이터다'),
             li('`data/model/`에 바로 쓸 모델이 있다. `schema.json`은 스키마(클래스와 관계), `graph.json`은 인스턴스 데이터다')
             + li('모델에는 공급사와 견적도 들어 있다. 이 둘은 구매팀의 질문을 다루는 13단계부터 쓴다')),
            ('원자료의 구성 요소는 41행인데 모델에는 40개인 까닭을 말할 수 있으면 됩니다.',
             f'원자료의 설비는 {raw("설비_대장.csv")}행인데 모델에는 {count("Asset")}개이고, 구성 요소는 {raw("구성요소_목록.csv")}행인데 {count("Component")}개, 센서는 {raw("센서_목록.csv")}행인데 {count("Sensor")}개인 까닭을 말할 수 있으면 됩니다.')],
        3: [(li('교체 부품이 없는 구성 요소는 질문 ② 답에서 뺄지, 「없음」으로 남길지도 지금 정해 두자'),
             li('교체 부품이 없는 구성 요소는 질문 ② 답에서 뺄지, 「없음」으로 남길지도 지금 정해 두자')
             + li('센서 표에는 붙은곳이 구성 요소가 아니라 「설비 전체」인 줄이 있다. 질문 ①은 구성 요소마다 붙은 센서를 묻는다. 이 줄을 답에 넣을지 뺄지도 지금 정해 두자'))],
        6: [('설비 쿼리에는 원자료 표 `data/equipment.csv`의 줄이 적힌 그대로 넘어온다. 나머지 종류와 관계는 미리 만들어 둔 코드가 모델 파일에서 넣는다',
             '설비 쿼리에는 원자료 표 `data/equipment.csv`의 줄이 적힌 그대로 넘어온다(모델이 담지 않은 줄은 넘어오지 않는다). 나머지 종류와 관계는 미리 만들어 둔 코드가 모델 파일에서 넣는다. '
             '공급사와 견적도 그때 들어가고, 그 둘을 부품까지 잇는 관계 둘만 13단계에서 내가 넣는다')],
        12: [('결과 화면 「랩 DB」 막대가 0이 아니고 12단계 뒤의 개수 그대로면 됩니다.', '결과 화면 「랩 DB」 막대가 0이 아니고 13단계 뒤의 개수 그대로면 됩니다.'),
             ('DB가 막아 주지 않아 내가 확인한 것은 무엇이었는지 말해 봅니다.',
              'DB가 막아 주지 않아 내가 확인한 것은 무엇이었는지 말해 봅니다. 구매팀 질문 때문에 그래프에 무엇을 더 이었고, 기준일을 쿼리의 어디에서 어떻게 걸렀는지도 말해 봅니다.')],
    }
    for i, pairs in swaps.items():
        body = steps[i]['body']
        for old, new in pairs:
            for a, b in ((old, new), (F.inline(old), F.inline(new))):
                if body.count(a) == 1:
                    body = body.replace(a, b)
                    break
            else:
                raise ValueError(f'통합반 그래프 가이드 {i + 1:02d}단계의 문장이 바뀌었습니다 — 실전반 덧댐을 다시 봅니다: ' + old[:50])
        steps[i]['body'] = body
    app = [
        G.section('구매팀 질문에 답할 관계 넣기: 공급사 · 견적 · 부품', [G.plan(
            '같은 그래프를 구매팀의 질문에 써 본다. 구매팀은 부품을 어느 공급사에서 어떤 조건으로 살 수 있는지를 묻는데, 랩 DB의 공급사와 견적은 아직 부품과 이어져 있지 않다. 그래서 그 둘을 부품까지 잇는 관계부터 넣는다.',
            ['보전팀의 세 질문에 답하는 그래프가 랩 DB에 있다', '공급사와 견적 노드는 07단계에서 함께 들어갔다. 공급사와 견적을 잇는 관계, 견적과 부품을 잇는 관계 둘은 아직 넣지 않았다',
             ('구매팀이 묻는 **역량 질문** ④', [QUESTION])],
            ['두 관계의 이름과 화살표가 어느 쪽을 가리키는지 `schema.json`에서 찾아 달라고 하자. 「시작 → 읽는 말 → 종료」로 읽어 말이 되는지 본다',
             '07단계에서 쓴 관계 쿼리를 떠올려 보자. 양 끝 노드는 무엇으로 찾고, 다시 넣어도 늘지 않으려면 무엇으로 이을까?',
             '`load.cypher`에 두 쿼리만 더해 달라고 하자. 앞의 쿼리 셋은 그대로 둔다', '아래 명령으로 넣자. 같은 쿼리를 한 번 더 실행해도 늘지 않는지까지 화면이 보여 준다'])],
            prompt='`load.cypher`에 쿼리 둘을 더해 줘. `data/model/schema.json`에서 공급사와 견적을 잇는 관계, 견적과 부품을 잇는 관계의 이름과 시작 · 종료를 찾아, 양 끝 노드를 레이블과 식별자로 찾아 MERGE로 이어 줘. '
                   '행은 $rows로 받고, 쿼리마다 바로 위에 `// 넣을 것: <관계 이름>`을 적어 줘. 앞의 쿼리 셋과 다른 파일은 바꾸지 마. 쓴 뒤 두 관계를 「시작 → 읽는 말 → 종료」로 읽어 줘.',
            cmd='python run.py supply', check=G.ok('맨 위에 「공급사 → 견적 → 부품이 이어졌습니다」가 나오고, 그림의 화살표가 내가 읽은 문장과 같은 쪽을 가리키면 됩니다. '
                                                 '개수가 모델과 다르거나 한 번 더 실행해 늘었다고 나오면 그 카드를 Codex에게 보여 주고 까닭부터 묻습니다.'), ai=1),
        G.section('구매팀 질문을 쿼리로 묻기: 기준일의 공급 조건', [G.plan(
            '질문 ④를 쿼리로 묻는다. 앞의 질문들과 같은 차례로, 기대 답을 먼저 정하고 쿼리를 돌려 견준다. 맞으면 이 화면이 구매팀에 건네는 조회 결과가 된다.',
            ['공급사에서 견적을 지나 부품까지 이어졌다', '견적마다 유효기한이 있고, 기준일은 현장 메모에 적혀 있다', '같은 공급사가 같은 부품에 견적을 두 번 낸 곳이 있고, 이 모델은 그 둘을 따로 담았다'],
            ['물어볼 부품 하나는 내가 고르자. 공급사가 둘 이상인 부품이면 견줄 것이 생긴다',
             '기대 답 후보를 원자료의 견적표와 승인 공급사 목록에서 근거 줄과 함께 받아 보자. 공급사와 승인 상태, 공급사와 단가처럼 줄마다 짝지어 견주게 둔다',
             '기준일에 유효기한이 지난 견적은 답에 넣을까, 뺄까? 승인 상태는 두 표 가운데 어느 쪽 것을 따를까? 구매 기준서의 줄로 물어보고 정하자',
             '그 부품의 다른 표기로 물은 줄과 원자료에 없는 품번으로 물은 줄도 하나씩 두자', '근거 줄을 한두 곳 열어 보고, 받아들인 줄만 `expected.csv`에 질문 4로 적어 달라고 하자',
             '그다음 `query.cypher`에 질문 ④만 더해 달라고 하자. 유효기한을 기준일과 어떻게 견줄지는 Codex에게 쿼리 한 줄로 풀어 달라고 하고, 내 말로 말해 보자',
             '아래 명령으로 실행하자. 「같음」이 아닌 줄은 물은 값 · 기대 답 · 실제 결과를 함께 보여 주며 까닭부터 물어보자'])],
            prompt=('구매팀 질문의 기대 답 후보를 `data/supply_terms.csv` · `data/approved_suppliers.csv`에서 찾아 근거 줄(파일:줄)과 함께 표로 보여 줘. 질문 4: ' + QUESTION + ' 부품 ○○로 물어 줘. '
                    '기준일은 현장 메모에 적힌 날이고, 승인 상태는 구매 기준서가 따르라고 한 표의 것으로 해 줘. 꼴은 `expected.csv` 빈 틀의 첫 줄을 따르고, 볼_열이 supplier+approval, supplier+price인 줄을 하나씩 두고(기대 답은 결과 줄마다 「값=값」), '
                    '같은 공급사의 유효한 견적이 둘이면 두 줄 다 적어 줘. 그 부품의 다른 표기 ○○로 물은 줄과, 원자료에 없는 품번 ○○로 물은 줄(볼_열 note, 기대 답 「원자료에 없는 품번」)도 넣어 줘. 파일은 바꾸지 마.',
                    '방금 표에서 내가 근거 줄을 열어 본 ○○ 줄은 맞았어. 표의 줄을 `expected.csv`에 질문 4로 적어 줘. 다른 파일은 바꾸지 마.',
                    '`query.cypher`에 질문 4만 더해 줘. 품번이나 다른 표기를 $ 자리 하나로 받아 그 부품의 사내 품번(part)과, 기준일에 유효기한이 남은 견적을 낸 공급사 이름(supplier), 그 견적의 승인 상태(approval) · 단가(price) · 불량률 · 납기 · 근거 줄을 돌려줘. '
                    '원자료에 없는 품번이면 note 열에 「원자료에 없는 품번」이라고 한 줄 돌려줘. 질문 1 · 2 · 3은 그대로 둬. 쓴 뒤 유효기한을 기준일과 견주는 줄이 무엇을 하는지 쉬운 말로 풀어 줘.'),
            cmd='python run.py purchase', check=G.ok('질문 ④의 모든 줄이 기대 답과 같고, 그림에 쿼리의 패턴이 부품에서 견적을 지나 공급사까지 간 길이 보이면 됩니다. 아래 표에는 같은 부품을 쓰는 설비가 함께 나옵니다. '
                                                   '공급사 한 줄을 골라 근거 줄을 열어 값이 맞는지 봅니다.'), ai=3)]
    return steps[:-1] + app + [steps[-1]]


# ───────────── 강사 참조 답(학생 폴더에 들어가지 않는다) ─────────────
def load_later_answer(schema):
    """구매팀 질문 단계에서 학생이 더하는 적재 쿼리 둘의 참조 답 — 양 끝을 레이블과 식별자로 찾아 MERGE로 잇는다."""
    lines = []
    for link in LATER:
        name = schema['links'][link]
        spec = schema['relations'][name]
        lines += [f'// 넣을 것: {name}', f"UNWIND $rows AS row MATCH (a:{spec['from']} {{id: row.a}}), (b:{spec['to']} {{id: row.b}}) MERGE (a)-[r:{name}]->(b);", '']
    return '\n'.join(lines).rstrip() + '\n'


def purchase_query(schema, as_of=True, aliases=True):
    """질문 4의 참조 쿼리 (머리 주석, 쿼리) — 품번이나 다른 표기로 부품을 찾고, 기준일에 유효기한이 남은 견적을 낸 공급사와 그 조건 · 근거 줄을 돌려준다.
    as_of=False · aliases=False = 강사 참조 시험이 보는 틀린 선택(기준일로 거르지 않음 · 사내 품번으로만 찾음)."""
    import data_session2 as D
    import session2_answers as A
    rel, prop, arrow = A.schema_names(schema)
    no, other, sname = prop('Part', '품번'), prop('Part', '다른표기'), prop('Supplier', '공급사')
    q = {c: prop('Quote', c) for c in ('유효기한', '승인상태', '단가(만원)', '불량률', '납기(일)', '견적일', '견적출처', '승인출처')}
    chain = arrow('공급사-견적', 's:Supplier', 'q:Quote', 'Supplier') + arrow('견적-부품', '', 'p', 'Quote')[2:]
    found = f"p.{no} = $part" + (f" OR $part IN coalesce(p.{other}, [])" if aliases else '')
    return ('// 질문 4 — 품번이나 다른 표기로 부품을 찾고, 기준일에 유효기한이 남은 견적을 낸 공급사와 그 조건 · 근거 줄',
            f"OPTIONAL MATCH (p:Part) WHERE {found}\n"
            f"OPTIONAL MATCH {chain}" + (f" WHERE q.{q['유효기한']} >= '{D.REF_DATE}'" if as_of else '') + "\n"
            f"RETURN p.{no} AS part, s.{sname} AS supplier, q.{q['승인상태']} AS approval, q.{q['단가(만원)']} AS price, q.{q['불량률']} AS defect_rate, q.{q['납기(일)']} AS lead_days,\n"
            f"       q.{q['견적일']} AS quote_date, q.{q['견적출처']} AS quote_source, q.{q['승인출처']} AS approval_source,\n"
            "       CASE WHEN p IS NULL THEN '원자료에 없는 품번' WHEN q IS NULL THEN '기준일에 유효한 견적 없음' END AS note\n"
            "ORDER BY supplier, quote_date;")


PURCHASE_ASK = dict(part=FA.ASKED_PART, alias='PS-4510', missing='P-PMP-SEAL-X')      # 구매팀 질문의 기대 답 예: 셋째 결정이 걸린 부품 · 기한 지난 견적이 있는 부품의 다른 표기 · 없는 품번


def live_quotes(part):
    """그 사내 품번에 기준일에 유효한 견적들 [(공급사, 승인 상태, 단가, 견적표 줄)] — 자료 생성기의 정답 구조(data_session2.TRUTH)에서 바로 센다(같은 공급사의 유효한 견적 둘은 둘 다)."""
    import data_session2 as D
    late, early = D.TRUTH['supply_modes'][D.QUOTE_MODES[0]], D.TRUTH['supply_modes'][D.QUOTE_MODES[1]]
    seen = {}
    for mode in (early, late):
        for (sup, p), v in mode.items():
            if p == part:
                seen[(sup, v['quote_line'])] = (sup, v.get('avl_status', '미등록'), '%g' % v['price_manwon'], v['quote_line'])
    return [seen[k] for k in sorted(seen)]


def purchase_expect_rows():
    """질문 4의 기대 답 줄(그래프 랩 기대 답 표의 꼴 — 질문 · 물을_값 · 볼_열 · 기대_답 · 근거)."""
    import data_session2 as D
    rows = []
    part = PURCHASE_ASK['part']
    quotes = live_quotes(part)
    where = f'입력/자료/{D.QUOTE_FILE}:' + ' · '.join(str(q[3]) for q in quotes)
    rows.append(['4', part, 'supplier+approval', ' · '.join(f'{q[0]}={q[1]}' for q in quotes), where + f' · 입력/자료/{D.AVL_FILE} 승인상태 칸'])
    rows.append(['4', part, 'supplier+price', ' · '.join(f'{q[0]}={q[2]}' for q in quotes), where + ' 단가(만원) 칸'])
    alias = PURCHASE_ASK['alias']
    (inner,) = sorted({c[0] for c in D.CROSS if c[1] == alias})
    quotes = live_quotes(inner)
    rows.append(['4', alias, 'supplier+price', ' · '.join(f'{q[0]}={q[2]}' for q in quotes),
                 f'입력/자료/품번_교차표.csv · 입력/자료/{D.QUOTE_FILE}:' + ' · '.join(str(q[3]) for q in quotes) + ' 단가(만원) · 유효기한 칸'])
    rows.append(['4', PURCHASE_ASK['missing'], 'note', '원자료에 없는 품번', '입력/자료/예비품_목록.csv · 입력/자료/품번_교차표.csv에 없음'])
    return rows


def chosen(change):
    """결정 지점 둘의 정한_것.csv 행(통합반 build_labs.graph_chosen과 같은 지점 · 같은 갈래) — 바뀌는 답의 설비 목록은 공장 규모 원자료에 적힌 그대로 센다(session2_factory_answers.usage)."""
    import build_labs as B
    import data_session2 as D
    D.require('실전반')
    retired, status = D.LAB_RETIRED
    where = B.retired_change_line()
    users = FA.usage(B.GRAPH_SHARED_PART)
    if retired not in users:
        raise ValueError(f'{B.GRAPH_SHARED_PART}를 불용 결정 설비 {retired}가 쓰지 않아 두 갈래의 바뀌는 답이 같습니다.')
    code, tag, _ = D.LAB_SENSOR_REMOVED
    gone = f'입력/자료_변경분/{D.CHANGE_DATE}_수정본/센서_변경.csv:{next(i for i, r in enumerate(D.changes()["센서_변경.csv"], 2) if r[0] == "삭제")}'
    return {'남김': [['불용 결정 설비', '상태로 남김', f'매각 전까지는 공장에 있는 설비라 기록을 지우지 않으려고 — {where}',
                    f'{B.GRAPH_SHARED_PART} 사용 설비에 {retired}이 「{status}」 상태로 남음 — 보전팀은 매각 전까지 그 설비에 어떤 예비품이 들어갔는지 그래프에서 봄'],
                   ['목록에서 빠진 센서', '상태로 남김', f'그 자리에 센서가 있었다는 것과 지금은 떼어 냈다는 것을 그래프에서 바로 보려고 — {gone}',
                    f'질문 1에서 {code}의 {tag} 줄이 「떼어 냄」 상태로 나옴(센서의 상태 속성을 스키마에 더함) — 운전은 그 자리의 값이 지금은 오지 않는다는 것을 그래프에서 봄']],
            '삭제': [['불용 결정 설비', '하위 대상과 지움', f'보전팀이 묻는 것은 지금 가동하는 설비의 예비품이라 쓰지 않을 설비는 답에서 빼려고 — {where}',
                    f'{B.GRAPH_SHARED_PART} 사용 설비가 {" · ".join(a for a in users if a != retired)} — 보전팀은 남은 설비 몫만 예비품을 준비하고, {retired}의 지난 기록은 CMMS에서 찾음'],
                   ['목록에서 빠진 센서', '지움', f'운전이 묻는 것은 지금 값이 오는 센서라 떼어 낸 센서는 답에서 빼려고 — {gone}',
                    f'질문 1에서 {code}의 {tag} 줄이 나오지 않음 — 운전은 지금 붙어 있는 센서만 받고, 떼어 낸 이력은 정비 기록에서 찾음']]}[change]
