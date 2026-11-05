"""검토한 문서 지식을 그래프 DB에 반영하고 관계 확인하기 — 결과 화면의 단계(START.md 「진행 단계」와 같은 번호 · 이름). 제공 파일 — 고치지 않는다.
단계마다 정할 자리(결과/의 「제공 빈 틀」 파일)를 채웠으면 제공 코드(doc_graph.py · lab_cypher.py)를 돌려 랩 DB에 적재 · 조회하고 결과/보기.html에 보인다."""
from pathlib import Path
import json
import show_result as R
import doc_graph as G

HERE = Path(__file__).resolve().parent
TITLE = '검토한 문서 지식을 그래프 DB에 반영하고 관계 확인하기'
PRACTICAL = False
TASK = 'SOP-COOL-14'
LATER_DOCS = ['OEM-HPP45A-MM', 'PR-07']
ITEMS = None                     # 기대_답.csv 질문 칸이 받는 카드 항목 이름(통합반은 None — 「질문 N」)
if PRACTICAL:                         # 실전 카드 랩: 종류마다 계약의 기본 항목, 역할.csv는 다르게 둘 것만
    G.ROLE_DEFAULT.update({'precondition': '준비', 'prohibition': '금지', 'completion': '완료', 'unit_value': '완료', 'step': '순서'})


def guard(fn):
    def run(previous):
        try:
            return fn(previous)
        except G.Problem as e:
            raise R.Stop(str(e))
    return run


def known():
    return G.model_ids()[0]


def shape():
    sh = G.shape()
    if sh is None:
        raise R.Blank('결과/그래프_모양.json이 아직 비어 있습니다.')
    return sh


def table_of(name, values, title):
    got = G.ask(name, values)
    if got is None:
        return R.note(f'{title} — 결과/질문_값.csv에 {name}의 값을 아직 적지 않았습니다.')
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
        raise R.Blank('결과/기대_답.csv에 행이 없습니다.')
    out = [R.table('조회 전에 적은 기대', ['질문', '기대 답', '근거'], [[r['질문'], r['기대_답'], r['근거']] for r in rows])]
    for r in rows:                                   # 근거마다 첫 줄을 원문 그대로(글자 방식은 저절로 — 내가 적은 줄이 그 내용인지 본다)
        for f, n in G.basis_lines(r['근거'])[:1]:
            if (HERE / '자료' / f).is_file():
                out.append(R.source_lines(HERE / '자료' / f, n))
    return out


@guard
def db(previous):
    import lab_cypher
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
        raise R.Blank('결과/연결_규칙.csv에 잇는 방법을 정한 행이 없습니다.')
    if not G.role_rows():
        raise R.Blank('결과/역할.csv에 행이 없습니다.')
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
            if (HERE / '자료' / f).is_file():
                out.append(R.source_lines(HERE / '자료' / f, n))
    return out


@guard
def other(previous):
    shape()
    rows = G.other_rows(known())
    if not rows:
        raise R.Blank('결과/다른문서_조건.csv에 행이 없습니다 — 잇지 않기로 했어도 그 행을 「아니오」로 남깁니다.')
    st = G.load_all()
    vals = G.ask_values()
    out = [R.counts('다시 적재한 뒤(직전 실행과 같으면 늘지 않은 것)', [('노드', st['after']['nodes']), ('관계', st['after']['rels'])]),
           R.table('다른 문서의 조건', ['문서', '판', '절', '글자', '작업', '잇는다', '관계', '근거'], [[r['문서'], r['판'], r['절'], r['인용에_든_글자'], r['작업'], r['잇는다'], r.get('관계', ''), r['근거']] for r in rows])]
    for r in rows:
        for f, n in G.basis_lines(r['근거'])[:1]:
            if (HERE / '자료' / f).is_file():
                out.append(R.source_lines(HERE / '자료' / f, n))
    return out


@guard
def ask123(previous):
    sh = shape()
    vals = G.ask_values()
    if not vals:
        raise R.Blank('결과/질문_값.csv에 값이 없습니다.')
    G.write(HERE / '결과/query.cypher', G.query_file(sh, vals))
    exp = G.expect_rows(ITEMS)
    state = json.loads((HERE / '랩_연결.json').read_text(encoding='utf-8')) if (HERE / '랩_연결.json').is_file() else {}
    return [R.table('내 기대', ['질문', '기대 답', '근거'], [[r['질문'], r['기대_답'], r['근거']] for r in exp]),
            table_of('q1', vals, '질문 1 — 조치마다 단계 · 준비 · 금지 · 완료 · 승인과 근거'),
            table_of('q2', vals, '질문 2 — 규칙마다 근거 원문과 맞는 정도'),
            table_of('q3', vals, '질문 3 — 이 작업이 확인하는 센서(값은 그래프 밖)'),
            table_of('hold', vals, '보류 후보가 그래프에 있는가'),
            R.note('Neo4j Browser로 모양을 볼 때: ' + (state.get('browser') or '랩_연결.json의 Browser 주소') + ' — 결과/query.cypher에서 그 질문의 「// Browser:」 줄의 :param부터 붙여 넣습니다. 터미널로는 「// 터미널:」 줄의 명령을 실행합니다.')]


@guard
def more(previous):
    rules = G.link_rows(known())
    have = {r['문서'] for r in rules}
    if not set(LATER_DOCS) <= have:
        raise R.Blank('결과/연결_규칙.csv에 다른 문서(' + ' · '.join(LATER_DOCS) + ')의 행이 아직 없습니다.')
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
def card(previous):
    sh = shape()
    vals = G.ask_values()
    if 'card' not in vals or not G.now_rows():
        raise R.Blank('결과/질문_값.csv의 card sop와 결과/현재값_원천.csv를 채웁니다.')
    G.write(HERE / '결과/query.cypher', G.query_file(sh, vals))
    G.write(HERE / '결과/남은_질문.json', G.dump(G.remaining(vals)))
    sop = vals['card']['sop']
    text = G.card_text(sop)
    if text is None:
        return [R.note(f'{sop}: 그래프에 그 작업이 없습니다 — 결과 없음.')]
    G.write(HERE / f'결과/작업확인카드_{sop}.md', text)
    exp = G.expect_rows(ITEMS)
    return [R.table('내 기대', ['카드 항목', '기대', '근거'], [[r['질문'], r['기대_답'], r['근거']] for r in exp]), R.note(text)]


@guard
def card_other(previous):
    vals = G.ask_values()
    if 'card_other' not in vals:
        raise R.Blank('결과/질문_값.csv의 card_other sop를 채웁니다.')
    sop = vals['card_other']['sop']
    text = G.card_text(sop)
    out = []
    if text is None:
        out.append(R.note(f'{sop}: 그래프에 그 작업이 없습니다 — 결과 없음.'))
    else:
        G.write(HERE / f'결과/작업확인카드_{sop}.md', text)
        out.append(R.note(text))
    out += [table_of('q5_target', vals, '제공되지 않은 작업 · 대상'), table_of('q5_section', vals, '제공되지 않은 절')]
    return out


@guard
def other_scope(previous):
    vals = G.ask_values()
    extra = [table_of('q4', vals, '질문_값.csv의 q4 doc — 그 문서의 지식이 걸리는 대상')] if 'q4' in vals else []   # 계약 밖 짝이지만 적었으면 결과를 보인다
    return card_other(previous) + [table_of('hold', vals, '보류 후보가 그래프에 있는가(찾은 수 0이어야 함)')] + extra + scope(previous)


@guard
def scope(previous):
    rows = G.now_rows()
    if not rows:
        raise R.Blank('결과/현재값_원천.csv에 행이 없습니다.')
    vals = G.ask_values()
    rq = G.remaining(vals)
    G.write(HERE / '결과/남은_질문.json', G.dump(rq))
    kinds = {}
    for x in rq:
        kinds[x['kind']] = kinds.get(x['kind'], 0) + 1
    out = [R.table('작업 직전 확인할 현재 값과 읽을 원천(그래프에 넣지 않음)', ['작업', '확인할 값', '읽을 원천', '근거'], [[r['작업'], r['확인할_값'], r['읽을_원천'], r['근거']] for r in rows]),
           R.counts('남은 질문(결과/남은_질문.json)', sorted(kinds.items()))]
    if not PRACTICAL:
        out += [table_of('q3', vals, '질문 3 — 이 작업이 확인하는 센서'), table_of('q5_target', vals, '질문 5 — 제공되지 않은 작업 · 대상'), table_of('q5_section', vals, '질문 5 — 제공되지 않은 절')]
    return out


@guard
def save(previous):
    import lab_cypher, subprocess, sys
    vals = G.ask_values()
    G.write(HERE / '결과/남은_질문.json', G.dump(G.remaining(vals)))
    graph = G.export_graph()
    graph['remaining_questions'] = json.loads((HERE / '결과/남은_질문.json').read_text(encoding='utf-8'))
    G.write(HERE / '결과/지식_내보내기.json', G.dump(graph))
    c = G.counts()
    run = subprocess.run([sys.executable, str(HERE / 'check.py')], capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=HERE)
    return [R.counts('내보내기(결과/지식_내보내기.json)', [('노드', len(graph['nodes'])), ('관계', len(graph['rels'])), ('남은 질문', len(graph['remaining_questions'])),
                                                     ('랩 DB 노드', c['nodes']), ('랩 DB 관계', c['rels'])]),
            R.note('python check.py 출력(끝 12줄, 종료 코드 ' + str(run.returncode) + ')\n' + '\n'.join(run.stdout.strip().splitlines()[-12:]))]


STEPS = [
    dict(no=1, name='폴더 · 입력 파악', slots=[], run=look),
    dict(no=2, name='질문과 기대 답 먼저', slots=['결과/기대_답.csv'], run=expect),
    dict(no=3, name='랩 DB 준비와 설비 모델 · 조치 기준 적재', slots=[], run=db),
    dict(no=4, name='판단① 그래프 모양 — 종류 · 관계 · ID', slots=['결과/그래프_모양.json'], run=plan),
    dict(no=5, name='판단② 연결 규칙 · 별칭 · 역할', slots=['결과/연결_규칙.csv', '결과/역할.csv'], run=link),
    dict(no=6, name='판단③ 다른 문서의 조건 · 반복 적재', slots=['결과/다른문서_조건.csv'], run=other),
    dict(no=7, name='판단④ 질문 1 ~ 3 조회와 보류 확인', slots=['결과/질문_값.csv'], run=ask123),
    dict(no=8, name='다른 문서 추가 반영과 기존 연결 비교', slots=[], run=more),
    dict(no=9, name='답할 수 있는 것과 현재 값 · 추가 자료가 필요한 것', slots=['결과/현재값_원천.csv'], run=scope),
    dict(no=10, name='내보내기 · 저장하고 다시 열기', slots=[], run=save),
]

